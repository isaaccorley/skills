# ai-audit

Flags AI-generated language patterns in academic manuscripts so you can fix them before a reviewer or detector does.

```bash
claude plugin marketplace add isaaccorley/skills
claude plugin install ai-audit@isaaccorley-skills
```

Then ask Claude to audit your manuscript and the skill triggers on its own, or invoke it directly with `/ai-audit path/to/main.tex`.

## Why

Reviewers are increasingly screening for AI-generated text, and AI detectors flag patterns that are easy to miss in your own draft: hedging tics ("suggesting potential for"), mechanical transitions ("Consequently,"), structural uniformity (every paragraph the same length, every Discussion heading a question), and vocabulary that no human reaches for unprompted ("delve", "tapestry", "multifaceted"). This skill checks for all of them systematically.

The goal is not to hide AI use (you should disclose it) but to make sure the final text sounds like you wrote it, because you reviewed and edited it until it did.

## What it checks

Five categories, roughly ordered from most to least noticeable:

| Category | What it catches | Examples |
|----------|----------------|----------|
| **A — Flagged terms** | Vocabulary that signals AI authorship | "delve", "leverage", "plays a role", "consequently" (opener), "furthermore" chains |
| **B — Throat-clearing** | Filler that announces instead of doing | "It is worth noting that...", "In the realm of...", abstract limitation apologies |
| **C — Structural tells** | Patterns in how text is organized | Question-format Discussion headings, trailing restatement sentences, metronomic paragraph length, synonym cycling |
| **D — Nominalization** | Noun-phrase bloat where a verb would do | "the utilization of X" → "using X" |
| **E — Punctuation** | AI-correlated punctuation density | Em-dash overuse, semicolon chains, colon-list sequences |

Every flag comes with a confidence level (HIGH = a reviewer would notice, LOW = debatable) and a proposed rewrite.

## Style Profile (optional)

The skill works out of the box with generic academic prose as the target. For better rewrites, add a **Style Profile** section calibrated from 2–3 of the author's prior publications. The profile describes the author's sentence architecture, transition preferences, vocabulary habits, and punctuation style, so rewrites match their voice instead of producing bland committee prose.

See the Style Profile template in [SKILL.md](skills/ai-audit/SKILL.md) for the format.

## Scope

Works on `.tex` and `.md` manuscripts. Audits section by section (Introduction through Conclusions) and produces a per-flag report with a summary count. Does not modify files; all changes are proposed as rewrites for the author to accept or reject.

## Credits

The flagged-term list draws on widely circulated AI-vocabulary lists. The structural-tell checks (trailing restatements, question-format headings, abstract caveats, parenthetical interrupts) were identified empirically during a week of editing a real MDPI Remote Sensing submission, cross-referencing what manual review caught against what the automated audit missed.

MIT licensed.
