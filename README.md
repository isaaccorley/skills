# skills

Research-workflow skills for [Claude Code](https://claude.com/claude-code), focused on writing and reviewing academic papers.

## Install

```bash
claude plugin marketplace add isaaccorley/skills
```

Then install whichever you want:

```bash
claude plugin install bib-audit@isaaccorley-skills
```

## What's in here

| Plugin | What it does |
|---|---|
| [`bib-audit`](plugins/bib-audit) | Flags hallucinated references, authors and bib items in a paper, and corrects badly formatted ones. Run it on your own draft before submitting, or on a submission you're reviewing. |
| [`ai-audit`](plugins/ai-audit) | Flags AI-generated language patterns in academic manuscripts (hedging tics, structural tells, flagged vocabulary, punctuation signatures) so you can fix them before a reviewer or detector does. |

## License

MIT. See [LICENSE](LICENSE).
