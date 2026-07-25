"""Find the authoritative identifier (DOI or arXiv ID) for a paper.

Companion to validate_refs.py: when an entry is [UNRESOLVED] or [CHECK],
use this to find the identifier to add to the bib. Queries Crossref title
search and arXiv in parallel-ish and prints candidates with enough context
(title, first author, year) to confirm the match by eye — never trust a
fuzzy hit blindly.

Stdlib only. Examples::

    python3 lookup_id.py "Decoupled Weight Decay Regularization"
    python3 lookup_id.py --arxiv-id 1711.05101          # verify a known ID
    python3 lookup_id.py "Panoptic Segmentation" --author Kirillov

Set ``BIB_AUDIT_MAILTO`` to join Crossref's polite pool (optional; anonymous
clients are throttled harder).
"""

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ARXIV_NS = {"a": "http://www.w3.org/2005/Atom"}
MAILTO = os.environ.get("BIB_AUDIT_MAILTO", "")


def http_get(url: str, timeout: float = 60.0, retries: int = 4) -> str:
    agent = "bib-audit-lookup/1.0"
    if MAILTO:
        agent += f" (mailto:{MAILTO})"
    req = urllib.request.Request(url, headers={"User-Agent": agent})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (TimeoutError, urllib.error.URLError) as exc:
            if attempt == retries - 1:
                raise
            print(f"  (retry {attempt + 1}: {exc})")
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


def crossref_candidates(title: str, author: str | None, rows: int) -> None:
    params = {"query.bibliographic": title, "rows": str(rows)}
    if author:
        params["query.author"] = author
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
    items = json.loads(http_get(url))["message"]["items"]
    print(f"== Crossref ({len(items)} candidates) ==")
    for w in items:
        t = (w.get("title") or ["?"])[0]
        authors = w.get("author") or []
        first = (
            f"{authors[0].get('family', '?')}, {authors[0].get('given', '')}".strip(", ")
            if authors
            else "?"
        )
        year = "?"
        for key in ("published-print", "published", "issued"):
            parts = w.get(key, {}).get("date-parts")
            if parts and parts[0] and parts[0][0]:
                year = parts[0][0]
                break
        venue = w.get("container-title") or ["?"]
        print(f"  doi:{w['DOI']}")
        print(f"    {t}")
        print(f"    {first} et al. ({year}) -- {venue[0]} -- {len(authors)} authors")


def arxiv_parse(xml_text: str) -> None:
    entries = ET.fromstring(xml_text).findall("a:entry", ARXIV_NS)
    real = [e for e in entries if e.find("a:id", ARXIV_NS) is not None]
    print(f"== arXiv ({len(real)} candidates) ==")
    for e in real:
        aid = e.find("a:id", ARXIV_NS).text.split("/abs/")[-1]
        aid = re.sub(r"v\d+$", "", aid)  # bib entries want the bare ID
        title_el = e.find("a:title", ARXIV_NS)
        if title_el is None or not title_el.text:
            continue
        title = " ".join(title_el.text.split())
        names = [
            a.find("a:name", ARXIV_NS).text
            for a in e.findall("a:author", ARXIV_NS)
            if a.find("a:name", ARXIV_NS) is not None
        ]
        pub = e.find("a:published", ARXIV_NS)
        year = pub.text[:4] if pub is not None and pub.text else "?"
        print(f"  arxiv:{aid}")
        print(f"    {title}")
        first = names[0] if names else "?"
        print(f"    {first} et al. ({year}) -- {len(names)} authors")


def arxiv_by_id(arxiv_id: str) -> None:
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        {"id_list": arxiv_id}
    )
    arxiv_parse(http_get(url))


def arxiv_search(title: str, author: str | None, rows: int) -> None:
    # search_query is flaky (503s/timeouts); http_get retries with backoff.
    q = f'ti:"{title}"'
    if author:
        q += f" AND au:{author}"
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        {"search_query": q, "max_results": str(rows)}
    )
    arxiv_parse(http_get(url))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("title", nargs="?", help="paper title (or distinctive phrase)")
    parser.add_argument("--author", help="author surname to narrow the search")
    parser.add_argument("--arxiv-id", help="verify a specific arXiv ID instead of searching")
    parser.add_argument("--rows", type=int, default=3, help="candidates per source")
    args = parser.parse_args()

    if args.arxiv_id:
        arxiv_by_id(args.arxiv_id)
        return 0
    if not args.title:
        parser.error("provide a title to search, or --arxiv-id to verify")

    crossref_candidates(args.title, args.author, args.rows)
    print()
    try:
        arxiv_search(args.title, args.author, args.rows)
    except (TimeoutError, urllib.error.URLError) as exc:
        print(f"== arXiv search unavailable ({exc}); retry later or use --arxiv-id ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
