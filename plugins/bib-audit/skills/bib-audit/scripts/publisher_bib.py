#!/usr/bin/env python3
"""Download the publisher's own citation export, convert it to BibTeX, compare it with a .bib entry.

  publisher_bib.py ID...                     print each export as BibTeX
  publisher_bib.py --bib FILE [--key K...]   compare every entry with a DOI or eprint
  publisher_bib.py --file EXPORT [--bib FILE --key K]
                                             convert (and compare) an export saved from the browser

ID is a DOI, a doi.org URL, or arXiv:<id>. Known export endpoints are tried first (Springer
Nature, BMC, and Springer; PLOS; Copernicus; arXiv), then the export links on the article's
landing page (Frontiers and others). BibTeX is preferred; otherwise whatever the publisher
offers is taken and converted: RIS, EndNote tagged (.enw), RefWorks tagged, PubMed/MEDLINE
(.nbib), or CSL-JSON. A plain-text citation is saved but not converted: it is free text, so
it is turned into BibTeX by reading it. Publishers behind a bot check (Elsevier, Wiley, NEJM,
PNAS, APS, OUP, IEEE, ACM, ...) answer 403; the script then takes the PubMed record (NLM's
MEDLINE file) as a secondary source when the work is in PubMed (--no-pubmed to skip), and
names the page whose "Cite" or "Export citation" button gives the publisher's file in a
browser.

The export is a second source, not the authority: exports carry their own errors (repeated
consortium members, PDF page ranges in place of article numbers, "Volume 12 - 2022").
Where the export, the registrar record, and the PDF byline disagree, the byline decides the
authors and the PDF the other fields. Standard library only; read-only except for --save.
"""

import argparse
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from bibmeta import default_mailto, norm_pages, norm_text

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
SPRINGER = ("10.1038/", "10.1007/", "10.1186/", "10.1140/", "10.1057/", "10.1365/")
CHALLENGE = re.compile(r"Just a moment|cf-chl|captcha|Access Denied|are you a robot", re.I)
EXT = {
    "BibTeX": "bib",
    "RIS": "ris",
    "EndNote": "enw",
    "RefWorks": "txt",
    "MEDLINE": "nbib",
    "CSL-JSON": "json",
    "plain text": "txt",
}
_last = {}


def http(url, accept="*/*", timeout=40):
    """GET url; returns (status or None, final url, text)."""
    host = urllib.parse.urlsplit(url).hostname or ""
    wait = 1.0 - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    agent = "bib-audit/1.0" + (f" (mailto:{default_mailto()})" if default_mailto() else "")
    req = urllib.request.Request(url, headers={"User-Agent": agent, "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            _last[host] = time.time()
            return r.status, r.geturl(), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        _last[host] = time.time()
        try:
            body = e.read().decode("utf-8", "replace")
        except (OSError, ValueError):
            body = ""
        return e.code, e.geturl() or url, body
    except (urllib.error.URLError, OSError) as e:
        return None, url, str(e)


def parse_id(s):
    s = s.strip()
    m = re.match(r"^(?:arxiv:|https?://arxiv\.org/abs/)(.+)$", s, re.I)
    if m:
        return "arxiv", re.sub(r"v\d+$", "", m.group(1))
    m = re.match(r"^(?:doi:|https?://(?:dx\.)?doi\.org/)?(10\.\S+)$", s, re.I)
    if m:
        d = m.group(1)
        a = re.match(r"10\.48550/arxiv\.(.+)$", d, re.I)
        return ("arxiv", a.group(1)) if a else ("doi", d)
    return None, s


# ---------------------------------------------------------------- text and names


def show(s):
    """A field value for display: braces removed, whitespace collapsed."""
    return re.sub(r"\s+", " ", (s or "").replace("{", "").replace("}", "")).strip()


def _balanced(text, i):
    depth = 0
    for j in range(i, len(text)):
        depth += (text[j] == "{") - (text[j] == "}")
        if depth == 0:
            return j
    return len(text) - 1


def parse_fields(body):
    fields, i, n = {}, 0, len(body)
    pat = re.compile(r"[\s,]*([A-Za-z][\w\-:.]*)\s*=\s*")
    while i < n:
        m = pat.match(body, i)
        if not m:
            break
        name, i = m.group(1).lower(), m.end()
        if i < n and body[i] == "{":
            j = _balanced(body, i)
            val, i = body[i + 1 : j], j + 1
        elif i < n and body[i] == '"':
            j, depth = i + 1, 0
            while j < n and not (body[j] == '"' and depth == 0):
                depth += (body[j] == "{") - (body[j] == "}")
                j += 1
            val, i = body[i + 1 : j], j + 1
        else:
            m2 = re.compile(r"[^,}\s]+").match(body, i)
            val, i = (m2.group(0), m2.end()) if m2 else ("", i + 1)
        fields[name] = re.sub(r"\s+", " ", val).strip()
    return fields


def parse_bib(text):
    out, i = [], 0
    while True:
        j = text.find("@", i)
        if j < 0:
            return out
        m = re.compile(r"@\s*([A-Za-z]+)\s*\{").match(text, j)
        if not m:
            i = j + 1
            continue
        end = _balanced(text, m.end() - 1)
        if m.group(1).lower() not in ("comment", "preamble", "string"):
            key, _, rest = text[m.end() : end].partition(",")
            out.append(dict(type=m.group(1).lower(), key=key.strip(), fields=parse_fields(rest)))
        i = end + 1


def split_names(s):
    out, depth, cur = [], 0, ""
    for t in re.split(r"(\{|\}|\s+and\s+)", s or ""):
        if t == "{":
            depth += 1
        elif t == "}":
            depth -= 1
        if t and re.fullmatch(r"\s+and\s+", t) and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += t or ""
    if cur.strip():
        out.append(cur.strip())
    return [n.strip(" ,") for n in out if n.strip(" ,")]


def name_split(raw):
    """(family key, given name); a braced or comma-less multi-word name is a group."""
    r = raw.strip()
    if is_group(r):
        return re.sub(r"^the ", "", norm_text(r)), ""
    if "," in r:
        parts = [x.strip() for x in r.split(",")]
        return norm_text(parts[0]), show(parts[-1])
    toks = show(r).split()
    return norm_text(toks[-1]), " ".join(toks[:-1])


# ---------------------------------------------------------------- export formats

RIS_TYPES = {
    "JOUR": "article",
    "JFULL": "article",
    "EJOUR": "article",
    "MGZN": "article",
    "NEWS": "article",
    "CONF": "inproceedings",
    "CPAPER": "inproceedings",
    "BOOK": "book",
    "EBOOK": "book",
    "EDBOOK": "book",
    "CHAP": "incollection",
    "ECHAP": "incollection",
    "RPRT": "techreport",
    "THES": "phdthesis",
}
CSL_TYPES = {
    "article-journal": "article",
    "journal-article": "article",
    "article": "article",
    "paper-conference": "inproceedings",
    "proceedings-article": "inproceedings",
    "book": "book",
    "monograph": "book",
    "chapter": "incollection",
    "book-chapter": "incollection",
    "report": "techreport",
    "thesis": "phdthesis",
    "dissertation": "phdthesis",
}


def word_type(s):
    s = (s or "").lower()
    for w, t in (
        ("journal", "article"),
        ("conference", "inproceedings"),
        ("proceedings", "inproceedings"),
        ("section", "incollection"),
        ("chapter", "incollection"),
        ("book", "book"),
        ("report", "techreport"),
        ("thesis", "phdthesis"),
    ):
        if w in s:
            return t
    return "article" if not s else "misc"


def tagged(text, pat):
    """[tag, value] pairs of a tagged format; indented lines continue the previous value."""
    out = []
    for line in text.splitlines():
        m = re.match(pat, line)
        if m:
            out.append([m.group(1).strip(), m.group(2).strip()])
        elif out and line[:1] == " " and line.strip():
            out[-1][1] += " " + line.strip()
    return out


def pages_of(p):
    return re.sub(r"\s*[-\u2013\u2014]+\s*", "--", (p or "").strip())


def year_of(s):
    m = re.search(r"\b(1[6-9]|20)\d\d\b", s or "")
    return m.group(0) if m else ""


def doi_of(s):
    m = re.search(r"10\.\d{4,9}/\S+?(?=\s*\[doi\]|\s|$)", s or "")
    return m.group(0).rstrip(".") if m else ""


GROUP_WORDS = re.compile(
    r"(?i)\b(consortium|group|team|committee|collaborat\w*|investigators|network|society|"
    r"association|organi[sz]ation|working|study|initiative|project|council|cent(er|re)|institute|"
    r"agency|department|ministry|office|programme|program|alliance|foundation|university|board|"
    r"panel|task force|writing|of|for|the|and|on|in)\b"
)


def is_group(name):
    """True for a group author: no comma, and group words, digits, parentheses, or more than
    four words. "Prescott C. Alexander" is a person; "Oxford COVID infection review team" is a
    group."""
    n = name.strip()
    if n.startswith("{") and n.endswith("}"):
        return True
    return "," not in n and (
        bool(GROUP_WORDS.search(n)) or bool(re.search(r"[0-9()]", n)) or len(n.split()) > 4
    )


def group(name):
    """A group author braced for BibTeX."""
    n = name.strip()
    return "{" + n + "}" if is_group(n) and not n.startswith("{") else n


def build(typ, tags, roles):
    """A record {type, fields} from tags; roles maps a field to the tags that fill it, in order."""
    f = {}
    for fld, keys in roles.items():
        vals = [v for k in keys for t, v in tags if t == k and v]
        if not vals:
            continue
        if fld in ("author", "editor"):
            f[fld] = " and ".join(group(v) for v in vals)
        else:
            f[fld] = vals[0]
    return dict(type=typ, fields=f)


def finish(rec):
    f = rec["fields"]
    venue = f.pop("venue", "")
    if venue:
        f["booktitle" if rec["type"] in ("inproceedings", "incollection") else "journal"] = venue
    if f.get("endpage"):
        f["pages"] = f.get("pages", "") + "--" + f.pop("endpage")
    if f.get("pages"):
        f["pages"] = pages_of(f["pages"])
    for k in ("year",):
        if f.get(k):
            f[k] = year_of(f[k])
    if f.get("doi"):
        f["doi"] = doi_of(f["doi"])
        if not f["doi"]:
            f.pop("doi")
    return rec


def parse_ris(t):
    tags = tagged(t, r"^([A-Z][A-Z0-9])  -\s?(.*)$")
    typ = next((RIS_TYPES.get(v.upper(), "misc") for k, v in tags if k == "TY"), "article")
    return finish(
        build(
            typ,
            tags,
            dict(
                author=["AU", "A1"],
                editor=["A2", "ED"],
                title=["TI", "T1"],
                venue=["JF", "JO", "T2", "BT", "JA", "J2"],
                volume=["VL"],
                number=["IS"],
                pages=["SP"],
                endpage=["EP"],
                year=["PY", "Y1", "DA"],
                publisher=["PB"],
                doi=["DO", "M3", "UR", "L3"],
            ),
        )
    )


def parse_enw(t):
    tags = tagged(t, r"^%(\S)\s+(.*)$")
    typ = word_type(next((v for k, v in tags if k == "0"), ""))
    return finish(
        build(
            typ,
            tags,
            dict(
                author=["A"],
                editor=["E"],
                title=["T"],
                venue=["J", "B"],
                volume=["V"],
                number=["N"],
                pages=["P"],
                year=["D"],
                publisher=["I"],
                doi=["R"],
            ),
        )
    )


def parse_refworks(t):
    tags = tagged(t, r"^([A-Z][A-Z0-9]) (.*)$")
    typ = word_type(next((v for k, v in tags if k == "RT"), ""))
    return finish(
        build(
            typ,
            tags,
            dict(
                author=["A1"],
                editor=["A2"],
                title=["T1"],
                venue=["JF", "T2", "JO"],
                volume=["VO"],
                number=["IS"],
                pages=["SP"],
                endpage=["OP"],
                year=["YR"],
                publisher=["PB"],
                doi=["DO"],
            ),
        )
    )


def parse_medline(t):
    tags = tagged(t, r"^([A-Z]{2,4})\s*- (.*)$")
    pts = " ".join(v for k, v in tags if k == "PT").lower()
    typ = "incollection" if "chapter" in pts else "book" if "book" in pts else "article"
    # authors in byline order: full names (FAU, else AU) and group authors (CN); the
    # investigator lists (IR, FIR) are not authors
    keep = ("FAU", "CN") if any(k == "FAU" for k, _ in tags) else ("AU", "CN")
    names = ["{" + v + "}" if k == "CN" else v for k, v in tags if k in keep]
    dois = [v for k, v in tags if k in ("LID", "AID") and "[doi]" in v]
    rec = build(
        typ,
        tags,
        dict(
            title=["TI"],
            venue=["JT", "TA"],
            volume=["VI"],
            number=["IP"],
            pages=["PG"],
            year=["DP"],
            publisher=["PB"],
        ),
    )
    if names:
        rec["fields"]["author"] = " and ".join(names)
    if dois:
        rec["fields"]["doi"] = dois[0]
    if rec["fields"].get("title"):
        rec["fields"]["title"] = rec["fields"]["title"].rstrip(".")
    return finish(rec)


def parse_csl(t):
    d = json.loads(t)
    d = d[0] if isinstance(d, list) else d
    f = {}

    def names(role):
        return " and ".join(
            "{" + (a.get("literal") or a.get("name")) + "}"
            if (a.get("literal") or a.get("name")) and not a.get("family")
            else ", ".join(x for x in (a.get("family"), a.get("given")) if x)
            for a in d.get(role) or []
        )

    f["author"], f["editor"] = names("author"), names("editor")
    title = d.get("title")
    f["title"] = title[0] if isinstance(title, list) else title or ""
    ct = d.get("container-title")
    f["venue"] = ct[0] if isinstance(ct, list) and ct else ct or ""
    for src, dst in (
        ("volume", "volume"),
        ("issue", "number"),
        ("page", "pages"),
        ("DOI", "doi"),
        ("publisher", "publisher"),
    ):
        if d.get(src):
            f[dst] = str(d[src])
    parts = ((d.get("issued") or {}).get("date-parts") or [[None]])[0]
    if parts and parts[0]:
        f["year"] = str(parts[0])
    rec = dict(
        type=CSL_TYPES.get(d.get("type", ""), "misc"), fields={k: v for k, v in f.items() if v}
    )
    return finish(rec)


def parse_export(text):
    """(record, format) of an export; record is None for plain text or an unknown file."""
    t = text.lstrip("\ufeff").strip()
    if not t or re.match(r"<(!doctype|html)", t, re.I):
        return None, None
    try:
        if t.startswith("@"):
            es = parse_bib(t)
            if es:
                f = es[0]["fields"]
                f["author"] = " and ".join(
                    group(n)
                    for n in split_names(re.sub(r"\s+AND\s+", " and ", f.get("author", "")))
                )
                return dict(type=es[0]["type"], fields=f, key=es[0]["key"]), "BibTeX"
        if re.match(r"TY  -", t):
            return parse_ris(t), "RIS"
        if re.match(r"%0 ", t) or re.search(r"(?m)^%A ", t):
            return parse_enw(t), "EndNote"
        if re.match(r"RT ", t):
            return parse_refworks(t), "RefWorks"
        if re.search(r"(?m)^PMID- ", t):
            return parse_medline(t), "MEDLINE"
        if t[:1] in "[{":
            return parse_csl(t), "CSL-JSON"
    except (ValueError, KeyError, IndexError, TypeError):
        return None, None
    return None, "plain text"


def bib_key(rec):
    fam = (
        name_split(split_names(rec["fields"].get("author", ""))[0])[0]
        if rec["fields"].get("author")
        else "anon"
    )
    return re.sub(r"[^a-z]", "", fam.split()[-1] if fam else "anon") + rec["fields"].get("year", "")


def to_bibtex(rec, key=None):
    order = (
        "author",
        "editor",
        "title",
        "journal",
        "booktitle",
        "volume",
        "number",
        "pages",
        "year",
        "publisher",
        "doi",
        "eprint",
        "archiveprefix",
        "primaryclass",
    )
    f = rec["fields"]
    lines = [f"@{rec['type']}{{{key or rec.get('key') or bib_key(rec)},"]
    lines += [f"  {k:<7} = {{{f[k]}}}," for k in order if f.get(k)]
    return "\n".join(lines).rstrip(",") + "\n}"


# ---------------------------------------------------------------- export URLs


def known_urls(kind, ident):
    if kind == "arxiv":
        return [f"https://arxiv.org/bibtex/{ident}"]
    d = ident.lower()
    if d.startswith(SPRINGER):
        u = f"https://citation-needed.springer.com/v2/references/{ident}?flavour=citation&format="
        return [u + "bibtex", u + "refman"]
    if d.startswith("10.1371/journal."):
        # PLOS BibTeX gives the PDF page range; its RIS export has the article number
        u = "https://journals.plos.org/plosone/article/citation/{}?id=" + ident
        return [u.format("ris"), u.format("bibtex")]
    m = re.match(r"10\.5194/([a-z]+)-(\d+)-(\d+)-(\d{4})$", d)
    if m:
        j, v, p, y = m.groups()
        base = f"https://{j}.copernicus.org/articles/{v}/{p}/{y}/{j}-{v}-{p}-{y}"
        return [base + ".bib", base + ".ris"]
    return []


def rank(u):
    for i, pat in enumerate(
        (r"bib", r"ris|refman", r"enw|endnote", r"refworks", r"medlars|nbib", r"csl")
    ):
        if re.search(pat, u, re.I):
            return i
    return 9


def landing_urls(doi):
    """Export links on the landing page, best format first; (urls, status, landing url)."""
    st, final, page = http("https://doi.org/" + urllib.parse.quote(doi, safe="/()"), "text/html")
    if st != 200 or CHALLENGE.search(page[:5000]):
        return [], st, final
    links = [html.unescape(h) for h in re.findall(r'href="([^"]+)"', page)]
    cands = [
        h
        for h in links
        if re.search(
            r"bibtex|\.bib(\?|$)|downloadcitation|citation-needed|exportcitation|citation[-_/]?export|"
            r"format=(ris|enw|endnote|refworks|medlars|csl|text|txt)|\.(ris|enw|nbib)(\?|$)|/citation/",
            h,
            re.I,
        )
    ]
    seen, out = set(), []
    for h in sorted(cands, key=rank):
        u = urllib.parse.urljoin(final, h)
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out, st, final


def pubmed_export(doi):
    """(text, url) of the PubMed (MEDLINE) record of a DOI, or None."""
    who = "&tool=bib-audit" + (
        f"&email={urllib.parse.quote(default_mailto())}" if default_mailto() else ""
    )
    st, _, js = http(
        EUTILS
        + "esearch.fcgi?db=pubmed&retmode=json&term="
        + urllib.parse.quote(doi + "[doi]")
        + who
    )
    try:
        ids = json.loads(js)["esearchresult"]["idlist"] if st == 200 else []
    except (ValueError, KeyError):
        ids = []
    if len(ids) != 1:
        return None
    st, final, text = http(
        EUTILS + f"efetch.fcgi?db=pubmed&id={ids[0]}&rettype=medline&retmode=text" + who
    )
    return (
        (text, f"https://pubmed.ncbi.nlm.nih.gov/{ids[0]}/")
        if st == 200 and parse_export(text)[0]
        else None
    )


def fetch_export(s, pubmed=True):
    """(text, url, note): the export, where it came from, or why it is missing. When the
    publisher gives nothing to a script, the PubMed record is the secondary source."""
    kind, ident = parse_id(s)
    if not kind:
        return None, None, f"not a DOI or arXiv identifier: {s}"
    plain, st, landing = None, None, None

    def attempt(urls, how):
        nonlocal plain
        for u in urls:
            st2, final, text = http(u)
            if st2 != 200:
                continue
            rec, fmt = parse_export(text)
            if rec:
                return text, final, f"{how}, {fmt}"
            if fmt == "plain text" and not plain:
                plain = (text, final, f"{how}, plain text")
        return None

    got = attempt(known_urls(kind, ident), "known endpoint")
    if got:
        return got
    if kind == "doi":
        found, st, landing = landing_urls(ident)
        got = attempt(found[:6], "export link on the landing page")
        if got:
            return got
    if plain:
        return plain
    if kind == "arxiv":
        return None, None, "arXiv export failed; re-run"
    browser = (
        f'open https://doi.org/{ident} in the browser, use its "Cite" or "Export citation" '
        "button (any format), then convert and compare the file with --file"
    )
    host = urllib.parse.urlsplit(landing).hostname if landing else "doi.org"
    why = (
        f"the publisher blocks scripts (HTTP {st}) at {host}"
        if st in (401, 403, 429) or st is None
        else f"no export link on the landing page at {host}"
    )
    pm = pubmed_export(ident) if pubmed else None
    if pm:
        return (
            pm[0],
            pm[1],
            f"PubMed record, the secondary source ({why}; for the publisher's file, {browser})",
        )
    return None, None, f"{why}; {browser}"


# ---------------------------------------------------------------- comparison


def compare(pf, bf, label, src="export"):
    out = []
    pa = [name_split(n) for n in split_names(pf.get("author", ""))]
    ba = [name_split(n) for n in split_names(bf.get("author", ""))]
    pk, bk = [k for k, _ in pa], [k for k, _ in ba]
    if pk == bk:
        out.append(("SAME", f"authors: {len(pk)}, same order"))
    else:
        dup = sorted({k for k in pk if pk.count(k) > 1 and bk.count(k) < pk.count(k)})
        if dup:
            out.append(("DIFF", f"the {src} repeats: " + ", ".join(dup)))
        extra = [k for k in dict.fromkeys(pk) if k not in bk]
        miss = [k for k in dict.fromkeys(bk) if k not in pk]
        if extra:
            out.append(
                ("DIFF", f"in the {src}, not in the {label} ({len(extra)}): " + ", ".join(extra))
            )
        if miss:
            out.append(
                ("DIFF", f"in the {label}, not in the {src} ({len(miss)}): " + ", ".join(miss))
            )
        if not dup and not extra and not miss:
            out.append(
                (
                    "DIFF",
                    f"same authors, different order "
                    f"({len(pk)} in the {src}, {len(bk)} in the {label})",
                )
            )
    given = dict((k, g) for k, g in ba if g and bk.count(k) == 1)
    for k, g in pa:
        if g and k in given and pk.count(k) == 1 and norm_text(g) != norm_text(given[k]):
            out.append(("DIFF", f'given name of {k}: {src} "{g}", {label} "{given[k]}"'))
    for fld in ("title", "venue", "volume", "number", "pages", "year", "doi"):
        if fld == "venue":
            pv = pf.get("journal") or pf.get("booktitle", "")
            bv = bf.get("journal") or bf.get("booktitle", "")
        else:
            pv, bv = pf.get(fld, ""), bf.get(fld, "")
        if not pv and not bv:
            continue
        if fld == "pages":
            same = norm_pages(pv) == norm_pages(bv)
        elif fld == "doi":
            same = pv.lower().strip() == bv.lower().strip()
        else:
            same = norm_text(pv) == norm_text(bv)
        if same:
            out.append(("SAME", fld))
        elif not pv:
            out.append(("INFO", f'{fld}: not in the {src}; {label} "{show(bv)}"'))
        else:
            out.append(("DIFF", f'{fld}: {src} "{show(pv)}", {label} "{show(bv) or "(none)"}"'))
    return out


def report(key, text, src, note, entry, save):
    print(f"=== {key}" + (f"  ({note}: {src})" if src else ""))
    if text is None:
        print(f"    MISSING {note}")
        return
    rec, fmt = parse_export(text)
    if save:
        os.makedirs(save, exist_ok=True)
        stem = os.path.join(save, re.sub(r"[^\w.-]+", "_", key) + ".publisher")
        with open(f"{stem}.{EXT.get(fmt, 'txt')}", "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"    saved {stem}.{EXT.get(fmt, 'txt')}")
        if rec and fmt != "BibTeX":
            with open(f"{stem}.bib", "w", encoding="utf-8") as fh:
                fh.write(to_bibtex(rec, entry["key"] if entry else None) + "\n")
            print(f"    saved {stem}.bib (converted from {fmt})")
    if not rec:
        print(
            f"    PLAIN the export is {fmt or 'not a citation file'}; "
            "convert it to BibTeX by reading it:"
        )
        print(re.sub(r"(?m)^", "      ", text.strip()[:2000]))
        return
    if entry is None:
        if fmt != "BibTeX":
            print(f"    (converted from {fmt})")
        print(re.sub(r"(?m)^", "    ", (text.strip() if fmt == "BibTeX" else to_bibtex(rec))))
        return
    if fmt != "BibTeX":
        print(f"    (export in {fmt}, compared after conversion)")
    for lvl, msg in compare(
        rec["fields"],
        entry["fields"],
        "bib",
        "PubMed record" if note.startswith("PubMed") else "export",
    ):
        print(f"    {lvl:4s} {msg}")


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("ids", nargs="*", help="DOIs or arXiv identifiers")
    p.add_argument("--bib", help="compare with the entries of this .bib")
    p.add_argument("--key", nargs="+", help="only these keys of --bib")
    p.add_argument("--file", help="an export saved from the browser, in any supported format")
    p.add_argument(
        "--save", help="directory for the downloaded exports and their BibTeX conversions"
    )
    p.add_argument("--no-pubmed", action="store_true", help="no PubMed fallback")
    a = p.parse_args()
    entries = []
    if a.bib:
        entries = parse_bib(open(a.bib, encoding="utf-8").read())
        if a.key:
            keys = {k.lower() for k in a.key}
            entries = [e for e in entries if e["key"].lower() in keys]
    if a.file:
        if a.bib and len(entries) != 1:
            p.error("--file with --bib needs exactly one --key")
        report(
            entries[0]["key"] if a.bib else os.path.basename(a.file),
            open(a.file, encoding="utf-8", errors="replace").read(),
            a.file,
            "saved export",
            entries[0] if a.bib else None,
            a.save,
        )
        return
    if a.ids:
        for s in a.ids:
            text, src, note = fetch_export(s, not a.no_pubmed)
            report(s, text, src, note, None, a.save)
        return
    if not entries:
        p.error("give identifiers, --bib, or --file")
    for e in entries:
        f = e["fields"]
        ident = f.get("doi") or (("arXiv:" + f["eprint"]) if f.get("eprint") else "")
        if not ident:
            print(f"=== {e['key']}\n    SKIP no doi or eprint")
            continue
        text, src, note = fetch_export(ident, not a.no_pubmed)
        report(e["key"], text, src, note, e, a.save)


if __name__ == "__main__":
    main()
