# bib-audit

Flags hallucinated references, authors and bib items in a paper, and corrects badly formatted ones.

```bash
/plugin marketplace add isaaccorley/skills
/plugin install bib-audit@isaaccorley-skills
```

Then just ask Claude to audit your references — the skill triggers on its own. Or run the scripts directly, since they're stdlib-only Python with no install step:

```bash
python3 skills/bib-audit/scripts/validate_refs.py refs.bib
```

## Why

Checking a bibliography is a tax reviewers pay for other people's carelessness, and it's a bad use of the scarcest resource in peer review. Now that a plausible-looking DOI costs nothing to generate, "did an LLM write this?" has become a thing reviewers feel obliged to spot-check by hand, forty entries at a time.

So this is built author-first. The goal is that you gate your own submission on it, and reference doubt stops being a category reviewers have to think about. Auditing someone else's paper works and is documented, but that's the fallback, not the point.

## What it catches

Ranked, because these are not the same kind of news and mixing them in one list invites the reader to dismiss the whole thing as pedantry:

- **P1** — the cited work isn't found anywhere. The sentence citing it has no support.
- **P2** — a fabricated identifier, or an invented author. Points at the wrong paper, or credits someone for work they didn't do.
- **P3** — wrong metadata on a real, correctly-identified work. Truncated author lists, preprint-vs-published year drift.
- **P4** — formatting. Single-hyphen page ranges, DOIs stored as URLs, double-braced titles, `J.D.` initials. Mechanical, batch-fixable last.

It also flags the literal string `and others` in `.bib` source. That's valid BibTeX — the `.bst` renders it as "et al." so it never looks broken in the built PDF — which is exactly why it's worth surfacing: a reference manager exporting a real record writes every author, so the phrase means the entry was authored without the full list ever being known.

## Inputs

A `.bib` file, a PDF, or a pasted reference list. The `.bib` path is fully automatic. The PDF path deliberately asks *you* (well, Claude) to read the extracted reference text and emit JSON, rather than running a regex at it — turning a rendered reference list back into fields is a language task, and every false "fabricated" verdict found during development traced to a parsing heuristic, never to a bad API answer.

## The design bias, stated plainly

**A false accusation is worse than a miss.** A missed bad reference is one entry a reviewer might still catch. A false "fabricated" verdict on a correct entry destroys trust in the whole report, and in a review it puts an integrity allegation next to someone's name. So when in doubt the tool downgrades to advisory instead of escalating, and `[LOOKUP FAILED]` is a first-class outcome meaning "re-run this one" rather than a finding.

Worth knowing what that cost in practice. Across roughly 590 references from four bibliographies that are entirely real, development builds of this tool produced hundreds of findings, and every P1/P2 that got hand-verified was the tool's bug rather than the paper's. Genuine findings totalled one hallucinated reference, one wrong DOI, and about ten wrong-author errors. The regression suite in [`tests/`](skills/bib-audit/tests) exists because of that, and it's written accusation-first — most assertions are "this correct entry must NOT be flagged".

Which also means the release gate is *a clean run on known-good bibliographies*, not *finds things*.

## Verify before you accuse

If you're using this in a review, resolve the identifier yourself in a browser first, and report the observation rather than the motive. "Ref [14]'s DOI resolves to a different paper" is checkable and useful; "the authors fabricated citations" is the editor's call, not a reviewer's line item. Anonymized references in a double-blind submission are unresolvable *by design* — the scripts detect those, but flagging one by hand reads as not understanding the review process.

## Tests

```bash
cd skills/bib-audit && python3 -m unittest discover -s tests -v
```

Offline and dependency-free, so it runs when Semantic Scholar is down and when OpenAlex has burned its daily budget. Both happened during development.

## Credits

The formatting and style rules are distilled from John Owens's (UC Davis) [Common Errors in Bibliographies](https://www.ece.ucdavis.edu/~jowens/biberrors.html) and Henning Schulzrinne's (Columbia) writing-style guide. Owens's page is worth reading in full once.

MIT licensed.
