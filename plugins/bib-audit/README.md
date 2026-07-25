# bib-audit

Flags hallucinated references, authors and bib items in a paper, and corrects badly formatted ones.

```bash
/plugin marketplace add isaaccorley/skills
/plugin install bib-audit@isaaccorley-skills
```

Then ask Claude to audit your references and the skill triggers on its own. Or run the scripts directly, since they're stdlib-only Python with no install step:

```bash
python3 skills/bib-audit/scripts/validate_refs.py refs.bib
```

## Why

Now that a plausible-looking DOI costs nothing to generate, "did an LLM write this?" has become something reviewers feel obliged to spot-check by hand, forty entries at a time. Run this on your own draft before submitting and nobody has to.

## Inputs

A `.bib` file, a PDF, or a pasted reference list. The `.bib` path is fully automatic. For a PDF, Claude reads the extracted reference text and writes out the fields, since turning a rendered reference list back into structured data is a language task rather than a regex one.

## What it catches

Findings come out ranked, worst first:

- **P1** — the cited work isn't found anywhere, so the sentence citing it has no support.
- **P2** — a fabricated identifier, or an invented author. Either points at the wrong paper or credits someone for work they didn't do.
- **P3** — wrong metadata on a real, correctly-identified work. Truncated author lists, preprint-vs-published year drift.
- **P4** — formatting. Single-hyphen page ranges, DOIs stored as URLs, double-braced titles, `J.D.` initials.

Every entry is resolved against Crossref, arXiv, DataCite and Semantic Scholar, and `--show-bibtex` gives you the publisher's own BibTeX to paste in place of a bad entry.

It also flags the literal string `and others` in `.bib` source. That's valid BibTeX and the `.bst` renders it as "et al.", so it never looks broken in the built PDF, but a reference manager exporting a real record writes every author.

When the evidence is thin the tool reports advisory `[CHECK]` rather than escalating, and `[LOOKUP FAILED]` means an API was unreachable, not that anything is wrong with the reference.

## Using it in a review

Resolve the identifier yourself in a browser first, and report the observation rather than the motive. "Ref [14]'s DOI resolves to a different paper" is checkable and useful; "the authors fabricated citations" is the editor's call. Anonymized references in a double-blind submission are unresolvable by design, and the scripts detect those.

## Optional environment variables

Read from the environment only, never as CLI flags.

| Variable | Why |
|---|---|
| `BIB_AUDIT_MAILTO` | Joins Crossref's polite pool. Anonymous clients get throttled harder across a few hundred entries. |
| `S2_API_KEY` | Authenticates Semantic Scholar, which is the only source that resolves a paper with no DOI and no arXiv ID. [Request one here.](https://www.semanticscholar.org/product/api) |

## Tests

```bash
cd skills/bib-audit && python3 -m unittest discover -s tests
```

Offline and dependency-free.

## Credits

The formatting and style rules are distilled from John Owens's (UC Davis) [Common Errors in Bibliographies](https://www.ece.ucdavis.edu/~jowens/biberrors.html) and Henning Schulzrinne's (Columbia) writing-style guide. Owens's page is worth reading in full once.

MIT licensed.
