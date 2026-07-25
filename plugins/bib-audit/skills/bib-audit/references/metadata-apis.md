# Bibliographic metadata APIs

OpenAlex is no longer free and unlimited. It now enforces a prepaid daily budget and returns `429 {"error":"Rate limit exceeded","message":"Insufficient budget. This request costs $0.001 but you only have $0.0009 remaining. Resets at midnight UTC."}` with a `Retry-After` measured in hours. Once the budget is exhausted each call burns ~3.2s for zero information, and it contributed nothing across several hundred references in testing. Treat it as a best-effort third source rather than a dependable leg of a quorum, and cap `Retry-After` low, or one exhausted budget stalls the whole audit.

The rest are free, no API key. Always send a descriptive `User-Agent` with a mailto (Crossref politely throttles anonymous clients). Sleep ~0.5 s between Crossref calls, ~3 s between arXiv calls.

## Source ranking

| Rank | Source | Endpoint | Use for |
|---|---|---|---|
| 1 | Crossref | `api.crossref.org/works/{doi}` | Any DOI'd paper. Publisher-deposited metadata: full author names, exact title, venue. |
| 1 | doi.org content negotiation | `curl -LH "Accept: application/x-bibtex" https://doi.org/{doi}` | Canonical drop-in BibTeX straight from the registrar. |
| 2 | arXiv Atom API | `export.arxiv.org/api/query?id_list={id}` | Preprint-only works; full author lists; the only source for `10.48550/arXiv.*` DOIs. |
| 3 | Crossref search | `api.crossref.org/works?query.bibliographic={title}&rows=1` | Title → DOI resolution. Advisory: verify the hit before trusting. |
| 4 | OpenAlex | `api.openalex.org/works?search={title}` | Broadest coverage (~250M works incl. preprints) when Crossref search misses. |
| 5 | DBLP | `dblp.org/search/publ/api?q={title}&format=json` | CS conference papers — cleanest `booktitle`/proceedings strings. |
| ✗ | Semantic Scholar | `api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=citationStyles` | Do NOT use for bib metadata: abbreviates given names, lowercases titles, `bibtex` often null for arXiv. Citation graphs only. |

## One-liners

Canonical BibTeX from a DOI (the killer command):

```bash
curl -sLH "Accept: application/x-bibtex" "https://doi.org/10.3390/rs14225738"
```

Title → DOI + canonical authors:

```bash
curl -s "https://api.crossref.org/works?query.bibliographic=TITLE+WORDS&rows=1" \
  | python3 -c 'import sys,json; w=json.load(sys.stdin)["message"]["items"][0]; \
    print(w["DOI"], "|", w["title"][0], "|", ", ".join(a.get("family","") for a in w.get("author",[])))'
```

arXiv metadata by ID (batched, comma-separated):

```bash
curl -s "https://export.arxiv.org/api/query?id_list=1905.11946,1502.03167"
```

## Batch queries — do this before optimizing anything else

Don't loop one request per reference if you can avoid it. With polite sleeps on top, a 200-entry list is minutes of wall clock and nearly all of it is waiting. Three of these APIs take many papers per request, so use them to resolve everything with a printed identifier in a handful of calls, then fall back to serial title search only for the leftovers.

**Semantic Scholar — up to 500 papers per POST.** The fastest existence check available, and the results come back in request order with `null` for anything that doesn't exist:

```bash
curl -s -X POST 'https://api.semanticscholar.org/graph/v1/paper/batch?fields=title,year,externalIds' \
  -H 'Content-Type: application/json' \
  -d '{"ids":["DOI:10.1109/MGRS.2017.2762307","ARXIV:1711.05101","ARXIV:9999.99999"]}'
# -> [{...}, {...}, null]   <- the null IS the fabricated-identifier signal
```

Accepts `DOI:`, `ARXIV:`, `CorpusId:`, `MAG:`, `ACL:`, `PMID:`, `PMCID:` prefixes, mixed freely in one call. Use it for existence and for citation graphs only, never for the metadata comparison. Verified: that exact call returns `"Deep learning in remote sensing: a review"` and `"Fixing Weight Decay Regularization in Adam"`, both *v1 preprint* titles, for works whose published titles are "…A Comprehensive Review and List of Resources" and "Decoupled Weight Decay Regularization". Diffing a bib against S2 titles manufactures title mismatches on correct entries.

**OpenAlex — OR-filter, ~50 per request.** Unlike S2 this returns publisher-grade metadata, so it is safe to compare against:

```bash
curl -s 'https://api.openalex.org/works?per-page=50&select=doi,display_name,publication_year\
&filter=doi:10.1109/MGRS.2017.2762307|10.1007/978-3-319-24574-4_28'
```

Results come back unordered and omit misses entirely, so match them back by DOI and treat any requested DOI absent from the response as unresolved, rather than assuming positional alignment.

**arXiv — comma-separated `id_list`.** Already the reliable endpoint (`search_query` is the flaky one); batching is free:

```bash
curl -s "https://export.arxiv.org/api/query?id_list=1711.05101,1505.04597&max_results=2"
```

**Crossref has no batch fetch.** `/works/{doi}` is strictly one DOI per request; there is no multi-DOI endpoint, and `filter=doi:a,b` ANDs rather than ORs. So for DOI-pinned entries the batch route is OpenAlex (metadata) or S2 (existence), with Crossref reserved for the authoritative single-entry check and for `x-bibtex` content negotiation. Do get into the polite pool with a `mailto` — it buys a better rate limit, which matters most exactly when you are issuing many requests.

Suggested shape for a large bibliography: (1) one S2 batch call over every printed identifier to find dead ones immediately; (2) one or two OpenAlex OR-filter calls to pull real metadata for the survivors; (3) serial title search, sleeping politely, only for entries with no identifier at all. That gets a 200-entry list down to a few calls plus a short serial tail.

## Per-source caveats

- **Crossref**: `published` date-parts can be the online-first year, not the print year — check `published-print` too before flagging a year. Author objects sometimes omit `family` for consortia.
- **doi.org negotiation**: returns the registrar's metadata; for Crossref DOIs that means the publisher's. Generated citation key is arbitrary — replace it with the bib's existing key.
- **arXiv**: `search_query` endpoint is flaky (timeouts, 503s); `id_list` is reliable. Returned year is the *v1 submission* year. Author list is the *latest version's* list, which may still differ from camera-ready.
- **DataCite DOIs** (`10.48550/arXiv.*`, Zenodo `10.5281/*`): not in Crossref (404). arXiv ones → arXiv API; others → `api.datacite.org/dois/{doi}` or doi.org negotiation (DataCite also honors `Accept: application/x-bibtex`).
- **OpenAlex**: includes a polite-pool boost if you append `&mailto=you@example.com`.
