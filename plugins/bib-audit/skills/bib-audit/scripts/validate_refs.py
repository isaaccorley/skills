"""Audit a BibTeX bibliography against authoritative metadata APIs.

Works the same whether the bibliography is your own pre-submission draft or one
you are reviewing: LLM- and hand-authored bib entries routinely carry
hallucinated titles, truncated author lists, wrong years, and fabricated
identifiers. The fix is to never hand-author bib fields: resolve every entry
from publisher-deposited metadata and diff it against what is in the file.

For a paper that arrives as a PDF (no .bib), use ``resolve_refs.py`` instead —
it takes the raw reference strings lifted out of the reference list.

Resolution order per entry:

* ``eprint``/arXiv DOI       -> arXiv Atom API.
* ``doi`` field present      -> Crossref REST (``api.crossref.org/works/{doi}``).
* neither                    -> Crossref bibliographic title search; the top
                                hit is accepted only if its title is a close
                                match (so we never silently bind to the wrong
                                paper).

For each resolved entry we compare title, author family names, and year, and
print a per-entry verdict. With ``--show-bibtex`` we also emit the canonical
BibTeX straight from the publisher (Crossref content negotiation) or rebuilt
from the arXiv record, reusing the existing citation key so it is drop-in.

Stdlib only. Read-only: it never edits the .bib. Exit code is non-zero if any
entry is fabricated, mismatches, or cannot be resolved, so this doubles as a
pre-submission / CI gate.

Examples::

    python3 validate_refs.py refs.bib                        # full audit
    python3 validate_refs.py refs.bib --key smith2024example --show-bibtex
    python3 validate_refs.py refs.bib --show-bibtex          # audit + drop-in fixes

Set ``BIB_AUDIT_MAILTO`` (or pass ``--mailto``) to join Crossref's polite
pool: an anonymous client gets throttled harder on large bibliographies.
"""

import argparse
import re
import sys
import time
import urllib.error
from dataclasses import dataclass
from pathlib import Path

from bibstyle import AND_OTHERS_RE, author_list_tells, generation_signal, style_findings
from triage import P1_INVENTED, P2_FABRICATED, P3_METADATA, Finding, render_ranked

from bibmeta import (
    TITLE_MATCH_RATIO,
    Record,
    arxiv_by_id,
    canonical_bibtex_from_doi,
    crossref_by_doi,
    crossref_search,
    LookupUnavailable,
    arxiv_search_title,
    openalex_search,
    datacite_by_doi,
    default_mailto,
    family_key,
    title_ratio,
)


@dataclass
class Entry:
    key: str
    etype: str
    fields: dict[str, str]
    raw: str

    def has_identifier(self) -> bool:
        """True if the entry claims a DOI or arXiv ID.

        Drives the fabricated-identifier verdict: an entry that *claims* an
        identifier but fails to resolve through it is a different (and much
        worse) problem than an entry that never had one.
        """
        return bool(self.fields.get("doi") or self.fields.get("eprint"))


def unescape_identifier(value: str) -> str:
    r"""Strip LaTeX escaping from a DOI or arXiv ID before resolving it.

    DBLP escapes underscores for LaTeX, so a perfectly valid DOI arrives as
    ``10.1162/tacl\_a\_00276``. That 404s, and the entry is then reported as a
    fabricated identifier — retraction-grade wording on a correct citation. Hits
    every TACL / MIT Press (``tacl_a_*``, ``coli_a_*``, ``neco.*``) reference in
    any DBLP-exported bibliography. ``delatex`` is applied to titles and names
    but was never applied to identifier fields.
    """
    return value.replace(r"\_", "_").replace(r"\&", "&").replace(r"\%", "%").strip()


def parse_authors_bibtex(value: str) -> list[str]:
    """Split a BibTeX author field into individual names.

    Drops the literal ``others`` token. It is BibTeX's "et al." marker, not a
    surname: keying it as one makes every abbreviated entry report an author
    "in the bib but not on the registry record", which is the invented-author
    signal — a false integrity accusation on a correctly-formed entry. The
    abbreviation itself is still reported, as truncation, by
    ``bibstyle.author_list_tells``.
    """
    parts = re.split(r"\s+and\s+", value.strip())
    return [p.strip() for p in parts if p.strip() and p.strip().lower() != "others"]


def parse_bibtex(text: str) -> list[Entry]:
    """Brace-aware parse of flat BibTeX entries.

    Good enough for a normal refs.bib (no nested @ inside values); extracts the
    entry type, key, and top-level ``field = {...}``/``"..."``/bareword values.
    """
    entries: list[Entry] = []
    i = 0
    n = len(text)
    while i < n:
        at = text.find("@", i)
        if at == -1:
            break
        m = re.match(r"@(\w+)\s*\{", text[at:])
        if not m:
            i = at + 1
            continue
        etype = m.group(1).lower()
        if etype in {"comment", "preamble", "string"}:
            i = at + m.end()
            continue
        body_start = at + m.end()  # just past the opening brace
        depth = 1
        j = body_start
        while j < n and depth > 0:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        body = text[body_start : j - 1]
        raw = text[at:j]
        i = j

        key_match = re.match(r"\s*([^,\s]+)\s*,", body)
        if not key_match:
            continue
        key = key_match.group(1).strip()
        fields = parse_fields(body[key_match.end() :])
        entries.append(Entry(key=key, etype=etype, fields=fields, raw=raw))
    return entries


def parse_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    i = 0
    n = len(body)
    while i < n:
        fm = re.match(r"\s*([A-Za-z][\w-]*)\s*=\s*", body[i:])
        if not fm:
            break
        name = fm.group(1).lower()
        i += fm.end()
        if i >= n:
            break
        if body[i] == "{":
            depth = 1
            i += 1
            start = i
            while i < n and depth > 0:
                if body[i] == "{":
                    depth += 1
                elif body[i] == "}":
                    depth -= 1
                i += 1
            value = body[start : i - 1]
        elif body[i] == '"':
            i += 1
            start = i
            while i < n and body[i] != '"':
                i += 1
            value = body[start:i]
            i += 1
        else:
            start = i
            while i < n and body[i] not in ",\n":
                i += 1
            value = body[start:i].strip()
        fields[name] = re.sub(r"\s+", " ", value).strip()
        comma = body.find(",", i)
        if comma == -1:
            break
        i = comma + 1
    return fields


def detect_arxiv_id(entry: Entry) -> str | None:
    r"""Find the arXiv ID an entry carries, wherever the exporter put it.

    Reading only ``eprint`` misses most of a real ML bibliography. The two
    dominant export formats hide the ID in free-text fields:

    * Google Scholar: ``journal = {arXiv preprint arXiv:2412.08905}``
    * DBLP:           ``journal = {CoRR}, volume = {abs/2402.17463}``

    Measured on one real 332-entry bibliography: 175 entries carried an arXiv ID
    visible ONLY in those fields, and reading just ``eprint`` found 24. Every one
    of the rest fell through to a Crossref title search, which does not hold
    preprints, and was reported as possibly invented. That single omission caused
    35 of 53 false "may not exist" findings on a bibliography with nothing wrong
    with it.
    """
    eprint = entry.fields.get("eprint", "").strip()
    if eprint:
        archive = entry.fields.get("archiveprefix", "").lower()
        if not archive or archive == "arxiv":
            return unescape_identifier(eprint)

    # arXiv mints DataCite DOIs under 10.48550/arXiv.<id>; Crossref lacks these.
    doi = unescape_identifier(entry.fields.get("doi", ""))
    m = re.match(r"10\.48550/arXiv\.(.+)$", doi, re.IGNORECASE)
    if m:
        return m.group(1)

    # Free-text fields, in the order exporters populate them.
    for field in ("journal", "volume", "note", "howpublished", "eprinttype", "booktitle"):
        value = entry.fields.get(field, "")
        if not value:
            continue
        m = re.search(
            r"(?:arxiv[:\s]*|abs/)((?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?)", value, re.I
        )
        if m:
            return re.sub(r"v\d+$", "", m.group(1))
    return None


def resolve(entry: Entry, mailto: str) -> tuple[Record | None, str | None]:
    """Resolve an entry. Returns (record, dead_identifier).

    ``dead_identifier`` is set when the entry claims a DOI or arXiv ID that
    names no paper — the fabricated-identifier case. Callers must not fall
    back to title search and report "add an identifier": the identifier is
    already there, it is simply fake.
    """
    arxiv_id = detect_arxiv_id(entry)
    if arxiv_id:
        rec = arxiv_by_id(arxiv_id, mailto)
        if rec is None:
            return None, f"arXiv:{arxiv_id}"
        return rec, None

    doi = entry.fields.get("doi")
    if doi:
        try:
            return crossref_by_doi(unescape_identifier(doi), mailto), None
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            # Crossref only holds Crossref-registered DOIs. Zenodo, figshare and
            # Dryad DOIs 404 there while being entirely real, so check DataCite
            # before calling the identifier fake — dataset citations are common.
            time.sleep(0.3)
            rec = datacite_by_doi(unescape_identifier(doi), mailto)
            if rec is not None:
                return rec, None
            return None, f"doi:{unescape_identifier(doi)}"

    title = entry.fields.get("title")
    if not title:
        return None, None
    # Full ladder, not Crossref alone. Conference papers at ICML/PMLR,
    # ICLR/OpenReview and NeurIPS D&B have no Crossref DOI, so a Crossref-only
    # fallback reported five real, well-known papers as possibly invented.
    rec = crossref_search(title, mailto)
    if rec is not None:
        return rec, None
    for finder in (arxiv_search_title, openalex_search):
        time.sleep(0.3)
        try:
            rec = finder(title, mailto)
        except LookupUnavailable:
            continue  # one source down says nothing about the work
        if rec is not None:
            return rec, None
    return None, None


def compare(entry: Entry, rec: Record) -> list[tuple[str, str]]:
    """Return (kind, message) issues; kind in {title, author, year}."""
    issues: list[tuple[str, str]] = []

    bib_title = entry.fields.get("title", "")
    if bib_title and rec.title:
        ratio = title_ratio(bib_title, rec.title)
        if ratio < TITLE_MATCH_RATIO:
            issues.append(
                (
                    "title",
                    f"title differs ({ratio:.2f}):\n      bib: {bib_title}\n      api: {rec.title}",
                )
            )

    bib_authors = parse_authors_bibtex(entry.fields.get("author", ""))
    bib_fam = sorted(family_key(a) for a in bib_authors)
    api_fam = sorted(rec.families)
    if rec.families and bib_fam != api_fam:
        if len(bib_fam) != len(api_fam):
            issues.append(
                (
                    "author",
                    f"author count {len(bib_fam)} (bib) vs {len(api_fam)} (api); bib={bib_authors}",
                )
            )
        missing = sorted(set(api_fam) - set(bib_fam))
        extra = sorted(set(bib_fam) - set(api_fam))
        if missing:
            issues.append(("author", f"authors in api but not bib (truncated?): {missing}"))
        if extra:
            # An author the registrar does not have is the fabrication tell:
            # it credits someone for work they did not do.
            issues.append(("author", f"authors in bib but NOT in api (invented?): {extra}"))

    # Accept any year the registrar deposited: Crossref carries both the
    # online-first and print-issue dates, and citing either is correct
    # (e.g. a journal with online 2008, print issue 2009).
    bib_year = entry.fields.get("year", "").strip()
    api_years = rec.years or ([rec.year] if rec.year else [])
    if bib_year and api_years and bib_year not in api_years:
        issues.append(("year", f"year {bib_year} (bib) vs {'/'.join(api_years)} (api)"))

    return issues


def canonical_bibtex(entry: Entry, rec: Record, mailto: str) -> str | None:
    """Return drop-in BibTeX (existing key) from the publisher / arXiv."""
    if rec.doi:
        return canonical_bibtex_from_doi(rec.doi, entry.key, mailto)
    if rec.source == "arxiv":
        arxiv_id = detect_arxiv_id(entry)
        authors = entry.fields.get("author", "")
        return (
            f"@misc{{{entry.key},\n"
            f"  title         = {{{rec.title}}},\n"
            f"  author        = {{{authors}}},\n"
            f"  year          = {{{rec.year}}},\n"
            f"  eprint        = {{{arxiv_id}}},\n"
            f"  archivePrefix = {{arXiv}}\n}}"
        )
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bib", type=Path, help="path to the .bib file to audit")
    parser.add_argument("--key", help="validate only this citation key")
    parser.add_argument(
        "--show-bibtex",
        action="store_true",
        help="print canonical BibTeX (from publisher/arXiv) for flagged entries",
    )
    parser.add_argument(
        "--mailto",
        default=default_mailto(),
        help="contact address for Crossref's polite pool (env: BIB_AUDIT_MAILTO)",
    )
    parser.add_argument("--sleep", type=float, default=0.5, help="delay between requests")
    args = parser.parse_args()

    if not args.bib.exists():
        print(f"error: {args.bib} not found", file=sys.stderr)
        return 2

    entries = parse_bibtex(args.bib.read_text(encoding="utf-8"))
    if args.key:
        entries = [e for e in entries if e.key == args.key]
        if not entries:
            print(f"error: key {args.key!r} not found in {args.bib}", file=sys.stderr)
            return 2

    ok = mismatch = check = unresolved = fabricated = unavailable = 0
    flagged: list[tuple[Entry, Record]] = []
    findings: list[Finding] = []
    and_others: list[str] = []

    for idx, entry in enumerate(entries):
        if idx:
            time.sleep(args.sleep)
        # Style checks are local; run them first so P4 survives a lookup failure.
        findings.extend(style_findings(entry.key, entry.fields))
        if AND_OTHERS_RE.search(entry.fields.get("author", "")):
            and_others.append(entry.key)

        try:
            rec, dead = resolve(entry, args.mailto)
        except (LookupUnavailable, urllib.error.HTTPError) as exc:
            # Never a finding: the reference was not checked, not disproved.
            unavailable += 1
            print(f"[LOOKUP FAILED] {entry.key}: {exc} -- re-run this one")
            continue

        if dead:
            fabricated += 1
            findings.append(Finding(P2_FABRICATED, entry.key,
                f"{dead} resolves to no paper",
                "the identifier in the entry names nothing",
                "re-resolve from the title with lookup_id.py and replace the IDENTIFIER, not the title"))
            print(f"[FABRICATED] {entry.key}: {dead} resolves to no paper")
            print("    - the identifier in the entry is fake; re-resolve from the title")
            print("      with lookup_id.py and replace the identifier, not the title")
            continue

        if rec is None:
            unresolved += 1
            note = (
                "no close title match; may be an invented paper"
                if entry.fields.get("title")
                else "no doi/arxiv id and no title to search"
            )
            print(f"[UNRESOLVED] {entry.key}: {note}")
            if entry.fields.get("title"):
                findings.append(Finding(P1_INVENTED, entry.key,
                    "no match in Crossref or arXiv for this title",
                    "verify by hand; if it truly does not exist, the claim citing it is unsupported",
                    "search the exact title in a browser before acting"))
            continue

        issues = compare(entry, rec)
        # A record bound by fuzzy title search is NOT authoritative. Crossref
        # accepted an R package named "madgrad" for Adam (ratio 0.879) and
        # "Is Attention All You Need?" for the Transformer paper (0.880) — after
        # which every real author reads as "cited but not on the record". That
        # produced 12 false invented-author findings, including reporting Kingma
        # and Ba as not being authors of Adam. Author-set diffs are only
        # meaningful once an identifier pins the work.
        pinned = rec.source in {"crossref:doi", "datacite:doi", "arxiv"}
        if not pinned:
            issues = [(k, m) for k, m in issues if k != "author"]
        findings.extend(author_list_tells(entry.key, entry.fields.get("author", ""), len(rec.families) or None))
        for kind, msg in issues:
            # An author present in the bib but absent from the registry record
            # credits someone falsely -- integrity-shaped, unlike truncation.
            invented_author = pinned and kind == "author" and "NOT in api" in msg
            findings.append(Finding(
                P2_FABRICATED if invented_author else P3_METADATA,
                entry.key,
                msg.splitlines()[0][:110],
                "\n".join(msg.splitlines()[1:]),
                "replace the field from the canonical source (--show-bibtex)"))
        # Hard-fail rule by source. Crossref-by-DOI = publisher metadata, so any
        # diff is a real error. arXiv pins the work but its preprint year/author
        # list legitimately differs from the published citation, so only a title
        # diff is hard there. Title-search may bind the wrong paper -> advisory.
        if rec.source.startswith("crossref:doi"):
            hard = bool(issues)
        elif rec.source == "arxiv":
            # arXiv retitles between versions (GELU v1 "Bridging Nonlinearities
            # ..." -> "Gaussian Error Linear Units (GELUs)"; AdamW likewise). The
            # bib citing the v1 title is correct, so a title diff on an
            # arXiv-resolved record is drift, not a wrong identifier.
            hard = False
        else:
            hard = False

        if not issues:
            ok += 1
            print(f"[OK]         {entry.key}  ({rec.source})")
        elif hard:
            mismatch += 1
            print(f"[MISMATCH]   {entry.key}  ({rec.source})")
            for _, msg in issues:
                print(f"    - {msg}")
            flagged.append((entry, rec))
        else:
            note = (
                "preprint vs published differs"
                if rec.source == "arxiv"
                else "verify match or add a DOI"
            )
            check += 1
            print(f"[CHECK]      {entry.key}  ({rec.source}) -- {note}")
            for _, msg in issues:
                print(f"    - {msg}")

    print(
        f"\n{ok} ok, {fabricated} fabricated identifiers, {mismatch} mismatched "
        f"(authoritative), {check} to check (search-only), {unresolved} unresolved, "
        f"{unavailable} lookup failed, {len(entries)} total"
    )

    findings_p1 = sum(1 for f in findings if f.priority == P1_INVENTED)
    sig = generation_signal(and_others, len(entries))
    if sig:
        findings.append(sig)
    print(render_ranked(findings, len(entries)))

    if args.show_bibtex and flagged:
        print(
            "\n" + "=" * 70 + "\nCanonical BibTeX for mismatched entries (drop-in replacements):\n"
        )
        for pos, (entry, rec) in enumerate(flagged):
            if pos:
                time.sleep(args.sleep)
            bib = canonical_bibtex(entry, rec, args.mailto)
            print(bib or f"% {entry.key}: no canonical source (title-search hit only)")
            print()

    # Everything the ranked report calls P1 or P2 fails the gate. Excluding
    # unresolved entries meant a CI run could pass a bibliography the tool had
    # just reported as containing works that may not exist.
    return 1 if (mismatch or fabricated or findings_p1) else 0


if __name__ == "__main__":
    raise SystemExit(main())
