"""Turn a PDF-extracted reference list into clean reference strings.

Pure text processing, no network. Split out from ``resolve_refs.py`` because
every hard-won rule here came from a real extraction failure that produced a
FALSE fabrication finding -- bad parsing manufactures accusations rather than
hiding problems, so these functions are the part worth reading first.

Pipeline: strip margin line numbers -> strip repeated page furniture ->
detect the list-marker style -> group lines into references -> dewrap each,
healing identifiers broken across the wrap.
"""

import re

from bibmeta import norm_text

# DOIs as printed in reference lists, with or without a resolver prefix.
DOI_RE = re.compile(r"\b(?:https?://(?:dx\.)?doi\.org/|doi:\s*)?(10\.\d{4,9}/[^\s,;)\]]+)", re.I)
# arXiv:2301.00001 / arXiv:2301.00001v2 / arXiv preprint arXiv:cs/0501001
ARXIV_RE = re.compile(r"arxiv[:\s]+((?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?)", re.I)
YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
# Leading list markers to strip: "[12]", "(3)", "12." -- the bare-number form
# requires a space then a letter after the period, so a wrapped numeric
# fragment ("017.2762307" continuing a DOI) is never mistaken for a marker.
# LETTER matches any Unicode letter. Plain [A-Za-z] silently breaks on the
# first author whose surname starts outside ASCII -- "13. Şimşek, F.F.: ..."
# fails to register as a marker and the whole reference merges into the
# previous one. Non-ASCII surnames are common in this literature.
LETTER = r"[^\W\d_]"
NUMBER_PREFIX_RE = re.compile(rf"^\s*(?:\[\d+\]|\(\d+\)|\d{{1,3}}\.(?=\s+{LETTER}))\s*")
# Candidate marker styles, most to least specific. Whichever one a reference
# list actually uses becomes the ONLY thing that starts a new entry -- see
# detect_marker.
MARKER_STYLES = (
    re.compile(r"^\s*\[\d+\]"),
    re.compile(r"^\s*\(\d+\)"),
    re.compile(rf"^\s*\d{{1,3}}\.\s+(?={LETTER})"),
)
# Lines that are nothing but digits and space: runs of margin line numbers,
# which pdftotext emits on their own lines in non-layout mode.
NUMERIC_ONLY_RE = re.compile(r"^[\s\d]+$")


def detect_marker(lines: list[str]) -> re.Pattern[str] | None:
    """Identify the list-marker style a reference list uses, if any.

    Marker style is *sticky*: once a list is known to number its entries
    ``[1]``, ``[2]``, ..., only a marker may start a new reference. Without
    this, a plain-prose heuristic ("a line beginning Surname, ...") splits
    entries mid-author-list -- "Huy V." / "Vo, Marc Sbai, ..." is one author
    name across a line wrap, and splitting there strands the real first author
    in the previous fragment, which then reads as a fabricated identifier.
    False fabrication findings are the worst output this tool can produce, so
    the heuristic is only allowed to run on lists with no markers at all.

    Candidate markers must also look like an *enumeration*: starting near 1 and
    mostly ascending. Without that test, wrapped continuation lines opening
    with a parenthesised year ("(2021) pp. 1016--1022") pass as ``(N)`` markers
    and swallow the whole list into a handful of giant merged entries.
    """
    for pattern in MARKER_STYLES:
        nums: list[int] = []
        for ln in lines:
            m = pattern.match(ln)
            if m and (d := re.search(r"\d+", m.group(0))):
                nums.append(int(d.group(0)))
        if len(nums) < 3 or nums[0] > 3:
            continue
        ascending = sum(1 for a, b in zip(nums, nums[1:]) if b > a)
        if ascending >= 0.8 * (len(nums) - 1):
            return pattern
    return None
# A line ending part-way through a DOI, arXiv id, or URL. pdftotext hard-wraps
# mid-token, so "doi:10.1109/MGRS.2\n017.2762307" must rejoin with NO space --
# joining with one truncates the DOI and the entry gets falsely reported as
# fabricated, which is the most damaging mistake this tool can make.
IDENT_TAIL_RE = re.compile(r"(?:10\.\d{4,9}/|arxiv[:\s]*|https?://)\S*$", re.I)


# Papers under review usually print line numbers in the margin, which
# pdftotext interleaves with the text: "279   References   279" (both margins)
# or "279   References" (left only). Unstripped, the leading number reads as a
# reference marker and the trailing one corrupts the reference string.
LINENO_PAIRED_RE = re.compile(r"^\s*(\d{1,4})\s+(.*?)\s+\1\s*$")
LINENO_LEAD_RE = re.compile(r"^\s*(\d{1,4})\s{2,}(\S.*)$")


def strip_line_numbers(text: str) -> str:
    """Remove review line numbers from extracted PDF text, if present.

    Detected rather than assumed: paired numbers must match on both margins,
    and leading-only numbers must run mostly consecutively (which a genuine
    ``12.`` reference marker does not, and which also requires no period after
    the digits). Returns the text unchanged when neither pattern holds.
    """
    lines = text.splitlines()
    nonblank = [ln for ln in lines if ln.strip()]
    if not nonblank:
        return text

    paired = [ln for ln in nonblank if LINENO_PAIRED_RE.match(ln)]
    if len(paired) >= 0.4 * len(nonblank):
        return "\n".join(
            LINENO_PAIRED_RE.sub(r"\2", ln) if LINENO_PAIRED_RE.match(ln) else ln for ln in lines
        )

    nums = [
        int(m.group(1)) for ln in nonblank if (m := LINENO_LEAD_RE.match(ln)) is not None
    ]
    if len(nums) >= 0.4 * len(nonblank) and len(nums) > 2:
        consecutive = sum(1 for a, b in zip(nums, nums[1:]) if b == a + 1)
        if consecutive >= 0.5 * (len(nums) - 1):
            return "\n".join(
                LINENO_LEAD_RE.sub(r"\2", ln) if LINENO_LEAD_RE.match(ln) else ln for ln in lines
            )
    return text


def strip_repeated_lines(text: str) -> str:
    """Remove running headers and footers, which repeat on every page.

    Must happen BEFORE references are grouped, not after. A header landing in
    the middle of a reference gets joined into it by ``dewrap`` and then cannot
    be told from the citation's own text -- observed splicing a venue header
    into the middle of a title ("...mission for <Venue> 2026 Submission #NNNN...
    GMES operational services"), which collapsed the title match and escalated
    a perfectly good reference to a fabrication finding. It also duplicates and
    corrupts DOIs when it interrupts one mid-string.

    A line repeated three or more times that is short enough to be furniture is
    dropped; real references do not recur.
    """
    lines = text.splitlines()
    counts: dict[str, int] = {}
    for ln in lines:
        key = norm_text(ln)
        if key:
            counts[key] = counts.get(key, 0) + 1
    return "\n".join(
        ln
        for ln in lines
        if not (norm_text(ln) and counts[norm_text(ln)] >= 3 and len(ln.strip()) < 120)
    )


# Grey literature: datasets, standards, agency reports, web resources. These are
# legitimately absent from Crossref/arXiv/OpenAlex, so "not found" says nothing
# about whether they exist. Reporting them alongside possibly-invented papers
# inflates the top tier with citations that were never indexable -- in testing,
# 13 of 17 "not found" references were of this kind (national mapping agencies,
# IPCC guidelines, ESA validation reports, NOAA atlases, NASA datasets).
# Only markers that cannot plausibly appear in a PAPER TITLE. Words like
# "dataset", "atlas", "guidelines" and "standard" are common in real titles --
# "<Name>: A Global Dataset of ..." is a conference paper, not grey
# literature -- and matching them misfiled a genuine reference, under-ranking a
# candidate that deserved human attention. Access phrasing, deliverable
# nomenclature and version strings do not occur in titles.
GREY_MARKERS_RE = re.compile(
    r"(?i)(\baccessed\b|\bavailable at\b|\bretrieved\b|\bonline at\b|"
    r"\btechnical (?:report|note)\b|\bvalidation report\b|\bdeliverable\b|"
    r"\buser manual\b|\bversion \d|github\.com|\bURL\b)"
)
# An organisational author: the reference opens with a name-like run terminated by
# a colon, but with no "Surname, I." personal-name shape anywhere in it.
ORG_AUTHOR_RE = re.compile(r"^([^:]{3,80}):\s")
PERSONAL_NAME_RE = re.compile(rf"{LETTER}[{LETTER[1:-1]}'\-]+,\s*{LETTER}\.")


def is_grey_literature(ref: str) -> bool:
    """True if a reference points at something DOI registries do not index."""
    if GREY_MARKERS_RE.search(ref):
        return True
    if re.search(r"https?://|www\.", ref) and not DOI_RE.search(ref):
        return True
    org = ORG_AUTHOR_RE.match(ref)
    return bool(org and not PERSONAL_NAME_RE.search(org.group(1)))


def dewrap(lines: list[str]) -> str:
    """Join wrapped lines of one reference, healing split identifiers.

    Three join rules, in order: de-hyphenate an end-of-line hyphen; close up
    with no space when the previous line ends mid-identifier and the next
    continues with a lowercase letter or digit; otherwise join with a space.
    """
    out = ""
    for line in lines:
        piece = line.strip()
        if not piece:
            continue
        if not out:
            out = piece
        elif IDENT_TAIL_RE.search(out):
            # Inside an identifier: join with nothing and KEEP any trailing
            # hyphen -- it is part of the DOI. De-hyphenating here silently
            # corrupts DOIs that wrap after a hyphen ("10.1038/s41597-" +
            # "026-07099-1" became s41597026-07099-1, reported as fabricated).
            out += piece if re.match(r"^[a-z0-9]", piece) else " " + piece
        elif re.search(r"\w-$", out):
            out = out[:-1] + piece
        else:
            out += " " + piece
    return out


def split_references(text: str) -> list[str]:
    """Split reference-list text into one string per reference.

    Handles both one-per-line and blank-line-separated blocks. A wrapped
    reference is joined when the following line does not start a new numbered
    entry; identifiers broken across the wrap are healed by ``dewrap``.
    """
    text = strip_repeated_lines(strip_line_numbers(text))
    # Drop standalone runs of margin line numbers, keeping blank lines (they
    # carry entry-boundary information for unmarked lists). A numeric-only line
    # is NOT furniture when the previous line ends mid-identifier: a DOI wrapping
    # after its final period leaves its tail alone on the next line
    # ("...TNNLS.2022." / "3152527"), indistinguishable from a line number by
    # shape alone. Dropping it truncated a live DOI into a dead one.
    lines: list[str] = []
    for ln in text.splitlines():
        if ln.strip() and NUMERIC_ONLY_RE.match(ln):
            prev = next((p for p in reversed(lines) if p.strip()), "").strip()
            # Keep the line only when the identifier above it is visibly
            # UNFINISHED -- ending in "." or "-" or "/". A DOI ending in an
            # alphanumeric ("...essd-15-5491-2023") is plausibly complete, and
            # gluing the next margin number onto it invents a dead DOI; a DOI
            # ending in a separator ("...TNNLS.2022.") is mid-token, and
            # dropping its tail truncates a live one. Both mistakes report a
            # real paper as fabricated, from opposite directions.
            if not (IDENT_TAIL_RE.search(prev) and prev.endswith((".", "-", "/"))):
                continue
        lines.append(ln)
    marker = detect_marker(lines)

    groups: list[list[str]] = []
    after_blank = True
    for line in lines:
        if not line.strip():
            after_blank = True
            continue
        if marker is not None:
            # Marked list: only a marker starts an entry. Blank lines and
            # author-name line wraps are then harmless, and anything before
            # the first marker (leftover heading text) is skipped.
            starts_entry = bool(marker.match(line))
            if not groups and not starts_entry:
                continue
        else:
            stripped_line = line.strip()
            # "Surname, " opening a line -- Unicode-aware, so "Şimşek, F." and
            # "Gonçalves, A." count the same as ASCII surnames.
            looks_like_author = bool(
                re.match(rf"^{LETTER}[{LETTER[1:-1]}'\-]+,\s", stripped_line)
            ) and stripped_line[:1].isupper()
            starts_entry = after_blank or looks_like_author
            # A previous line ending mid-identifier plus a next line opening
            # with a digit or lowercase letter is a wrap, not a new entry --
            # the same discriminator dewrap uses. Also survives a page break
            # landing inside a DOI, hence outranking the blank-line rule.
            if (
                groups
                and IDENT_TAIL_RE.search(groups[-1][-1].strip())
                and re.match(r"^[a-z0-9]", line.strip())
            ):
                starts_entry = False
        after_blank = False
        if groups and not starts_entry:
            groups[-1].append(line)
        else:
            groups.append([line])

    candidates: list[str] = []
    for group in groups:
        cleaned = NUMBER_PREFIX_RE.sub("", dewrap(group)).strip()
        # Skip section headers and obvious page furniture.
        if len(cleaned) < 25 or re.fullmatch(r"(?i)references?|bibliography", cleaned):
            continue
        candidates.append(cleaned)

    # Running headers and footers ("<Venue> 2026 Submission #NNNN") repeat on
    # every page; a real reference appears once. Anything showing up three or
    # more times is furniture, not a citation.
    counts: dict[str, int] = {}
    for c in candidates:
        counts[norm_text(c)] = counts.get(norm_text(c), 0) + 1
    return [c for c in candidates if counts[norm_text(c)] < 3]


def printed_doi(ref: str) -> str | None:
    """The DOI printed in a reference, if any.

    When a reference carries several DOI-shaped strings -- which happens when a
    page break corrupts one copy and leaves another intact -- prefer the longest
    match. A DOI truncated or de-hyphenated by extraction is always shorter than
    the real one, and picking the mangled copy reports a live paper as fake.
    """
    found = [m.group(1).rstrip(".,;") for m in DOI_RE.finditer(ref)]
    return max(found, key=len) if found else None


def printed_arxiv(ref: str) -> str | None:
    m = ARXIV_RE.search(ref)
    return re.sub(r"v\d+$", "", m.group(1)) if m else None


def _namelike(chunk: str) -> bool:
    """True if a chunk reads as a run of author names rather than prose.

    Names are almost all capitalised words and bare initials; a title carries
    lowercase function words ("for", "with", "of").
    """
    words = [w for w in re.findall(r"\S+", chunk) if w.lower() not in {"and", "et", "al."}]
    if not words:
        return False
    namelike = sum(
        1 for w in words if re.match(rf"^{LETTER}", w) and w[:1].isupper() or re.fullmatch(r"\w\.", w)
    )
    return namelike / len(words) >= 0.8


def guess_title(ref: str) -> str:
    """Best-effort title for a title search.

    Reference lists use two incompatible author styles and the extractor has to
    handle both, because leaving the author block in the query measurably
    degrades Crossref's top hit -- enough to make famous papers (U-Net, Tent)
    look unfindable, which then reads as "invented":

    * ``Ronneberger, O., Fischer, P., Brox, T.: Title`` (surname-first)
    * ``Olaf Ronneberger, Philipp Fischer, and Thomas Brox. Title`` (given-first)

    The given-first form is the one a surname-first regex silently misses.
    Strategy: cut at the delimiter that ends the author block -- a colon, or the
    first sentence-ending period that follows an author-list-looking run.
    """
    stripped = re.sub(r"https?://\S+", "", ref)
    stripped = DOI_RE.sub("", stripped)
    stripped = re.sub(r"(?i)\barxiv[:\s]+\S+", "", stripped)

    # CVPR-style reference lists append the pages where the work was cited
    # ("... 2023. 1, 3, 4, 5"); that trailing run is not part of the title.
    stripped = re.sub(r"[.,]\s*\d+(?:\s*,\s*\d+)*\s*$", "", stripped)

    # Surname-first lists usually end the author block with a colon -- but so
    # does a title with a subtitle ("DINOv2: Learning Robust ..."), so only cut
    # there when what precedes the colon actually looks like a list of names.
    # Cap generously: a 19-author surname-first block runs past 300 chars, and a
# too-tight bound silently skips title extraction on exactly the entries
# whose long author lists most need it.
    colon = re.match(r"^([^:]{5,400}):\s+(?=\S)", stripped)
    if colon and len(stripped) - colon.end() > 20 and _namelike(colon.group(1)):
        stripped = stripped[colon.end() :]
    else:
        # Given-first lists end it at the period after the last name. Walk
        # sentence boundaries and drop leading chunks that look like names
        # (mostly capitalised words and initials, no lowercase function words).
        parts = re.split(r"(?<=\.)\s+", stripped, maxsplit=4)
        while len(parts) > 1 and _namelike(parts[0]) and len(" ".join(parts[1:])) > 20:
            parts = parts[1:]
        stripped = " ".join(parts)

    stripped = re.sub(r"^\s*\(?\d{4}\)?[.,]?\s*", "", stripped)
    # Keep only up to the first sentence end: past that is venue and pages.
    stripped = re.split(r"(?<=[a-z0-9])\.\s+[A-Z]", stripped, maxsplit=1)[0]
    return " ".join(stripped.split())[:300]


# Double-blind submissions anonymize their own prior work ("Anonymous. Title.
# Under review."). Those references carry no author or venue to check, so an
# author comparison against them ALWAYS fails -- reporting that as a fabricated
# identifier accuses authors of misconduct for following the review process.
ANONYMIZED_RE = re.compile(
    r"(?i)\b(anonymous|anonymized|under review|submitted to|in submission|blind review)\b"
)


def is_anonymized(ref: str) -> bool:
    return bool(ANONYMIZED_RE.search(ref))


