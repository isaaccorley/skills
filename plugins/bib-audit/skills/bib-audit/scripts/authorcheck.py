"""Ordered, given-name-aware comparison of a bib author list with a registry record.

The family-name set comparison in ``validate_refs.compare`` is blind to three
error shapes that were found together in two real, submitted bibliographies:

* **Invented given names with the right initial.** An LLM working from an
  initials-only source (PubMed listings, Google Scholar, "Trombley N.") expands
  the initial into a plausible full name ("Nicole" for Nathan). Surnames still
  match, and an initials-only style (elsarticle-num, IEEE) prints "N. Trombley",
  so the error is invisible in the built PDF and in any proofread. Twenty-five
  such names across ten entries passed every earlier check.
* **Swapped author order.** Same surname set, different order.
* **Silent truncation.** A list that stops at 15 of 26 authors with no
  ``and others`` renders as a complete author list.

It also removes the noise that buried real findings: an ``and others`` entry
whose listed authors are the correct prefix of the registry list is correct,
deliberate abbreviation and is no longer reported as a count mismatch.

Stdlib only, no network.
"""

import re

from bibmeta import delatex, family_keys, strip_accents


def split_bib_name(name: str) -> tuple[str, str, bool]:
    """Return (given, family, corporate) for one BibTeX author name.

    A name wrapped whole in braces (``{ISARIC4C Investigators}``,
    ``{Institute for Disease Modeling}``) is a corporate author: registries
    either omit it or store it without a family name, so it takes no part in
    the positional comparison.
    """
    raw = name.strip()
    if raw.startswith("{") and raw.endswith("}") and raw.count("{") == 1:
        return "", raw[1:-1], True
    if "," in raw:
        family, given = raw.split(",", 1)
        return given.strip(), family.strip(), False
    toks = raw.split()
    if len(toks) == 1:
        return "", raw, False
    return " ".join(toks[:-1]), toks[-1], False


def given_token(given: str) -> str:
    """First given-name token, normalized; '' when absent."""
    text = strip_accents(delatex(given).replace("{", "").replace("}", "")).lower()
    for tok in re.split(r"[\s.\-]+", text):
        tok = re.sub(r"[^a-z]", "", tok)
        if tok:
            return tok
    return ""


def same_person(bib_family: str, api_family: str) -> bool:
    return bool(family_keys(bib_family) & family_keys(api_family))


def compare_authors(
    bib_names: list[str], has_others: bool, api: list[tuple[str, str]]
) -> tuple[list[tuple[str, str]], int]:
    """Compare a bib author list with registry ``(given, family)`` pairs in order.

    Returns ``(issues, same_initial_given_mismatches)``. Each issue is
    ``(kind, message)`` with kind in {author, given}. A message containing
    "invented?" names a person who is not on the registry record at all and is
    ranked P2 by the caller.
    """
    persons = [split_bib_name(n) for n in bib_names]
    persons = [(g, f) for g, f, corp in persons if not corp]
    api = [(g or "", f) for g, f in api if f]
    issues: list[tuple[str, str]] = []
    if not persons or not api:
        return issues, 0

    def label(given: str, family: str) -> str:
        return f"{delatex(given).replace('{', '').replace('}', '')} {delatex(family).replace('{', '').replace('}', '')}".strip()

    # Greedy in-order alignment; repeated surnames (two Robbins, two Li) pair
    # with the first unused registry author of that surname.
    used: set[int] = set()
    pairs: list[tuple[int, int]] = []
    extra: list[str] = []
    for bi, (_, bf) in enumerate(persons):
        match = next(
            (ai for ai, (_, af) in enumerate(api) if ai not in used and same_person(bf, af)),
            None,
        )
        if match is None:
            extra.append(label(*persons[bi]))
        else:
            used.add(match)
            pairs.append((bi, match))
    missing = [label(*api[ai]) for ai in range(len(api)) if ai not in used]

    # The registrar's list can itself be short: some deposits carry only the
    # first author (JAMA's 2002 Aiken et al. lists one of five). When every
    # registry author matches the bib's leading authors in order, the extra bib
    # names sit past the end of the deposit, so this is not evidence of
    # invention -- ask for the byline instead of ranking it P2.
    deposit_short = (
        extra and not missing and len(pairs) == len(api)
        and all(bi == ai for bi, ai in pairs)
    )
    if deposit_short:
        issues.append((
            "author",
            f"registry record lists only {len(api)} of the bib's {len(persons)} authors "
            f"(incomplete deposit?); confirm {extra} against the PDF byline",
        ))
    elif extra:
        issues.append(("author", f"authors NOT on the registry record (invented?): {extra}"))

    in_order = all(bi == ai for bi, ai in pairs)
    if has_others:
        if not in_order and not extra:
            first = next((bi, ai) for bi, ai in pairs if bi != ai)
            issues.append((
                "author",
                f"listed authors are not the registry's first {len(persons)} in order: "
                f"position {first[0] + 1} is {label(*persons[first[0]])}, "
                f"registry has {label(*api[first[0]])}" if first[0] < len(api) else
                "listed authors are not the registry's leading authors in order",
            ))
    else:
        if missing and not extra and in_order and len(pairs) == len(persons):
            issues.append((
                "author",
                f"list stops at {len(persons)} of {len(api)} authors with no 'and others', "
                f"so it renders as complete; missing {missing}",
            ))
        elif missing:
            issues.append(("author", f"authors on the registry record but not in bib: {missing}"))
        if not missing and not extra and not in_order:
            first = next(bi for bi, ai in pairs if bi != ai)
            issues.append((
                "author",
                f"author order differs from the registry from position {first + 1}: "
                f"bib {[label(*p) for p in persons[first:first + 3]]} vs "
                f"registry {[label(*a) for a in api[first:first + 3]]}",
            ))

    same_initial = 0
    for bi, ai in pairs:
        bg, ag = given_token(persons[bi][0]), given_token(api[ai][0])
        if len(bg) < 2 or len(ag) < 2 or bg == ag:
            continue
        if bg[0] == ag[0]:
            same_initial += 1
        issues.append((
            "given",
            f"given name differs: bib '{label(*persons[bi])}' vs registry '{label(*api[ai])}'"
            + (" (same initial: typical of a name expanded from initials)" if bg[0] == ag[0] else ""),
        ))
    return issues, same_initial
