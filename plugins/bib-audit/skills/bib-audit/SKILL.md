---
name: bib-audit
description: Flag hallucinated references, authors and bib items, and correct badly formatted ones, in any paper — your own draft (run it before submitting) or one you are reviewing — from a .bib file, a PDF, or a pasted reference list. Checks every entry against Crossref (DOI), arXiv (eprint ID), and title search; detects fabricated DOIs/arXiv IDs, hallucinated titles and authors, truncated author lists, wrong years; recovers canonical publisher BibTeX. Also citation-style rules (et al., \cite spacing, shortcite, reference sorting, bib title capitalization). Use to validate/audit/check references, verify citations in a submission under review, fix bib entries, hunt hallucinated or invented citations, extract a bibliography from a PDF, look up a DOI/canonical BibTeX, or gate a pre-submission bibliography.
---

# Bib Audit

Two jobs, in priority order:

1. **Flag hallucinated references, authors and bib items** — works that don't exist, identifiers that name a different paper, authors who aren't on the paper.
2. **Correct badly formatted references** — resolve every field from the registrar of record instead of hand-authoring it.

Core rule: **never author bib fields — resolve them.** Every reference should trace to a DOI or arXiv ID.

**Why this matters more than tidiness.** The point is for authors to run this *before* submitting, so that reviewers never have to spend their time spot-checking a bibliography to decide whether an LLM wrote the paper. Reference-checking is currently a tax that reviewers pay for other people's carelessness, and it is a bad use of the scarcest resource in peer review. If everyone gates their own submission on this, that doubt disappears as a category. So the tool is built author-first: it is read-only, it exits non-zero for CI, and it tells you how to *fix* each finding rather than only naming it. Using it to audit someone else's submission works and is documented below, but that is the fallback, not the goal.

That priority also sets the design bias: a false accusation is worse than a miss. A missed bad reference is one entry a reviewer might still catch; a false "fabricated" verdict on a correct entry destroys trust in the whole report, and in a review it puts an integrity allegation next to someone's name. When in doubt the tool downgrades to advisory rather than escalating.

Both situations differ only in what you do with a finding:

- **Your own paper** (draft, pre-submission, camera-ready) — fix in place. Replace fields from the canonical source, add missing identifiers, re-run until the audit is clean, then wire it into CI as a gate.
- **Someone else's paper** (peer review, reading a preprint, checking a collaborator's draft) — you can't fix it, so the output is evidence. Resolve each finding to "identifier names no paper" or "identifier names a different paper" *before* saying anything, quote the specific entry, and see the review-etiquette note below — a citation-manager glitch and deliberate fabrication look identical in the audit output.

## Quick start

Pick the entry point by what you have:

**A `.bib` file** — already structured, so no parsing step:

```bash
python3 scripts/validate_refs.py path/to/refs.bib
python3 scripts/validate_refs.py refs.bib --key somekey2024 --show-bibtex
```

**A PDF** — three steps, and step 2 is yours, not a regex's:

```bash
# 1. get the reference-list text (plain pdftotext, NOT -layout — see below)
pdftotext paper.pdf - | tr -d '\f' | sed -n '/^[[:space:]]*References[[:space:]]*$/,$p' > refs.txt
# 2. READ refs.txt and write refs.json yourself: one object per reference
#    (schema in scripts/audit_refs.py — title required; doi/arxiv ONLY if printed)
# 3. resolve and rank
python3 scripts/audit_refs.py refs.json
```

**Extract in chunks of ~20 references, writing each chunk to its own file before starting the next**, then combine them into one `refs.json` and verify the object count before auditing. A 117-reference bibliography is far too much to emit in a single response — attempting it killed two test runs mid-generation — and chunking also means an interruption costs you one chunk instead of the whole paper.

**Fill in `kind` and `authors_truncated` as you extract** — they are the two fields that decide whether the report is usable. Mark datasets, agency reports, software, standards and web pages as non-`article`: DOI registries don't index them, so an unmarked one lands in the top tier as "may not exist", and on a paper citing national mapping agencies and NOAA atlases that was most of the top tier. Mark `authors_truncated` whenever the reference printed "et al." — otherwise its deliberately partial author list is reported as missing authors, which was over half of all housekeeping findings on real bibliographies.

**Do the extraction step yourself; do not add heuristics to do it.** Turning a rendered reference list back into fields is a language task — authors, title, venue and year are separated by conventions that differ per style — and it is the single most bug-prone thing in this skill's history: every false "fabricated" verdict found during testing traced back to a title- or reference-splitting heuristic, not to a bad API answer. Read the text, emit JSON, hand it to the script. Critically, **only fill in `doi`/`arxiv` when the reference actually prints one** — supplying an identifier you inferred defeats the entire audit.

This also matches what the APIs want. Semantic Scholar's [title matcher](https://api.semanticscholar.org/api-docs/#tag/Paper-Data/operation/get_graph_paper_title_search) resolves a clean title exactly and rejects a raw reference string outright; Crossref's `query.bibliographic` accepts a raw string but will confidently bind an invented reference to an unrelated work (it matched a fabricated title to *"Thomas Aquinas on the Ultimate Why Question"*). Give both a parsed title and they behave. `audit_refs.py` then re-fetches authoritative metadata from the registrar, because S2 returns v1 preprint titles.

**Legacy path** (`scripts/resolve_refs.py` + `scripts/refparse.py`) does the parsing with heuristics instead. Keep it only for CI gates and other non-interactive runs where no extraction step is available; it is best-effort and its extraction caveats are documented below. Prefer `audit_refs.py`.

Both are stdlib-only (no deps) and read-only — they never edit your files. Both exit 1 on fabricated identifiers or authoritative mismatches, so either works as a CI/pre-submission gate. Layout: `scripts/refparse.py` turns messy extracted text into clean reference strings, `scripts/bibmeta.py` does all API resolution, and `scripts/lookup_id.py` finds the identifier for a single paper.

Optional: `export BIB_AUDIT_MAILTO=you@example.org` to join Crossref's polite pool — anonymous clients get throttled harder on a few hundred entries.

**On speed — flag, don't perfect.** Not every reference will resolve, and that is fine: the job is to *flag* what could not be checked so a human follows up, not to guarantee an answer for each one. Retries are deliberately impatient (2 attempts, ~1s backoff, `Retry-After` capped at 3s) because a long exponential backoff times three sources times a few hundred references turns a two-minute audit into an afternoon. `[LOOKUP FAILED]` is a first-class outcome meaning "re-run this one", never a finding. A "not found" verdict needs only a **quorum of two** sources answering, not unanimity — otherwise one third party's rate limit silently downgrades every entry to unverifiable. Measured: 7 references in ~10s with one source actively returning 429.

**Batching, when you need more speed:** both scripts resolve serially with a polite sleep. Semantic Scholar accepts 500 papers per POST, OpenAlex ~50 per OR-filtered request (but see its budget limit below), and arXiv takes a comma-separated `id_list` — so every entry with a printed DOI or arXiv ID can be checked in a handful of calls, leaving only identifier-less entries for the serial tail. Recipes and the ordering caveats are in [references/metadata-apis.md](references/metadata-apis.md#batch-queries--do-this-before-optimizing-anything-else). One rule if you build that path: use S2 for *existence* (a `null` in the batch response is the fabricated-identifier signal) but never for metadata comparison — it returns v1 preprint titles.

## Getting references out of a PDF

`pdftotext` (poppler) is the reliable path; without it, have Claude read the PDF and write the reference list to a text file — `resolve_refs.py` only needs one reference per line, or blank-line-separated blocks, and strips `[12]`/`12.`/`(3)` markers itself.

**Use plain `pdftotext`, NOT `-layout`.** This is counterintuitive — `-layout` looks like the careful choice — but on a two-column paper (most CVPR/ICCV/NeurIPS submissions) it preserves the visual columns, so every output line splices together text from the left *and* right columns and no reference survives intact. Plain mode follows the content stream, which usually gets reading order right — but **not always**: on one two-column ICCV paper it emitted the 117 references in the order 19-38, 1-18, 56-75, 39-54, 98-117, 76-96. Recoverable (the markers are still there) but check them. Measured across six real submissions, plain mode extracted every reference list; `-layout` extracted zero from the two-column ones.

**If arXiv LaTeX source is available, parse the `.bbl` instead of the PDF.** It has none of these problems — one `\bibitem` per reference, in order, one field per `\newblock`, no de-hyphenation damage (`Perpixel`, `graphbased`, `largescale` all came out of real PDF text) and no form feeds hiding markers. A ~30-line `.bbl` parser reproduced a careful 117-reference hand extraction field-for-field, and hand extraction took ~35 minutes against ~13 minutes of actual API time. Reserve the manual extraction step for PDF-only inputs, where the ambiguity genuinely lives.

**Papers under review usually carry margin line numbers**, which `pdftotext` interleaves into the text (`279  References  279`, or numbers on their own lines). `resolve_refs.py` detects and strips both shapes (`strip_line_numbers`) — paired numbers must match across both margins, and leading-only numbers must run consecutively, so a real `12.` reference marker is never mistaken for one. Unstripped, the leading number reads as a list marker and the trailing one corrupts the reference string.

**PDF text extraction hard-wraps mid-token**, which is the one thing that will burn you: a DOI can arrive as `doi:10.1109/MGRS.2` + newline + `017.2762307`. Naively rejoining with a space truncates the DOI and the reference gets reported as fabricated — a false accusation, and the most damaging mistake this skill can make. `resolve_refs.py` heals these (see `dewrap`), but **spot-check the parse before trusting a fabrication verdict on a PDF**:

```bash
python3 -c "import sys; sys.path.insert(0,'scripts')
from refparse import split_references, printed_doi, printed_arxiv
for i, r in enumerate(split_references(open('refs.txt').read()), 1):
    print(i, printed_doi(r), printed_arxiv(r), r[:90])"
```

A DOI that ends mid-string, or a reference count that disagrees with the paper's, means the extraction went wrong — not that the authors invented anything.

**Strip the form feed.** `pdftotext` emits `\f` before a page break, so a References heading that starts a page arrives as `\fReferences` and `^ *References *$` matches nothing — the step silently yields an empty file. Verified on a real paper: the un-stripped recipe returned **0 lines**, `tr -d '\f'` returned 258.

**Count the references before trusting any verdict.** With LaTeX source available the exact oracle is `grep -c '\\bibitem'` or the `\begin{thebibliography}{N}` argument. From a PDF alone, compare the extracted count against the highest marker number — but note this only works for `[1]`…`[N]` lists. **Author–year bibliographies (ICLR, COLM, NeurIPS, ACL) have no markers at all**, so the check prints `?` and tells you nothing; on one such paper it silently hid a 26% loss (74 references merged into 55). For a `[1]`…`[N]` bibliography those two numbers must be equal; a gap means references got merged and any verdict on them is untrustworthy:

```bash
python3 -c "import re, sys; sys.path.insert(0,'scripts')
from refparse import split_references, detect_marker, strip_line_numbers
t = open('refs.txt').read(); lines = strip_line_numbers(t).splitlines()
m = detect_marker(lines); n = [int(re.search(r'\d+', m.match(l).group(0)).group(0)) for l in lines if m and m.match(l)]
print('extracted', len(split_references(t)), 'highest marker', max(n) if n else '?')"
```

Extraction failures found by running this against real submissions, all of which produced *false* findings before they were fixed — the pattern to expect is that bad parsing manufactures fabrication, not that it hides it:

- **A prose heuristic must never override an explicit marker style.** In a `[N]`-numbered list, "a line starting `Surname, `" splits references mid-author-list: `Huy V.` / `Vo, Marc Sbai, …` is *one* name across a line wrap, and splitting there strands the real first author in the previous fragment, so the orphan resolves to a paper whose first author is "missing" → reported as a fabricated identifier. `detect_marker` makes marker style sticky for exactly this reason.
- **Marker detection needs an enumeration test, not just a pattern match.** Wrapped lines opening with a parenthesised year (`(2021) pp. 1016--1022`) pass as `(N)` markers. Requiring the numbers to start near 1 and mostly ascend rejects years; without it, two of six test papers collapsed from 50 and 25 references to 9 and 5.
- **Match letters as Unicode, not `[A-Za-z]`.** `13. Şimşek, F.F.: …` failed the marker's ASCII letter lookahead, so that reference silently merged into number 12. Any surname starting outside ASCII hits this.
- **Strip standalone digit runs and repeated page furniture — at line level, before grouping.** Non-layout `pdftotext` emits margin line numbers on their own lines, and the running header (`<Venue> 2026 Submission #NNNN`) repeats every page. Dropping furniture only *after* grouping is too late and was the subtlest bug of the set: a header landing mid-reference gets joined into it and becomes indistinguishable from the citation's own text. Observed spliced into the middle of a title — `Sentinel-2: ESA's optical high-resolution mission for <header> GMES operational services` — which dropped the title match to 0.18 and escalated a real, correctly-cited paper to `[FABRICATED]`. The same splice duplicated and corrupted a DOI, leaving one mangled copy and one intact copy in the same reference.
- **Prefer the longest DOI when a reference contains several.** Extraction damage always *shortens* a DOI (truncation at a wrap, or a hyphen eaten by de-hyphenation), so when a page break leaves both a corrupted and an intact copy, the longest match is the real one.
- **Never de-hyphenate inside an identifier.** Joining wrapped lines by dropping a trailing hyphen is right for prose and wrong for DOIs: `10.1038/s41597-` + `026-07099-1` became `s41597026-07099-1`, a dead DOI on a live paper. The identifier check has to run *before* the de-hyphenation rule.
- **Route non-Crossref DOIs to DataCite.** Zenodo (`10.5281/*`), figshare and Dryad DOIs 404 on Crossref while being entirely real — dataset citations are common in remote-sensing papers, and treating a Crossref 404 as proof of fabrication flags them all.

What the PDF path *cannot* do, by design: **it can't detect author truncation.** Reference lists legitimately abbreviate to "et al.", so a 3-of-7 author list in a PDF is normal formatting, not an error. Truncation is only checkable against a real `.bib` (`validate_refs.py`), where the full list was supposed to be present.

## Verdicts and what to do with each

| Verdict | Meaning | Action |
|---|---|---|
| `[OK]` | Matches authoritative metadata | Nothing |
| `[FABRICATED]` | The entry's own DOI/arXiv ID names no paper, or names a work whose title is clearly not the one cited | Fix the **identifier**, never the title — see below |
| `[MISMATCH]` | DOI/arXiv pins the work and the bib disagrees → genuine error | Replace fields with `--show-bibtex` output |
| `[NOT FOUND]` (PDF path) | No Crossref/arXiv/OpenAlex match for the reference string | Check the extraction parsed cleanly, then suspect an invented paper |
| `[CHECK]` (search-only) | Fuzzy title-search bound *some* paper and it differs — may be a wrong bind, not a bib error | Verify by hand; best fix is adding a `doi`/`eprint` to the entry |
| `[CHECK]` (preprint vs published) | arXiv-resolved entry differs on year/authors — preprints legitimately differ from camera-ready | Usually the bib is right; confirm against the published venue |
| `[UNRESOLVED]` | No DOI/arXiv ID and no close title match | Add an identifier (see workflow); web specs/`@misc` URLs stay unresolved by design |
| `[LOOKUP FAILED]` | Rate limit or API outage | Not a finding at all — re-run those entries |
| `[UNVERIFIABLE]` | Grey literature (`kind` ≠ `article`) or anonymized for blind review | Expected. Check the URL resolves; never a fabrication signal |

## Priority order for fixing

Both scripts print the per-reference log first, then a **ranked findings** section grouping everything into four tiers (`scripts/triage.py`). Fix top-down; the tiers exist because these are not the same kind of news, and mixing them in one list invites the reader — a co-author or an author you're reviewing — to dismiss the whole thing as pedantry.

| Tier | What it means | Why it ranks here |
|---|---|---|
| **P1** | The cited work isn't found anywhere | The sentence citing it has no support. Re-read the claim; don't just swap in a similar paper. |
| **P2** | Fabricated identifier, or an invented author | Points at the wrong paper, or credits someone for work they didn't do. Integrity-shaped. |
| **P3** | Wrong metadata on a real, correctly-identified work | Truncated author lists, preprint-vs-published year drift. Housekeeping. |
| **P4** | Formatting and style | Mechanical, batch-fixable last, changes nothing about which paper is cited. |

The **P2/P3 boundary is the one to internalize**: an identifier naming no paper and an author who isn't on the paper are different in kind from a truncated author list. In a review they belong in different paragraphs; in your own paper, different work sessions.

P4 findings are checked mechanically by `scripts/bibstyle.py` on the `.bib` path — single-hyphen page ranges, all-entries-start-at-page-1, DOI stored as a URL, `url` duplicating `doi`, spelled-out months, double-braced titles, ALL-CAPS titles, `J.D.` initials, and entries with no identifier at all. These are the rules a human reviewer never has patience to check across sixty entries.

### The "and others" tell

`author = {Smith, J. and others}` is **valid BibTeX** — the `.bst` renders it as "et al.", so it never looks broken in the built PDF. That's exactly why it's worth flagging: a reference manager exporting a real record writes every author, so the phrase appearing in `.bib` *source* means the entry was authored without the full list ever being known. Reported at P3 per entry, and when it recurs across 2+ entries, once more as a corpus-level signal — a repeated short-prefix-plus-`and others` pattern is a generation artifact, not a typing habit, and it's grounds to treat *every* identifier in the file as unverified rather than just those entries.

Two traps when implementing this: the literal token `others` must be excluded from author comparison (keying it as a surname makes every abbreviated entry report an author "in the bib but not on the registry record" — i.e. the invented-author signal, a false integrity accusation), and the same `and others` in a *rendered* reference list means something different, since a working `.bst` would have emitted "et al." there.

**Severity is deliberately asymmetric.** Only a dead identifier or a badly wrong title reaches `[FABRICATED]`; author- and year-level disagreements stay advisory `[CHECK]`. That's because on a PDF-extracted string those signals are unreliable — `et al.` hides author order, and extraction mangles diacritics (`Gökçe` arriving as `Gök"e` fails a surname check against `gokce` on a perfectly correct entry). Escalating them produced six false fabrication findings in a single real paper during testing.

## Fabricated identifiers and authors — hunt these first

An LLM-drafted bibliography doesn't just get fields wrong, it invents DOIs, arXiv IDs, co-authors, and occasionally whole papers. Fabrication is nastier than ordinary error because a well-formed identifier makes an entry *look* verified. Four shapes, worst first:

1. **Identifier resolves, but to a different paper.** Syntactically valid, HTTP 200, wrong work. Shows up as `[MISMATCH]` with a title diff on a DOI-resolved entry. Treat any such title diff as a fabricated DOI until proven otherwise — **fix the identifier, never the title.** Editing the bib title to match a wrong DOI is how a fake citation becomes permanent. Re-resolve from the title with `lookup_id.py`, confirm first author + year by eye, replace the identifier.
2. **Identifier doesn't resolve at all.** Dead DOI (404 from Crossref) or an arXiv ID with no record. Both scripts report this as `[FABRICATED]` and name the identifier, keeping it distinct from `[UNRESOLVED]`, which means the entry never claimed an identifier in the first place. The distinction is the whole point: "you forgot a DOI" is housekeeping, "your DOI is fake" is a retraction-grade problem. Note the two arXiv shapes — a well-formed-but-nonexistent ID returns zero results, while a *malformed* ID returns a record titled `Error`; both are treated as naming no paper rather than as a title mismatch against the literal string "Error".
3. **Real paper, invented authors.** Plausible co-authors grafted onto a genuine work. The tell is `authors in bib but not api` — an *extra* surname the registrar doesn't have. This is worse than the truncation case (`authors in api but not bib`): truncation shortchanges people, fabrication credits them for work they didn't do, and reviewers notice when it's their own name.
4. **The paper doesn't exist.** Confident title, real-sounding venue, no record anywhere. Signal: title search misses across Crossref *and* OpenAlex *and* arXiv (see [references/metadata-apis.md](references/metadata-apis.md) — one source missing means nothing, all three missing on a supposedly-published paper means invented). Delete the entry and the claim it supports; don't go hunting for a real paper to swap in without re-reading what the sentence asserts.

An entry with no `doi`/`eprint` at all isn't evidence of good faith — it's just unfalsifiable. Resolve it before trusting it.

### Reporting this in a review

The audit finds *wrong metadata*. It cannot tell you *why* the metadata is wrong, and the innocent explanations are common: Google Scholar and publisher exports ship systematically broken BibTeX (see the gotchas below), citation managers silently mangle DOIs, and a wrong-but-real DOI is usually a copy-paste slip from the adjacent entry. Before writing anything in a review:

- **Anonymized references are not missing references.** A double-blind submission cites its own prior work as "Anonymous. Title. Under review." — unresolvable *by design*, and the author comparison against it can never pass. The scripts detect these (`is_anonymized`) and report `[CHECK]`, never `[FABRICATED]`, but if you audit by hand: an unresolvable "Anonymous" entry is the authors following the rules, and flagging it reads as though you didn't understand the review process.
- **Re-verify by hand.** Resolve the identifier yourself in a browser. On a PDF, confirm the extraction didn't wrap or truncate it. One false accusation of fabrication costs you more credibility than the finding was worth.
- **Report the observation, not the motive.** "Ref [14]'s DOI `10.xxxx/yyy` resolves to a different paper (*actual title*); the cited title appears to be *other title*, DOI `10.zzz`" is checkable and useful. "The authors fabricated citations" is an integrity allegation, which is the editor's call to make, not a reviewer's line item.
- **Count before you generalize.** One bad DOI in forty is noise. A cluster — several unresolvable identifiers, or authors who don't exist on real papers — is a pattern worth raising with the editor explicitly and separately from the technical review.
- **Say which shape it is.** Truncated author lists and preprint-vs-published year drift are formatting nits. Identifiers that name no paper, and papers that exist nowhere, are not. Grouping them together in one comment invites the authors to dismiss the whole list as pedantry.

## Workflow: fixing your own bibliography

1. Run the audit. Triage by verdict per the table above, `[FABRICATED]` first.
2. For each `[MISMATCH]`: rerun with `--key <key> --show-bibtex` — it prints the publisher's own BibTeX (Crossref content negotiation) with the existing citation key preserved, ready to paste.
3. For `[UNRESOLVED]`/`[CHECK]` real papers: find the identifier with `scripts/lookup_id.py`, add it to the entry, re-run. This flips the entry from fuzzy matching to authoritative.

   ```bash
   python3 scripts/lookup_id.py "Decoupled Weight Decay Regularization" --author Loshchilov
   python3 scripts/lookup_id.py --arxiv-id 1711.05101   # verify a candidate ID
   ```

   Confirm title + first author by eye before adding — **never add an identifier from memory**. Conference/ML papers nearly all have arXiv IDs (`eprint = {...}, archivePrefix = {arXiv}`); journal papers get `doi = {...}`.
4. Re-run until 0 mismatches. Rebuild the paper (`pdflatex` + `bibtex`) to confirm no undefined citations and — if only identifiers were added — an unchanged PDF.

## Workflow: auditing a paper you didn't write

You can't edit the bib, so the goal is a short list of defensible findings rather than a clean exit code.

1. Get the reference list out (`pdftotext` recipe above), then **verify the parse before the audit** — reference count matches the paper, no DOI truncated at a line wrap. Extraction noise masquerades as fabrication.
2. Run `resolve_refs.py`. Read `[FABRICATED]` and `[NOT FOUND]` first; treat `[CHECK]` as "the search bound something loosely," which on a messy reference string is expected and usually not a finding at all.
3. Hand-verify every `[FABRICATED]` and `[NOT FOUND]` in a browser before it goes in the review. Two lookups per finding, and it's the step that keeps you out of trouble.
4. Write it up per the review-etiquette rules above: observation, not motive; count before generalizing; keep formatting nits in a separate bucket from identifiers that name no paper.
5. Optional: `--emit-bibtex` recovers a real `.bib` from the PDF's references — handy when you want to cite something the paper cited, without retyping it.

For API endpoints, curl one-liners, source ranking, and per-source caveats, read [references/metadata-apis.md](references/metadata-apis.md).

## Non-obvious gotchas (each cost real debugging time)

- **arXiv DOIs 404 on Crossref.** `10.48550/arXiv.*` = DataCite-registered; route to the arXiv API (script does this).
- **Preprint ≠ published.** arXiv year = v1 year (AdamW: 2017 preprint vs ICLR 2019); v1 author lists can differ from camera-ready (MS COCO: 10 vs 8). Never hard-fail these.
- **Title-search false binds.** Crossref fuzzy search confidently returns the wrong paper ("U-Net" matched a 2017 single-author work). Search hits advisory only — pin with an identifier before trusting any diff.
- **LaTeX accents break author comparison.** `H{\"a}nsch` must decode to Crossref's Unicode `Hänsch` (script handles `\"a`, `\c{c}`, `{\v s}`, `\ss`, etc.). Decode *before* stripping braces, or nested-brace `Gon{\c{c}}alves` degrades to `Gon\ccalves`, keys as `ccalves` — permanent false MISMATCH.
- **Online-first ≠ print year; both right.** Crossref deposits multiple dates (`published-online` 2008 vs `published-print` 2009, Akbari et al., Climatic Change); journals' "cite this" pages typically use print year. Script accepts a bib year matching *any* deposited date — never hard-fail.
- **Google Scholar BibTeX = discovery, not copying.** Can omit `year` (AdamW), no DOIs, mangles venues. Canonical-source ranking: Crossref content negotiation (DOI) > DBLP for CS/ML conferences (`curl https://dblp.org/rec/<key>.bib`) > arXiv export. Script doesn't consult DBLP — for ICLR-style no-DOI venues, pull the DBLP record manually.
- **ICLR/OpenReview papers have no page numbers.** `pages = {1--19}` on an ICLR entry = authored, not resolved — delete. DBLP record (publisher `OpenReview.net`, no pages) is canon.
- **Semantic Scholar ≠ metadata source.** Its `citationStyles.bibtex` abbreviates given names (`Jane Doe` → `J. Doe`), lowercases titles, nulls some arXiv papers — the exact truncation failure this skill catches. S2 = citation graphs only.
- **`eprint`/`archivePrefix`.** Classic `.bst` styles ignore them (PDF unchanged); arXiv export uses them — but *not* conventional in journal/conference bibs for published papers. Strictly conventional file wanted → arXiv IDs in a sidecar list, not the bib.
- **arXiv API flakiness.** `search_query` times out / 503s under load; `id_list` reliable. Prefer `id_list`, retry with backoff, ~3 s between requests.

## Citation & reference style

Style-side companion to the metadata audit; prose/typesetting nitpicks live in the `research-paper-nitpick` skill. Rules below distilled from John Owens's (UC Davis) writing and bibliography-error notes and Henning Schulzrinne's (Columbia) writing-style guide, plus Chicago 7.56 on abbreviation italics.

- **Never cite as a noun.** "A similar strategy is discussed by AuthorOne et al. [15]", not "described in [15]". Test: imagine the citations as superscripts — if the sentence breaks, it's wrong.
- **"et al.":** period after "al" only ("et al.", never "et. al"); never italicized (Chicago 7.56 — same for "e.g."/"i.e."). In-text author forms: one author = A; two = A and B; three+ = A et al.
- **"i.e." ≠ "e.g.":** *id est* (that is) vs *exempli gratia* (for example) — not interchangeable.
- **`text~\cite{key}`** — non-breaking `~` before every citation. Multiple works in ONE `\cite{a,b}`, ordered so rendered numbers ascend ([6, 8, 10], not [8, 6, 10]); the `cite` package auto-sorts and ranges ([1–4, 6]).
- **`\shortcite`** when the author is already named in the sentence: "AuthorOne [2002] discusses…", not "AuthorOne discusses this in [AuthorOne 2002]". Style lacks it → `\providecommand{\shortcite}[1]{\cite{#1}}` in the preamble — `\providecommand`, not `\newcommand`, so the definition is skipped rather than erroring out on styles that already supply it.
- **Sort the reference list alphabetically** by first author's last name; cited-order only for surveys where citation proximity helps.
- **Bib title capitalization:** brace only the specific words that must keep caps (`{L}oop`, `{GPU}`, proper names); never double-brace the whole title — let the `.bst` decide title vs sentence case.
- **ACM/IEEE Digital Library BibTeX ships systematic errors** — venue capitalization ("workshop on Graphics hardware" → "Workshop on … Hardware"), mangled booktitles ("Intelligent Vehicles Symposium (IV), 2011 IEEE" → "Proceedings of the 2011 IEEE Intelligent Vehicles Symposium"), `month={june}` — fix before submission. Same spirit as the Google Scholar gotcha above: exports are discovery, not canon.
- **Citation placement + agreement** (Schulzrinne): reference goes right after the author name ("Smith [1] showed"), not sentence-end; "et al." makes the subject plural ("Smith et al. [1] show", not "shows"). Alternative subject: "the foobar protocol [1]".
- **Reference-list consistency** (Schulzrinne): one capitalization scheme (all title case or all sentence case); author names all full (John Doe) or all abbreviated (J. Doe), never mixed; conference entries carry location + month, journal entries volume/issue/pages — a reader must be able to tell journal from conference at a glance; the year appears exactly once per entry; tech reports name the issuing organization; refresh superseded refs (draft → RFC, preprint → camera-ready — the audit's `--show-bibtex` handles this).

## Bib entry hygiene

Field-authoring rules for when you must hand-touch an entry anyway. Sourced from John Owens's (UC Davis) "Common Errors in Bibliographies", <https://www.ece.ucdavis.edu/~jowens/biberrors.html> — worth reading in full once; everything actionable from it is reproduced here and in the style section above.

- **Author names exactly as printed on the paper** — capitalization, diacritics, everything. Initials space-separated: `J. D. Owens`, never `J.D.` (BibTeX reads it as one first name → abbreviated styles emit only "J."). Hyphenated names with lowercase second half: `Wu-{chun} Feng`, `Wen{-mei} Hwu`.
- **Titles as printed; the style enforces case.** Brace only must-capitalize words (`{L}oop` — it's a surname; acronyms, proper names). All-caps titles from publishers: rewrite in title case. Never double-brace the whole title.
- **Months as BibTeX macros, unquoted:** `month = mar`, `month = jun # "\slash " # jul`, `month = "18~" # dec` — lets the style pick "Jan."/"January"/"1/". Include the month when it disambiguates same-year papers.
- **Pages always, en-dash:** `35--49`. Electronic proceedings: `12:1--12:10` (paper 12, 10 pages). Every entry starting at page 1 = fake pages — omit instead.
- **Record a DOI in every entry that has one, even when your style doesn't print it.** An unused `doi` field costs nothing in the PDF and is what makes the entry re-verifiable later — it's the difference between an entry this audit can pin authoritatively and one it can only fuzzy-match. Same argument for keeping `eprint` on preprint-only works.
- **DOI = number only** (`10.1109/IVS.2011.5940539`), never the `dx.doi.org` URL. Don't duplicate the DOI in `url`.
- **URLs in `\url{}`** (`\usepackage{url}`) so they wrap.
