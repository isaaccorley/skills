# bib-audit

Flags hallucinated references, authors and bib items in a paper, and corrects badly formatted ones.

```bash
/plugin marketplace add isaaccorley/skills
/plugin install bib-audit@isaaccorley-skills
```

Then ask Claude to audit your references and the skill triggers on its own.

## Without Claude Code

The scripts are plain Python 3.10+ with no dependencies, so nothing about them is Claude-specific. Clone and run:

```bash
git clone https://github.com/isaaccorley/skills.git
cd skills/plugins/bib-audit/skills/bib-audit
python3 scripts/validate_refs.py path/to/refs.bib
```

On a bibliography with a fabricated DOI, an invented co-author and some formatting debt, that prints:

```
[CHECK]      vaswani2017  (arxiv) -- preprint vs published differs
    - author count 2 (bib) vs 8 (api); bib=['Vaswani, Ashish', 'Shazeer, Noam']
[FABRICATED] fake2023: doi:10.1234/jmlr.2023.99999 resolves to no paper
    - the identifier in the entry is fake; re-resolve from the title
[MISMATCH]   ronneberger2015  (crossref:doi)
    - authors in bib but NOT in api (invented?): ['bogus']

RANKED FINDINGS (11 across 4 references)
Start here: Fabricated identifier or invented author  (2xP2, 5xP3, 4xP4)
```

Exit status is 1 when anything is fabricated or mismatched and 0 on a clean file, so it drops straight into CI:

```yaml
- name: Audit bibliography
  run: python3 scripts/validate_refs.py paper/refs.bib
```

To fix an entry, ask for the publisher's own BibTeX and paste it over yours. Your citation key is preserved:

```bash
python3 scripts/validate_refs.py refs.bib --key ronneberger2015 --show-bibtex
```

```
@inbook{ronneberger2015, title={U-Net: Convolutional Networks for Biomedical Image Segmentation},
  DOI={10.1007/978-3-319-24574-4_28}, booktitle={Medical Image Computing and
  Computer-Assisted Intervention – MICCAI 2015}, publisher={Springer International
  Publishing}, author={Ronneberger, Olaf and Fischer, Philipp and Brox, Thomas},
  year={2015}, pages={234–241} }
```

And to find the identifier for an entry that doesn't have one:

```bash
python3 scripts/lookup_id.py "Decoupled Weight Decay Regularization" --author Loshchilov
python3 scripts/lookup_id.py --arxiv-id 1711.05101
```

## With Codex, Copilot or Cursor

The PDF path wants a model to read the extracted reference text and write out the fields, since turning a rendered reference list back into structured data is a language task. Any coding agent can do that part. Point yours at [`SKILL.md`](skills/bib-audit/SKILL.md) from whichever instruction file it reads:

```bash
# Codex and anything else following the AGENTS.md convention
echo "For bibliography and citation work, follow skills/bib-audit/SKILL.md." >> AGENTS.md

# GitHub Copilot
mkdir -p .github
echo "For bibliography and citation work, follow skills/bib-audit/SKILL.md." \
  >> .github/copilot-instructions.md

# Cursor
mkdir -p .cursor/rules
printf -- '---\nglobs: ["**/*.bib","**/*.tex"]\n---\nFollow skills/bib-audit/SKILL.md.\n' \
  > .cursor/rules/bib-audit.mdc
```

The agent then does the extraction step and hands the JSON to `scripts/audit_refs.py`. The `.bib` path needs no model at all.

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
