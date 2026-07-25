"""Audit references supplied as STRUCTURED JSON — the primary PDF workflow.

The parsing problem and the verification problem are different jobs, and mixing
them was a mistake. Turning a rendered reference list back into fields is a
language task: authors, title, venue and year are separated by conventions that
vary per style, and no regex survives contact with real PDFs. An LLM does it in
one pass. This script therefore does NOT parse references at all — it takes
already-structured records and does only what code is good at: hitting the APIs
and comparing fields.

Both APIs want clean fields, which is the other half of the argument:
Semantic Scholar's ``/paper/search/match`` resolves a bare title exactly, and
rejects a raw reference string outright; Crossref's ``query.bibliographic``
accepts a raw string but will confidently bind an invented reference to an
unrelated work. Feed them a parsed title and both behave.

Input: JSON array on stdin or in a file. One object per reference::

    [
      {
        "n": 1,                      # reference number as printed, for reporting
        "title": "U-Net: Convolutional Networks for Biomedical Image Segmentation",
        "authors": ["Ronneberger, O.", "Fischer, P.", "Brox, T."],
        "year": "2015",
        "doi": "10.1007/978-3-319-24574-4_28",   # omit or null if not printed
        "arxiv": "1505.04597",                    # omit or null if not printed
        "venue": "MICCAI",
        "url": "https://...",                     # if the reference prints one
        "identifier_printed": "S0924271626001899",# any other printed handle: PII,
                                                  # EGUsphere id, DBLP key, R version
        "kind": "article",                        # see below; default "article"
        "authors_truncated": false,               # true if the reference printed "et al."
        "anonymized": false,                      # true for "Anonymous. Under review."
        "raw": "Ronneberger, O., ... pages 234-241, 2015."   # optional, for reporting
      }
    ]

Only ``title`` is required. Include ``doi``/``arxiv`` ONLY when actually printed
in the reference — inventing one defeats the entire audit.

``kind`` is one of ``article`` (default), ``dataset``, ``report``, ``software``,
``standard``, ``web``, ``thesis``. Anything other than ``article`` is grey
literature: DOI registries legitimately do not index it, so a miss is reported as
``[UNVERIFIABLE]`` at the housekeeping tier rather than "may not exist". Getting
this wrong in the other direction is what filled the top tier with national
mapping agencies, IPCC guidelines and NOAA atlases on one real paper.

Set ``authors_truncated`` whenever the reference printed "et al." — otherwise a
deliberately partial list is reported as missing authors, which was over half of
all housekeeping findings on real papers.

Usage::

    python3 audit_refs.py refs.json
    pdftotext paper.pdf - | ...LLM extraction... | python3 audit_refs.py -

Stdlib only. Read-only. Exit 1 on P1/P2 findings.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
from pathlib import Path

from bibmeta import (
    LookupUnavailable,
    Record,
    arxiv_by_id,
    arxiv_search_title,
    crossref_by_doi,
    crossref_candidates,
    datacite_by_doi,
    default_mailto,
    family_keys,
    http_get,
    norm_text,
    openalex_search,
    s2_batch,
    TITLE_ACCEPT_RATIO,
    title_coverage,
    title_ratio,
)
from triage import P1_INVENTED, P2_FABRICATED, P3_METADATA, Finding, render_ranked

S2_MATCH = "https://api.semanticscholar.org/graph/v1/paper/search/match"


def s2_match_title(title: str, mailto: str) -> dict | None:
    """Resolve a clean title to identifiers via Semantic Scholar's matcher.

    Returns the externalIds dict (DOI / ArXiv / ...) or None. Used ONLY to find
    out *which* paper a reference names; the authoritative metadata is then
    re-fetched from the registrar, because S2 returns v1 preprint titles (it
    reports "Fixing Weight Decay Regularization in Adam" for the work published
    as "Decoupled Weight Decay Regularization").
    """
    params = urllib.parse.urlencode({"query": title, "fields": "title,externalIds"})
    try:
        payload = json.loads(http_get(f"{S2_MATCH}?{params}", "application/json", mailto))
    except (urllib.error.HTTPError, json.JSONDecodeError):
        return None  # 404 here means "no title match", which is a real answer
    data = payload.get("data") or []
    if not data:
        return None
    hit = data[0]
    if title_ratio(title, hit.get("title") or "") < 0.85:
        return None
    return hit.get("externalIds") or {}



# Crossref work types that a normal paper reference should not resolve to. A
# fuzzy title search will happily return a thesis or a book chapter whose title
# restates a famous paper's, and the title score cannot tell the difference --
# "Graph based image segmentation" (an HKUST master's thesis) and "Is Attention
# All You Need?" (a 2025 book chapter) both scored as accepted binds.
UNLIKELY_BIND_TYPES = {
    "dissertation", "book-chapter", "book", "book-part", "book-section",
    "monograph", "edited-book", "reference-book", "book-series",
}
# Words in the reference's own venue/kind that make such a type legitimate --
# people really do cite theses and book chapters, just not usually by accident.
_TYPE_OK_WORDS = ("thesis", "dissertation", "book", "chapter", "monograph", "phd", "msc", "master")


def type_is_plausible(cand: Record, ref: dict) -> bool:
    """Reject a bind whose publication type contradicts the reference.

    Only fires on the types above, and only when the reference gives no sign of
    citing that kind of work. A reference that genuinely cites a thesis says so
    in its venue, so this costs nothing on correct entries.
    """
    if cand.ctype not in UNLIKELY_BIND_TYPES:
        return True
    described = norm_text(f"{ref.get('venue') or ''} {ref.get('kind') or ''} {ref.get('raw') or ''}")
    return any(word in described for word in _TYPE_OK_WORDS)


def bind_is_credible(cand: Record, ref: dict) -> bool:
    """Should a fuzzy title-search hit be accepted as the cited work?

    Coverage alone is not enough, and asymmetric coverage is actively dangerous:
    it divides by the length of the REGISTRAR title, so any shorter registrar
    title contained in the reference scores 1.0. That bound "Efficient
    graph-based image segmentation" to a master's thesis titled "Graph based
    image segmentation" (cov 1.000) and "Attention is all you need" to a 2025
    book chapter "Is Attention All You Need?" (cov 0.905, ratio 0.880) -- after
    which the real authors were reported as invented.

    So: require similarity in BOTH directions, require at least one author in
    common when the reference names any, and reject a hit whose publication TYPE
    is not the kind of thing the reference describes. Every wrong bind observed in
    testing had zero author overlap, which makes it the cheapest reliable
    discriminator; the type check is defence in depth, and it happens to catch
    both of the binds above on its own (`dissertation` and `book-chapter`) even
    when the author lists are unavailable to compare.
    """
    title = (ref.get("title") or "").strip()
    if not title or not cand.title:
        return False
    if title_ratio(title, cand.title) < TITLE_ACCEPT_RATIO:
        return False
    if title_coverage(cand.title, title) < 0.80 or title_coverage(title, cand.title) < 0.80:
        return False
    if not type_is_plausible(cand, ref):
        return False
    cited = {k for a in (ref.get("authors") or []) for k in family_keys(a)}
    if cited and cand.families:
        known = {k for f in cand.families for k in family_keys(f)}
        if not (cited & known):
            return False
    return True


def resolve(ref: dict, mailto: str) -> tuple[Record | None, str | None, str]:
    """Resolve one structured reference. Returns (record, dead_identifier, how)."""
    arxiv = (ref.get("arxiv") or "").strip()
    if arxiv:
        try:
            rec = arxiv_by_id(arxiv, mailto)
        except urllib.error.HTTPError as exc:
            if exc.code != 400:
                raise
            # arXiv returns 400 for a malformed id (a wrap-truncated one, say).
            # That is "this string is not an id", not "this paper is fake".
            return None, None, "arxiv:malformed"
        return (rec, None, "arxiv") if rec else (None, f"arXiv:{arxiv}", "arxiv")

    doi = (ref.get("doi") or "").strip()
    if doi:
        try:
            return crossref_by_doi(doi, mailto), None, "crossref:doi"
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            time.sleep(0.15)
            rec = datacite_by_doi(doi, mailto)  # Zenodo/figshare/Dryad are real
            return (rec, None, "datacite:doi") if rec else (None, f"doi:{doi}", "crossref:doi")

    title = (ref.get("title") or "").strip()
    if not title:
        return None, None, "no-title"

    # Grey literature and blinded references carry no identifier by nature, and a
    # title search for them binds something spurious: an ESA validation report
    # bound to a 1995 book chapter titled "Model validation", and a software
    # citation to the same-named CRAN package -- each then producing phantom
    # author and year findings. Do not search; report as unverifiable.
    if (ref.get("kind") or "article").lower() != "article" or ref.get("anonymized"):
        return None, None, "grey"

    # No printed identifier: let the APIs do the matching, on a clean title.
    # Each source is tried independently — one being rate-limited or down must
    # not abort the reference, or a flaky third party turns into "unverifiable"
    # for an entry the next source would have resolved immediately. Only when
    # every source is unavailable is the reference genuinely unchecked.
    # Count sources that gave a definitive answer. "Not found" needs a quorum of
    # two, not unanimity: an HTTP 404 from S2 and a clean empty result from
    # Crossref are both real noes, and demanding that every source also answer
    # turns any third party's rate limit into "unverifiable".
    answered = 0

    try:
        ids = s2_match_title(title, mailto)
        answered += 1
    except LookupUnavailable:
        ids = None
    if ids is not None:
        # ICLR / OpenReview / DBLP-only records carry NEITHER DOI nor ArXiv --
        # only DBLP + CorpusId. Falling through on those reported real,
        # heavily-cited papers as "may not exist", the worst output this tool
        # can produce. An S2 match above the ratio gate IS existence evidence;
        # we just cannot use S2 metadata for comparison (v1 preprint titles),
        # so the record is returned with empty fields and compares as clean.
        if not ids.get("DOI") and not ids.get("ArXiv"):
            return (
                Record(source="s2:match", title="", families=[], year=None, years=[]),
                None,
                "s2:match",
            )
        if ids.get("DOI"):
            time.sleep(0.15)
            try:
                return crossref_by_doi(ids["DOI"], mailto), None, "s2->crossref"
            except LookupUnavailable:
                pass
            except urllib.error.HTTPError as exc:
                # ACM DL DOIs (10.5555/...) are not Crossref-registered, so
                # Dropout's own DOI 404s here. The printed-DOI branch already
                # falls back to DataCite; this one did not.
                if exc.code == 404:
                    time.sleep(0.15)
                    rec = datacite_by_doi(ids["DOI"], mailto)
                    if rec is not None:
                        return rec, None, "s2->datacite"
        if ids.get("ArXiv"):
            time.sleep(0.15)
            try:
                rec = arxiv_by_id(ids["ArXiv"], mailto)
                if rec:
                    return rec, None, "s2->arxiv"
            except LookupUnavailable:
                pass

    time.sleep(0.15)
    try:
        for cand in crossref_candidates(title, mailto, rows=3):
            if bind_is_credible(cand, ref):
                return cand, None, "crossref:search"
        answered += 1
    except LookupUnavailable:
        pass

    # arXiv title search — exists in bibmeta and was only ever called by the
    # deprecated path, so the primary path regressed against its predecessor and
    # reported real preprints as nonexistent.
    time.sleep(0.15)
    try:
        rec = arxiv_search_title(title, mailto)
        answered += 1
        if rec is not None and bind_is_credible(rec, ref):
            return rec, None, "arxiv:search"
    except LookupUnavailable:
        pass

    time.sleep(0.15)
    try:
        rec = openalex_search(title, mailto)
        answered += 1
        if rec is not None and bind_is_credible(rec, ref):
            return rec, None, "openalex"
    except LookupUnavailable:
        pass

    if answered < 2:
        raise LookupUnavailable(
            f"only {answered} of 4 title sources answered; result inconclusive"
        )
    # Report how many sources actually answered, not a fixed list of names: with
    # OpenAlex budget-limited and S2 intermittently 500ing, the old hardcoded
    # "no match in S2, Crossref or OpenAlex" named sources never consulted.
    return None, None, f"search:{answered}-sources"


def compare(ref: dict, rec: Record, how: str = "") -> tuple[list[str], bool, list[str]]:
    """Compare structured fields.

    Returns (issues, identifier_names_other_work, invented_authors).
    ``invented_authors`` is separate because an author cited but absent from the
    registrar record is integrity-shaped -- triage's P2 tier is literally titled
    "Fabricated identifier or invented author" -- while a short author list is
    housekeeping. Collapsing both into one P3 list buried seven verified
    wrong-author findings under guidance reading "Not an integrity issue".
    """
    issues: list[str] = []

    title = (ref.get("title") or "").strip()
    wrong_work = False
    if title and rec.title:
        coverage = title_coverage(rec.title, title)
        if coverage < 0.80:
            issues.append(f"title mismatch ({coverage:.0%} overlap): registrar has {rec.title!r}")
            wrong_work = coverage < 0.45

    # Compare key SETS per author: a name can legitimately key several ways
    # (diacritic folding, compound surnames), and requiring one exact key made
    # correct entries look wrong.
    markers = {"others", "al", "etal", "anonymous", "anon"}
    cited_names = [a for a in (ref.get("authors") or []) if a]
    cited_sets = [family_keys(a) - markers for a in cited_names]
    cited_sets = [k for k in cited_sets if k]
    known_sets = [family_keys(f) - markers for f in rec.families]
    known_sets = [k for k in known_sets if k]

    invented_authors: list[str] = []
    if cited_sets and known_sets:
        known_all = set().union(*known_sets)
        for name, keys in zip(cited_names, cited_sets):
            if not (keys & known_all):
                invented_authors.append(name)
        if invented_authors:
            issues.append(f"author(s) cited but NOT on the registrar record: {invented_authors}")

        # Truncation is only a finding when the reference claims a COMPLETE list.
        # A printed "et al." means the list is partial by design, and reporting it
        # was 16 of 30 P3 findings on one paper -- pure noise, and contradicting
        # this skill's own documentation.
        if not ref.get("authors_truncated"):
            cited_all = set().union(*cited_sets)
            missing = [k for k in known_sets if not (k & cited_all)]
            if len(missing) > 2:
                issues.append(f"{len(missing)} author(s) on the record but not cited")

    year = str(ref.get("year") or "").strip()
    years = set(rec.years or ([rec.year] if rec.year else []))
    # An arXiv record knows only when the preprint was POSTED. A reference citing
    # the conference year is then correct and a diff is a resolution artifact, not
    # a finding — this fired systematically on ICLR/NeurIPS papers.
    arxiv_sourced = "arxiv" in how or rec.source.startswith("arxiv")
    if year and years and year not in years:
        if arxiv_sourced and any(0 < int(year) - int(y) <= 3 for y in years if y.isdigit()):
            pass  # preprint posted earlier than the cited venue year
        else:
            issues.append(f"year {year} cited vs {'/'.join(sorted(years))} on record")

    return issues, wrong_work, invented_authors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("refs", help="JSON file of structured references, or - for stdin")
    ap.add_argument("--mailto", default=default_mailto(), help="Crossref polite pool contact")
    ap.add_argument("--sleep", type=float, default=0.2,
                help="pause between references; lower is faster, 0 for maximum speed")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.refs == "-" else Path(args.refs).read_text(encoding="utf-8")
    try:
        refs = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"error: input is not valid JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(refs, list):
        print("error: expected a JSON array of reference objects", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    ok = fabricated = check = notfound = unavailable = 0


    for i, ref in enumerate(refs, start=1):
        if i > 1:
            time.sleep(args.sleep)
        label = str(ref.get("n") or i)
        shown = (ref.get("title") or ref.get("raw") or "?")[:66]
        try:
            rec, dead, how = resolve(ref, args.mailto)
        except LookupUnavailable as exc:
            unavailable += 1
            print(f"[LOOKUP FAILED] {label}: {exc} — NOT a finding, re-run this one")
            continue

        if dead:
            fabricated += 1
            print(f"[FABRICATED] {label}: {dead} names no paper")
            findings.append(Finding(P2_FABRICATED, f"ref {label}", f"{dead} names no paper",
                                    shown, "correct the identifier, never the title"))
            continue
        if rec is None:
            kind = (ref.get("kind") or "article").lower()
            if ref.get("anonymized"):
                check += 1
                print(f"[UNVERIFIABLE] {label}: anonymized for blind review — expected")
                continue
            if kind != "article":
                # Grey literature: absence from a DOI registry is not evidence.
                check += 1
                print(f"[UNVERIFIABLE] {label}: {kind} — not indexed by DOI registries")
                findings.append(Finding(
                    P3_METADATA, f"ref {label}", f"{kind} citation cannot be registrar-verified",
                    shown,
                    "check the URL resolves and an access date is given; prefer a "
                    "Zenodo/DataCite DOI if the resource has one"))
                continue
            notfound += 1
            n_src = how.split(":")[-1] if how.startswith("search:") else "?"
            print(f"[NOT FOUND]  {label}: no title match ({n_src} answered)")
            findings.append(Finding(P1_INVENTED, f"ref {label}",
                                    f"no title match; {n_src} answered", shown,
                                    "search the exact title by hand before concluding"))
            continue

        issues, wrong_work, invented = compare(ref, rec, how)
        pinned = how in {"arxiv", "crossref:doi", "datacite:doi", "s2->crossref", "s2->arxiv"}
        if wrong_work and how in {"arxiv", "crossref:doi", "datacite:doi"}:
            fabricated += 1
            print(f"[FABRICATED] {label}: printed identifier names a different paper")
            for m in issues:
                print(f"    - {m}")
            findings.append(Finding(P2_FABRICATED, f"ref {label}",
                                    "printed identifier names a different paper",
                                    "\n".join(issues), "re-resolve the identifier from the title"))
        elif issues:
            check += 1
            # Distinguish a fuzzy title bind from an identifier-pinned record: on
            # an unpinned bind the "authors" may belong to a different paper
            # entirely, so its diffs are never evidence about the cited work.
            print(f"[CHECK]      {label} ({how})" + ("" if pinned else " -- search-only, verify the bind"))
            for m in issues:
                print(f"    - {m}")
            if invented and pinned:
                findings.append(Finding(
                    P2_FABRICATED, f"ref {label}",
                    f"author(s) cited but not on the registrar record: {invented}",
                    f"identifier resolved via {how}; the work is right, these names are not on it",
                    "correct the author list from the registrar record"))
            rest = [m for m in issues if not m.startswith("author(s) cited but NOT")]
            if rest:
                findings.append(Finding(
                    P3_METADATA, f"ref {label}", rest[0][:110], "\n".join(rest[1:]),
                    "correct from the registrar record" if pinned
                    else "verify the search bind before acting"))
        else:
            ok += 1
            print(f"[OK]         {label} ({how})")

    print(f"\n{ok} ok, {fabricated} fabricated, {check} to check, {notfound} not found, "
          f"{unavailable} lookup failed, {len(refs)} references")
    print(render_ranked(findings, len(refs)))
    return 1 if (fabricated or notfound) else 0


if __name__ == "__main__":
    raise SystemExit(main())
