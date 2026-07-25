"""Mechanical bib-hygiene checks — local only, no network.

Implements the checkable subset of the field-authoring rules in SKILL.md (John
Owens, "Common Errors in Bibliographies"). These are P4 findings: none of them
change *which* paper is cited, so they are safe to batch-fix last. They are worth
automating anyway because they are the ones a human reviewer never has the
patience to check across sixty entries.

Also detects the "and others" pattern, which needs care -- see
``author_list_tells``.

Stdlib only.
"""

import re

from triage import P3_METADATA, P4_STYLE, Finding

# "and others" is valid BibTeX -- the .bst renders it as "et al.", so it never
# looks broken in the built PDF. It is still worth flagging, because a reference
# manager exporting a real record writes every author: the phrase appearing in
# .bib SOURCE means the entry was authored without knowing the full list, which
# is a reliable tell for a generated bibliography.
AND_OTHERS_RE = re.compile(r"\band\s+others\b", re.I)


def style_findings(key: str, fields: dict[str, str]) -> list[Finding]:
    """P4 formatting findings for one .bib entry."""
    out: list[Finding] = []

    pages = fields.get("pages", "")
    if pages and re.fullmatch(r"\s*\d+\s*-\s*\d+\s*", pages):
        out.append(
            Finding(P4_STYLE, key, "page range uses a single hyphen", f"pages = {{{pages}}}",
                    "use an en-dash: 35--49")
        )
    if pages and re.fullmatch(r"\s*1\s*(--?|–)\s*\d+\s*", pages):
        out.append(
            Finding(P4_STYLE, key, "page range starts at 1 — often placeholder pages",
                    f"pages = {{{pages}}}",
                    "confirm against the published version; for e-proceedings use 12:1--12:10, "
                    "otherwise omit pages")
        )

    doi = fields.get("doi", "")
    if doi and re.search(r"https?://|doi\.org", doi, re.I):
        out.append(
            Finding(P4_STYLE, key, "doi field contains a URL, not a bare DOI",
                    f"doi = {{{doi}}}", "store only the 10.xxxx/yyy portion")
        )
    url = fields.get("url", "")
    if doi and url and doi.lower().split("doi.org/")[-1] in url.lower():
        out.append(
            Finding(P4_STYLE, key, "url duplicates the doi", f"url = {{{url}}}",
                    "drop the url; the doi field already carries it")
        )

    month = fields.get("month", "")
    if month and not re.fullmatch(r"[a-z]{3}", month.strip(), re.I):
        if re.fullmatch(r"[A-Za-z]{4,}", month.strip()):
            out.append(
                Finding(P4_STYLE, key, "month spelled out instead of a BibTeX macro",
                        f"month = {{{month}}}", "use an unquoted 3-letter macro: month = mar")
            )

    title = fields.get("title", "")
    # Only complain when the braced span is a real multi-word title. "{{GQA}}"
    # or "{{ChatML}}" is the CORRECT way to protect a single all-caps token, and
    # flagging it sent authors to "fix" properly-protected entries.
    braced_whole = title.startswith("{") and title.endswith("}") and title.count("{") == 1
    if braced_whole and (" " in title.strip("{}").strip() or title.strip("{}")[:1].islower()):
        out.append(
            Finding(P4_STYLE, key, "title is double-braced, overriding the style's casing",
                    f"title = {{{title}}}",
                    "brace only the words that must keep caps ({GPU}, {L}oop), not the whole title")
        )
    if title and len(title) > 8 and title == title.upper():
        out.append(
            Finding(P4_STYLE, key, "title is ALL CAPS as exported", f"title = {{{title[:60]}}}",
                    "rewrite in title case; brace only true acronyms")
        )

    author = fields.get("author", "")
    if re.search(r"\b[A-Z]\.[A-Z]\.", author):
        out.append(
            Finding(P4_STYLE, key, "initials not space-separated",
                    f"author = {{{author[:70]}}}",
                    "write J. D. Owens — BibTeX reads J.D. as one first name and abbreviated "
                    "styles then emit only 'J.'")
        )


    return out


def author_list_tells(key: str, author_field: str, api_author_count: int | None) -> list[Finding]:
    """Findings about a truncated author list.

    ``and others`` is valid BibTeX syntax -- the .bst renders it as "et al." --
    so it will never look broken in the built PDF. That is exactly why it is worth
    flagging: it is the shape a generated entry takes when the author list was
    never actually known. A reference manager exporting a real record emits every
    author; "and others" in the .bib source means someone (or something) wrote the
    entry by hand without the full list. Two things follow:

    * Owens's rule is to record authors exactly as printed, so a *published*
      entry should normally carry them all.
    * When the real paper has only a handful of authors, abbreviating is
      unnecessary -- and a short listed prefix followed by "and others" is a
      recognisable machine-generation pattern rather than something a person
      typing from the PDF would produce.
    """
    out: list[Finding] = []
    if not AND_OTHERS_RE.search(author_field):
        return out

    listed = len([p for p in re.split(r"\s+and\s+", author_field) if p.strip()]) - 1
    if api_author_count is not None and api_author_count <= 6:
        out.append(
            Finding(
                P3_METADATA,
                key,
                f"'and others' hides authors on a {api_author_count}-author paper",
                f"entry lists {listed}, the registry record has {api_author_count} — "
                "there is nothing to abbreviate",
                "spell out the full author list from the canonical record",
            )
        )
    else:
        out.append(
            Finding(
                P3_METADATA,
                key,
                "'and others' truncates the author list",
                f"entry lists {listed} author(s) explicitly",
                "valid BibTeX, but prefer the full list as printed on the paper",
            )
        )
    return out


def generation_signal(and_others_keys: list[str], total: int) -> Finding | None:
    """Corpus-level tell: 'and others' recurring across many entries.

    One abbreviated author list is a style choice. The same abbreviation across
    several entries, especially in a list that is otherwise inconsistent, is a
    signal the bibliography was generated rather than collected -- which is a
    reason to scrutinise every entry, not just these ones. Reported once, at P3,
    as a pointer rather than an accusation.
    """
    if len(and_others_keys) < 2:
        return None
    shown = ", ".join(and_others_keys[:8]) + ("..." if len(and_others_keys) > 8 else "")
    return Finding(
        P3_METADATA,
        "(whole bibliography)",
        f"{len(and_others_keys)} of {total} entries abbreviate authors with 'and others'",
        f"entries: {shown}\nA short listed prefix plus 'and others' repeated across a "
        "bibliography is a machine-generation pattern, not a typing habit.",
        "treat the whole reference list as unverified: check every identifier, not just these",
    )
