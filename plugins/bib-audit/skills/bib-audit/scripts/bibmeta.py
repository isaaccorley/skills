"""Shared metadata layer: LaTeX-aware normalization + Crossref/arXiv resolution.

Imported by ``validate_refs.py`` (structured .bib input) and ``resolve_refs.py``
(raw reference strings lifted out of a PDF or pasted bibliography). Keeping one
copy of the name/title comparison rules means both entry points agree on what
counts as a match.

Stdlib only.
"""

import difflib
import html
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

CROSSREF_WORKS = "https://api.crossref.org/works"
ARXIV_API = "https://export.arxiv.org/api/query"
DOI_NEGOTIATE = "https://doi.org/{doi}"
ARXIV_NS = {"a": "http://www.w3.org/2005/Atom"}

# Title similarity below which we refuse to bind a title-search hit to an entry.
TITLE_ACCEPT_RATIO = 0.85
# Title similarity below which a DOI/arXiv-resolved entry is flagged as a
# title mismatch (looser, because the identifier already pins the work).
TITLE_MATCH_RATIO = 0.90


def default_mailto() -> str:
    """Contact address for Crossref's polite pool; empty = anonymous."""
    return os.environ.get("BIB_AUDIT_MAILTO", "")


def s2_api_key() -> str:
    """Semantic Scholar key, from the environment only.

    Read from ``S2_API_KEY`` and never accepted as a command-line flag, so it
    cannot end up in shell history, a process listing, or a pasted command in an
    issue. Optional: the endpoints used here work unauthenticated, just with a
    much lower rate limit and (observed during development) long stretches of
    HTTP 500. Request one at https://www.semanticscholar.org/product/api.
    """
    return os.environ.get("S2_API_KEY", "").strip()


@dataclass
class Record:
    """Authoritative metadata for one work."""

    source: str
    title: str
    families: list[str]
    year: str | None
    doi: str | None = None
    # All years the registrar deposited (published-print, published-online,
    # issued, ...). Publishers register both an online-first and a print-issue
    # date; a bib citing either year is correct.
    years: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    # Crossref's work `type` ("journal-article", "dissertation", "book-chapter",
    # ...) and container title. Both exist to catch wrong title-search binds: a
    # reference to a conference paper that lands on a dissertation is wrong no
    # matter how well the titles score, and the type says so in one field.
    ctype: str = ""
    venue: str = ""


# Letters that do NOT decompose under NFKD. Without an explicit mapping they
# survive normalization, then norm_text's [^0-9a-zA-Z] rule turns them into WORD
# SEPARATORS -- so family_key("Rußwurm") returned "wurm" and family_key("Straße")
# returned "e". Self-consistent only while both sides spell the name identically,
# which fails the moment one transliterates, and transliterating is normal (the
# same author publishes as "Russwurm" on arXiv).
_TRANSLIT = {
    "ß": "ss", "ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D",
    "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "þ": "th", "Þ": "TH",
    "ð": "d", "Ð": "D", "ı": "i", "ĸ": "k", "ŋ": "ng",
}
# German/Nordic convention EXPANDS umlauts (ä->ae) where plain accent-stripping
# COLLAPSES them (ä->a). Both spellings occur in real bibliographies, so names
# are compared under both foldings and a match on either counts.
_EXPAND = {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "å": "aa", "Å": "Aa"}


def strip_accents(text: str) -> str:
    """Fold to ASCII, mapping non-decomposing letters instead of dropping them."""
    for src, dst in _TRANSLIT.items():
        text = text.replace(src, dst)
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def expand_diacritics(text: str) -> str:
    """The alternate folding: ä->ae rather than ä->a."""
    for src, dst in _EXPAND.items():
        text = text.replace(src, dst)
    return strip_accents(text)


# Standalone LaTeX glyph macros -> ASCII (\ss, \o, \aa, ...).
_LATEX_GLYPHS = {
    r"\ss": "ss",
    r"\o": "o",
    r"\O": "O",
    r"\l": "l",
    r"\L": "L",
    r"\aa": "a",
    r"\AA": "A",
    r"\ae": "ae",
    r"\AE": "AE",
    r"\oe": "oe",
    r"\OE": "OE",
    r"\i": "i",
    r"\j": "j",
}


def delatex(text: str) -> str:
    r"""Decode LaTeX accent macros to their base letter.

    Handles ``{\"a}``/``\"a``/``\"{a}`` (accent over a letter) and
    ``\c{c}``/``{\c c}`` (named-accent forms) so e.g. ``H{\"a}nsch``
    compares equal to the Unicode ``Hänsch`` that Crossref returns.
    """
    # \"a  \'e  \`a  \^o  \~n  \=a  \.a  -- accent symbol over one letter.
    text = re.sub(r"\\[\"\'`^~=.]\s*\{?(\w)\}?", r"\1", text)
    # \c{c}  \v{s}  \u{g}  \H{o}  -- named accent, braced argument.
    text = re.sub(r"\\[a-zA-Z]+\{(\w)\}", r"\1", text)
    # {\c c}  {\v s}  -- named accent, spaced argument.
    text = re.sub(r"\\[a-zA-Z]+\s+(\w)", r"\1", text)
    for macro, repl in _LATEX_GLYPHS.items():
        text = text.replace(macro, repl)
    return text


def norm_text(text: str) -> str:
    """Lowercase, decode LaTeX and markup, drop braces/accents/punctuation."""
    # Some publishers deposit escaped markup in the title itself (SPIE deposits
    # "&lt;title&gt;On seeing stuff&lt;/title&gt;"). Left in, the junk inflates the
    # denominator of any coverage test and a fully-present title reads as a
    # mismatch. Unescape, then strip tags.
    text = html.unescape(text)
    text = re.sub(r"<[^>]{1,40}>", " ", text)
    text = strip_accents(delatex(text).replace("{", "").replace("}", ""))
    text = re.sub(r"[^0-9a-zA-Z]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def title_ratio(a: str, b: str) -> float:
    """Similarity of two titles after normalization."""
    return difflib.SequenceMatcher(None, norm_text(a), norm_text(b)).ratio()


def squash(text: str) -> str:
    """Normalize and remove ALL separators, for hyphen-blind containment tests.

    PDF extraction cannot reliably tell a soft hyphen (inserted by justification
    at a line break) from a hard one (part of a real compound). De-hyphenating a
    wrap turns "remote sensing-based" into "remote sensingbased", after which a
    plain containment test against the registrar's title fails and a correctly
    cited paper is reported as fabricated. Comparing with every space and hyphen
    removed makes all three spellings equal.
    """
    return norm_text(text).replace(" ", "")



def title_coverage(api_title: str, reference: str) -> float:
    """How much of the registrar's title is present in the reference string.

    This is the right shape for the question "does this reference cite the work
    the identifier names?", and it needs NO title extraction from the reference.
    That matters: every attempt to scrape a title out of a raw reference is a
    heuristic that fails on real input -- it dropped the one disambiguating token
    ("U-Net:"), gave up on a 19-author block, and reduced a title to its subtitle
    -- and each failure fed a FALSE fabrication verdict. The API already supplies
    the authoritative title, so the reference only ever needs to be searched, not
    parsed.

    Returns matched characters / length of the API title, in [0, 1], comparing
    with separators removed so hyphenation damage does not count against it.
    """
    needle, hay = squash(api_title), squash(reference)
    if not needle:
        return 0.0
    matcher = difflib.SequenceMatcher(None, needle, hay, autojunk=False)
    return sum(block.size for block in matcher.get_matching_blocks()) / len(needle)


def family_keys(name: str) -> set[str]:
    """All plausible comparison keys for one author name.

    Returns both diacritic foldings and, for a multi-word surname, the full
    normalized surname as well as its last token. Callers should count a match on
    ANY key: "Riquelme Ruiz" keyed only on "ruiz" read as a different person from
    "Riquelme, Carlos", which surfaced as an invented author on a correct entry.
    """
    keys: set[str] = set()
    for fold in (strip_accents, expand_diacritics):
        raw = delatex(name).replace("{", "").replace("}", "").strip()
        if "," in raw:
            candidates = [raw.split(",", 1)[0]]
        else:
            # "Given Family" — the surname may be more than the last token
            # ("Carlos Riquelme Ruiz"), and which part the other source recorded
            # as the family name is not knowable. Offer the trailing one and two
            # tokens, and each of them alone, so a match on any counts.
            toks = raw.split()
            candidates = [raw] if len(toks) == 1 else [
                toks[-1], " ".join(toks[-2:]), toks[-2]
            ]
        for cand in candidates:
            norm = re.sub(r"\s+", " ", re.sub(r"[^0-9a-zA-Z]+", " ", fold(cand).lower())).strip()
            if not norm:
                continue
            keys.add(norm)                      # surname, spaces collapsed
            keys.add(norm.replace(" ", ""))     # joined: Solar-Lezama/SolarLezama
            keys.add(norm.split(" ")[-1])       # last token (historical behaviour)
    return {k for k in keys if len(k) > 1}


def family_key(name: str) -> str:
    r"""Reduce an author name to its comparison key: last surname token.

    Handles ``Family, Given``, ``Given Family``, and multi-word surnames
    (``van der Berg`` -> ``berg``) so the same author keys identically
    whether it comes from the .bib, Crossref, or arXiv.

    LaTeX accents must be decoded *before* braces are stripped: otherwise the
    nested-brace form ``Gon{\c{c}}alves`` degrades to ``Gon\ccalves`` and the
    accent macro can no longer be recognized (keys as ``ccalves``).
    """
    name = delatex(name).replace("{", "").replace("}", "").strip()
    if "," in name:
        surname = name.split(",", 1)[0]
    else:
        surname = name.rsplit(" ", 1)[-1] if " " in name else name
    norm = norm_text(surname)
    return norm.split(" ")[-1] if norm else ""


class LookupUnavailable(Exception):
    """A lookup could not be completed: rate limit, outage, timeout.

    Deliberately distinct from "the identifier resolves to nothing". Callers
    MUST NOT fold this into a fabricated/not-found verdict — a 429 reported as
    "may be invented" is a false accusation caused by our own request rate.
    """


# Retried rather than surfaced: Crossref rate-limits (429) and both APIs return
# 503 under load. A few hundred references is enough to hit this routinely.
RETRY_STATUS = {429, 500, 502, 503, 504}


def http_get(
    url: str, accept: str, mailto: str, timeout: float = 12.0, retries: int = 2
) -> str:
    """GET with a SHORT retry budget.

    Deliberately impatient. The goal is to flag what could not be checked so a
    human follows up, not to guarantee an answer for every reference: a long
    exponential backoff multiplied by three sources and a few hundred references
    turns a 2-minute audit into an afternoon. One quick retry, then give up and
    let the caller report the reference as unchecked.
    """
    agent = "bib-audit/1.0"
    if mailto:
        agent += f" (mailto:{mailto})"
    headers = {"Accept": accept, "User-Agent": agent}
    # Only Semantic Scholar takes a key, and sending it anywhere else would leak
    # it to Crossref/arXiv/OpenAlex logs for no benefit.
    if "semanticscholar.org" in url and (key := s2_api_key()):
        headers["x-api-key"] = key
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRY_STATUS:
                raise  # 404 and friends are real answers; let callers see them
            if attempt == retries - 1:
                raise LookupUnavailable(f"HTTP {exc.code} after {retries} attempts") from exc
            # Honour Retry-After when the server sends it, else back off.
            # Cap the wait low: honouring a 60s Retry-After per reference is how
            # an audit stops being usable. Better to flag and move on.
            wait = 1.0 * (attempt + 1)
            after = exc.headers.get("Retry-After") if exc.headers else None
            if after and after.strip().isdigit():
                wait = min(max(wait, float(after.strip())), 3.0)
            time.sleep(wait)
        except (TimeoutError, urllib.error.URLError, OSError) as exc:
            # BrokenPipeError/ConnectionResetError are bare OSError, not
            # URLError. Uncaught, one reset killed a 332-entry run at
            # entry 138 and lost every verdict already computed.
            if attempt == retries - 1:
                raise LookupUnavailable(str(exc)) from exc
            time.sleep(1.0)
    raise LookupUnavailable("unreachable")


def crossref_to_record(msg: dict, source: str) -> Record:
    titles = msg.get("title") or [""]
    authors = msg.get("author") or []
    families = [family_key(a["family"]) for a in authors if a.get("family")]
    years: list[str] = []
    for key in ("published", "published-print", "published-online", "issued"):
        parts = msg.get(key, {}).get("date-parts")
        if parts and parts[0] and parts[0][0]:
            y = str(parts[0][0])
            if y not in years:
                years.append(y)
    return Record(
        source=source,
        title=titles[0],
        families=families,
        year=years[0] if years else None,
        doi=msg.get("DOI"),
        years=years,
        ctype=(msg.get("type") or "").strip().lower(),
        venue=next(iter(msg.get("container-title") or []), ""),
    )


def crossref_by_doi(doi: str, mailto: str) -> Record:
    url = f"{CROSSREF_WORKS}/{urllib.parse.quote(doi)}"
    msg = json.loads(http_get(url, "application/json", mailto))["message"]
    return crossref_to_record(msg, source="crossref:doi")


def crossref_search(title: str, mailto: str, accept_ratio: float = TITLE_ACCEPT_RATIO) -> Record | None:
    """Bind a title (or a whole raw reference string) to a Crossref work.

    Returns None when the top hit isn't a close enough title match, so we never
    silently bind an entry to the wrong paper.
    """
    params = urllib.parse.urlencode({"query.bibliographic": title, "rows": "1"})
    items = json.loads(http_get(f"{CROSSREF_WORKS}?{params}", "application/json", mailto))[
        "message"
    ]["items"]
    if not items:
        return None
    rec = crossref_to_record(items[0], source="crossref:search")
    if title_ratio(title, rec.title) < accept_ratio:
        return None
    return rec


def crossref_candidates(query: str, mailto: str, rows: int = 3) -> list[Record]:
    """Top-N Crossref hits, unfiltered — for advisory display, not binding."""
    params = urllib.parse.urlencode({"query.bibliographic": query, "rows": str(rows)})
    items = json.loads(http_get(f"{CROSSREF_WORKS}?{params}", "application/json", mailto))[
        "message"
    ]["items"]
    return [crossref_to_record(it, source="crossref:search") for it in items]


def arxiv_by_id(arxiv_id: str, mailto: str) -> Record | None:
    params = urllib.parse.urlencode({"id_list": arxiv_id})
    xml_text = http_get(f"{ARXIV_API}?{params}", "application/atom+xml", mailto)
    entry = ET.fromstring(xml_text).find("a:entry", ARXIV_NS)
    if entry is None:
        return None
    title_el = entry.find("a:title", ARXIV_NS)
    title = (title_el.text or "").strip() if title_el is not None else ""
    # A well-formed but nonexistent id returns totalResults=0 and no entry at
    # all (handled above); a *malformed* id returns one entry titled "Error".
    # Both mean "this identifier names no paper" -> let the caller call it
    # fabricated rather than reporting a title mismatch against "Error".
    if not title or title == "Error":
        return None
    families: list[str] = []
    for author in entry.findall("a:author", ARXIV_NS):
        name_el = author.find("a:name", ARXIV_NS)
        if name_el is not None and name_el.text:
            families.append(family_key(name_el.text))
    published = entry.find("a:published", ARXIV_NS)
    year = published.text[:4] if published is not None and published.text else None
    return Record(
        source="arxiv",
        title=title,
        families=families,
        year=year,
        years=[year] if year else [],
    )


S2_BATCH = "https://api.semanticscholar.org/graph/v1/paper/batch"


def s2_batch(ids: list[str], mailto: str) -> list[dict | None]:
    """Look up many papers in ONE request. Returns results in request order.

    ``ids`` are prefixed identifiers: ``DOI:10.1109/...``, ``ARXIV:1711.05101``.
    A ``None`` in the returned list means that identifier names no paper — which
    is the fabricated-identifier signal, obtained for the whole bibliography in a
    single round trip instead of one request per reference.

    Accepts up to 500 ids per call. Family names in the response are reliable;
    TITLES ARE NOT — S2 serves v1 preprint titles (it returns "Fixing Weight
    Decay Regularization in Adam" for the work published as "Decoupled Weight
    Decay Regularization"), so treat a title disagreement here as a signal to
    re-check against the registrar, never as a finding on its own.
    """
    if not ids:
        return []
    body = json.dumps({"ids": ids}).encode()
    url = f"{S2_BATCH}?" + urllib.parse.urlencode(
        {"fields": "title,year,externalIds,authors"}
    )
    agent = "bib-audit/1.0" + (f" (mailto:{mailto})" if mailto else "")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": agent},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LookupUnavailable(f"S2 batch: {exc}") from exc
    if not isinstance(payload, list) or len(payload) != len(ids):
        raise LookupUnavailable("S2 batch returned an unexpected shape")
    return payload


def datacite_by_doi(doi: str, mailto: str) -> Record | None:
    """Resolve a DOI that Crossref does not hold.

    Crossref only carries DOIs registered through Crossref. Zenodo datasets
    (``10.5281/*``), figshare, Dryad and other DataCite registrants 404 there
    while being perfectly real — a Zenodo dataset DOI reported as "names no
    paper" is a false fabrication finding, and data-descriptor citations are
    common in exactly the remote-sensing papers this skill gets pointed at.
    """
    url = f"https://api.datacite.org/dois/{urllib.parse.quote(doi)}"
    try:
        attrs = json.loads(http_get(url, "application/json", mailto))["data"]["attributes"]
    except (urllib.error.HTTPError, KeyError, json.JSONDecodeError):
        return None
    titles = attrs.get("titles") or []
    title = (titles[0].get("title") if titles else "") or ""
    if not title:
        return None
    families = [
        family_key(c.get("familyName") or c.get("name") or "")
        for c in (attrs.get("creators") or [])
        if c.get("familyName") or c.get("name")
    ]
    year = str(attrs["publicationYear"]) if attrs.get("publicationYear") else None
    return Record(
        source="datacite:doi",
        title=title,
        families=[f for f in families if f],
        year=year,
        doi=doi,
        years=[year] if year else [],
    )


def arxiv_search_title(title: str, mailto: str) -> Record | None:
    """Find an arXiv record by title.

    Needed because a large share of ML references are arXiv-only preprints with
    no DOI: Crossref simply does not hold them, and treating a Crossref miss as
    "this paper does not exist" is how a real preprint gets called invented.
    """
    query = urllib.parse.urlencode(
        {"search_query": f'ti:"{title}"', "max_results": "1"}
    )
    xml_text = http_get(f"{ARXIV_API}?{query}", "application/atom+xml", mailto)
    entry = ET.fromstring(xml_text).find("a:entry", ARXIV_NS)
    if entry is None:
        return None
    title_el = entry.find("a:title", ARXIV_NS)
    found = " ".join((title_el.text or "").split()) if title_el is not None else ""
    if not found or found == "Error":
        return None
    if title_ratio(title, found) < TITLE_ACCEPT_RATIO:
        return None
    families = [
        family_key(n.text)
        for a in entry.findall("a:author", ARXIV_NS)
        if (n := a.find("a:name", ARXIV_NS)) is not None and n.text
    ]
    published = entry.find("a:published", ARXIV_NS)
    year = published.text[:4] if published is not None and published.text else None
    return Record(
        source="arxiv:search",
        title=found,
        families=families,
        year=year,
        years=[year] if year else [],
    )


def openalex_search(title: str, mailto: str) -> Record | None:
    """Find a work in OpenAlex — broadest coverage, includes preprints.

    Last resort before declaring a reference unfindable. A hit here on a paper
    Crossref and arXiv both missed still means the paper is real.
    """
    params = {"search": title, "per-page": "1"}
    if mailto:
        params["mailto"] = mailto
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    results = json.loads(http_get(url, "application/json", mailto)).get("results") or []
    if not results:
        return None
    work = results[0]
    found = work.get("display_name") or ""
    if not found or title_ratio(title, found) < TITLE_ACCEPT_RATIO:
        return None
    families = [
        family_key(a["author"]["display_name"])
        for a in work.get("authorships") or []
        if a.get("author", {}).get("display_name")
    ]
    year = str(work["publication_year"]) if work.get("publication_year") else None
    doi = (work.get("doi") or "").replace("https://doi.org/", "") or None
    return Record(
        source="openalex",
        title=found,
        families=families,
        year=year,
        doi=doi,
        years=[year] if year else [],
    )


def canonical_bibtex_from_doi(doi: str, key: str, mailto: str) -> str:
    """Publisher BibTeX via doi.org content negotiation, rekeyed to ``key``."""
    raw = http_get(DOI_NEGOTIATE.format(doi=doi), "application/x-bibtex", mailto).strip()
    return re.sub(r"^@(\w+)\s*\{[^,]+,", rf"@\1{{{key},", raw, count=1)
