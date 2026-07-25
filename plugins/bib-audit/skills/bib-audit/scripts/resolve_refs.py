"""Audit a reference list that is plain text, not BibTeX.

For papers that arrive as a PDF (reviewing someone else's submission, checking
a preprint, auditing your own camera-ready) there is no .bib to parse — only the
rendered reference list. This resolves each raw reference string against
Crossref/arXiv and applies the same fabrication checks as ``validate_refs.py``.

Input: a text file of references, one per line, or separated by blank lines for
references that wrap across lines. Numbering (``[12]``, ``12.``) is stripped.
Get that text with either::

    pdftotext paper.pdf - | sed -n '/^ *References *$/,$p' > refs.txt
    # or have Claude read the PDF and write out the reference list

Use plain ``pdftotext``, NOT ``-layout``: on a two-column paper ``-layout``
splices the left and right columns onto each output line and no reference
survives intact. Margin line numbers from papers under review are detected and
stripped automatically (see ``strip_line_numbers``).

Then::

    python3 resolve_refs.py refs.txt
    python3 resolve_refs.py refs.txt --emit-bibtex > recovered.bib

Verdicts::

    [OK]             resolved and consistent with the reference string
    [SUSPECT]        a printed DOI/arXiv id names no paper, or names a work
                     whose title is clearly not the one cited -- PROVISIONAL
    [CHECK]          bound by title search, or resolved with an author/year
                     discrepancy, or anonymized for blind review -- advisory
    [NOT FOUND]      no match in Crossref, arXiv or OpenAlex -- PROVISIONAL
    [LOOKUP FAILED]  rate limit or outage; says nothing about the reference

**Every finding from this script is capped at P3 (advisory), by design.** This
path splits and parses the reference list with heuristics, and that parsing --
not any API answer -- is what produced every false fabrication verdict found
during development. It also silently drops text on author-year bibliographies
(ICLR/ACL/NeurIPS style, no ``[N]`` markers), where a capitalised continuation
line reads as a new reference: one real paper lost 26% of its list that way.

So this script is structurally unable to report P1 (work does not exist) or P2
(fabricated identifier / invented author). An unreliable parser must not put an
integrity-shaped accusation next to somebody's name. It still exits non-zero, so
it works as a CI gate; when you need a verdict you can actually defend, use
``audit_refs.py``, where a reader extracts the fields.

Stdlib only. Read-only. Exit 1 on suspect or unfindable references.
"""

import argparse
import re
import sys
import time
import urllib.error
from pathlib import Path

from bibmeta import (
    TITLE_ACCEPT_RATIO,
    LookupUnavailable,
    datacite_by_doi,
    Record,
    arxiv_by_id,
    arxiv_search_title,
    canonical_bibtex_from_doi,
    crossref_by_doi,
    crossref_candidates,
    default_mailto,
    norm_text,
    title_coverage,
    openalex_search,
    title_ratio,
)

# P1_INVENTED and P2_FABRICATED are deliberately NOT imported: this path's
# heuristic parsing is not reliable enough to justify an integrity-shaped
# finding, so every finding it emits is capped at P3. See the module docstring.
from triage import P3_METADATA, Finding, render_ranked

from refparse import (
    YEAR_RE,
    guess_title,
    is_anonymized,
    is_grey_literature,
    printed_arxiv,
    printed_doi,
    split_references,
)


def agrees(ref: str, rec: Record) -> tuple[list[str], bool]:
    """Cross-check a resolved record against the reference string.

    Returns (issues, title_clearly_wrong). Only the second value may escalate to
    a fabrication finding. Author- and year-level disagreements are NOT
    fabrication evidence on a messy PDF-extracted string: "et al." hides the
    author order, extraction mangles diacritics (``Gökçe`` arrives as
    ``Gök"e``, so a surname check against "gokce" fails on a correct
    entry), and preprint-vs-published years legitimately differ. Escalating any
    of those produced six false fabrication findings in one real paper.
    """
    issues: list[str] = []
    ref_norm = norm_text(ref)

    if is_anonymized(ref):
        # Nothing to compare against; the caller downgrades this to a CHECK.
        return ["reference is anonymized for review -- cannot verify authorship"], False

    title_clearly_wrong = False
    if rec.title:
        # Search the WHOLE reference for the registrar's title rather than
        # extracting a title from the reference and comparing. Extraction is the
        # fragile step and it decided verdicts it had no business deciding.
        coverage = title_coverage(rec.title, ref)
        if coverage < 0.80:
            issues.append(
                f"only {coverage:.0%} of the registrar title appears in the reference: "
                f"api={rec.title!r}"
            )
            # A partial match is extraction noise (wraps, lost accents, ligatures).
            # Near-zero overlap means the identifier names a different work.
            title_clearly_wrong = coverage < 0.45

    if rec.families:
        first = rec.families[0]
        # Prefix match, not exact-token: survives mangled diacritics and the
        # hyphenation/truncation that PDF extraction introduces.
        tokens = ref_norm.split()
        # No length floor on the token: short surnames are real ("Wu", "Xu",
        # "Ng"), and filtering them out made a reference whose FIRST WORD was
        # the author read as author-missing.
        if first and not any(
            t == first or t.startswith(first[:5]) or first.startswith(t) for t in tokens
        ):
            issues.append(f"first author {first!r} (api) not found in the reference")

    years_in_ref = set(YEAR_RE.findall(ref))
    api_years = set(rec.years or ([rec.year] if rec.year else []))
    if years_in_ref and api_years and not (years_in_ref & api_years):
        issues.append(
            f"year {'/'.join(sorted(years_in_ref))} (ref) vs {'/'.join(sorted(api_years))} (api)"
        )

    return issues, title_clearly_wrong


def resolve_reference(ref: str, mailto: str) -> tuple[Record | None, str | None, str]:
    """Return (record, dead_identifier, how) for one raw reference string."""
    aid = printed_arxiv(ref)
    if aid:
        rec = arxiv_by_id(aid, mailto)
        if rec is None:
            return None, f"arXiv:{aid}", "arxiv"
        return rec, None, "arxiv"

    doi = printed_doi(ref)
    if doi:
        try:
            return crossref_by_doi(doi, mailto), None, "crossref:doi"
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            # Not in Crossref is not the same as not existing: DataCite holds
            # Zenodo/figshare/Dryad DOIs, which are legitimate citations.
            time.sleep(0.3)
            rec = datacite_by_doi(doi, mailto)
            if rec is not None:
                return rec, None, "datacite:doi"
            return None, f"doi:{doi}", "crossref:doi"

    # No printed identifier: search, widening across sources. Crossref misses
    # arXiv-only preprints entirely, so a Crossref miss alone is NOT evidence
    # that a paper does not exist -- only all three missing is.
    title = guess_title(ref)
    # Query the trimmed title AND the raw reference string. Neither wins alone:
    # trimming can drop the one disambiguating token (dropping "U-Net:" leaves
    # a generic phrase that binds to the wrong paper), while the raw string's
    # author and venue noise sinks other lookups. Crossref's bibliographic
    # query is built to accept a whole reference, so trying both is cheap.
    for query in (title, " ".join(ref.split())[:300]):
        cands = crossref_candidates(query, mailto, rows=1)
        if not cands:
            continue
        rec = cands[0]
        # Accept on coverage of the registrar title within the whole reference.
        if title_coverage(rec.title, ref) >= 0.80 or title_ratio(title, rec.title) >= TITLE_ACCEPT_RATIO:
            return rec, None, "search"
        time.sleep(0.3)

    for finder in (arxiv_search_title, openalex_search):
        time.sleep(0.5)
        try:
            rec = finder(title, mailto)
        except LookupUnavailable:
            continue  # one source down is not evidence about the paper
        if rec is not None:
            return rec, None, rec.source
    return None, None, "search"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("refs", type=Path, help="text file of references (one per line or blank-line separated)")
    parser.add_argument(
        "--emit-bibtex",
        action="store_true",
        help="print canonical BibTeX for every resolved reference",
    )
    parser.add_argument(
        "--mailto",
        default=default_mailto(),
        help="contact address for Crossref's polite pool (env: BIB_AUDIT_MAILTO)",
    )
    parser.add_argument("--sleep", type=float, default=0.5, help="delay between requests")
    args = parser.parse_args()

    if not args.refs.exists():
        print(f"error: {args.refs} not found", file=sys.stderr)
        return 2

    refs = split_references(args.refs.read_text(encoding="utf-8"))
    if not refs:
        print(f"error: no references parsed out of {args.refs}", file=sys.stderr)
        return 2

    print(
        "NOTE: references were split and parsed by heuristic, so every finding below\n"
        "      is PROVISIONAL and capped at advisory (P3). Do not put any of it in a\n"
        "      review without re-running through audit_refs.py. See --help.\n"
    )

    ok = fabricated = check = notfound = unavailable = unindexed = 0
    resolved: list[tuple[int, Record]] = []
    findings: list[Finding] = []

    for idx, ref in enumerate(refs, start=1):
        if idx > 1:
            time.sleep(args.sleep)
        label = f"{idx:3d}"
        short = ref[:70] + ("..." if len(ref) > 70 else "")
        try:
            rec, dead, how = resolve_reference(ref, args.mailto)
        except LookupUnavailable as exc:
            # Never let our own rate limiting read as a finding about the paper.
            unavailable += 1
            print(f"[LOOKUP FAILED] {label} {exc} -- re-run this one; NOT a finding")
            print(f"    ref: {short}")
            continue
        except urllib.error.HTTPError as exc:
            unavailable += 1
            print(f"[LOOKUP FAILED] {label} HTTP {exc.code} -- NOT a finding: {short}")
            continue

        if dead:
            fabricated += 1
            print(f"[SUSPECT]    {label} {dead} names no paper (provisional)")
            print(f"    ref: {short}")
            findings.append(Finding(P3_METADATA, f"ref {idx}",
                f"{dead} names no paper — PROVISIONAL, parsed by heuristic",
                short,
                "check the extraction did not truncate the identifier at a line wrap, "
                "then resolve it in a browser. Re-run through audit_refs.py before "
                "treating this as a real finding"))
            continue

        if rec is None:
            if is_anonymized(ref):
                # Expected and correct: the work is withheld for blind review.
                check += 1
                print(f"[CHECK]      {label} anonymized for review -- unresolvable by design")
                print(f"    ref: {short}")
                continue
            if is_grey_literature(ref):
                # A dataset, standard or agency report. Absence from the DOI
                # registries is expected and is NOT evidence about existence.
                unindexed += 1
                print(f"[UNINDEXED]  {label} dataset/report/web resource — not DOI-indexed")
                print(f"    ref: {short}")
                findings.append(Finding(P3_METADATA, f"ref {idx}",
                    "grey literature — cannot be verified against a DOI registry",
                    short,
                    "check the URL still resolves and that an access date is given; "
                    "prefer a Zenodo/DataCite DOI if the dataset has one"))
                continue
            notfound += 1
            print(f"[NOT FOUND]  {label} no Crossref/arXiv/OpenAlex match")
            print(f"    ref: {short}")
            findings.append(Finding(P3_METADATA, f"ref {idx}",
                "no match in Crossref, arXiv or OpenAlex — PROVISIONAL",
                short,
                "most likely a parse failure, not a missing paper: this path merges and "
                "drops references on author-year lists. Confirm the extracted count "
                "matches the paper, then re-run through audit_refs.py"))
            continue

        issues, title_wrong = agrees(ref, rec)
        # Escalate to a fabrication finding ONLY when a printed identifier
        # resolves to a work whose title is clearly not the cited one. Author
        # or year disagreements alone stay advisory -- see agrees().
        authoritative = how in {"arxiv", "crossref:doi", "datacite:doi"} and not is_anonymized(ref)
        if authoritative and title_wrong:
            # A printed identifier that resolves to a work the reference does
            # not describe is the same failure as a dead one: the id is wrong.
            fabricated += 1
            print(f"[SUSPECT]    {label} printed identifier resolves to a different paper (provisional)")
            for msg in issues:
                print(f"    - {msg}")
            print(f"    ref: {short}")
            findings.append(Finding(P3_METADATA, f"ref {idx}",
                "printed identifier resolves to a different paper — PROVISIONAL",
                "\n".join(issues) + f"\nref: {short}",
                "confirm the reference parsed intact, then re-resolve from the title. "
                "Re-run through audit_refs.py before treating this as a real finding"))
            continue

        if issues:
            check += 1
            print(f"[CHECK]      {label} ({how}) {short}")
            for msg in issues:
                print(f"    - {msg}")
            findings.append(Finding(P3_METADATA, f"ref {idx}",
                issues[0][:110], "\n".join(issues[1:]),
                "advisory — confirm against the published record"))
        else:
            ok += 1
            print(f"[OK]         {label} ({how}) {short}")
        resolved.append((idx, rec))

    print(
        f"\n{ok} ok, {fabricated} fabricated, {check} to check, {notfound} not found, "
        f"{unindexed} unindexed (grey lit), {unavailable} lookup failed, "
        f"{len(refs)} references"
    )
    print(render_ranked(findings, len(refs)))
    if unavailable:
        print(
            f"warning: {unavailable} reference(s) could not be checked (rate limit or "
            "outage). Re-run before drawing any conclusion about those."
        )

    if args.emit_bibtex:
        print("\n" + "=" * 70 + "\nRecovered BibTeX:\n")
        for pos, (idx, rec) in enumerate(resolved):
            if not rec.doi:
                print(f"% ref {idx}: resolved via {rec.source}, no DOI to negotiate")
                continue
            if pos:
                time.sleep(args.sleep)
            key = f"{rec.families[0] if rec.families else 'ref'}{rec.year or ''}"
            print(canonical_bibtex_from_doi(rec.doi, key, args.mailto))
            print()

    return 1 if (fabricated or notfound) else 0


if __name__ == "__main__":
    raise SystemExit(main())
