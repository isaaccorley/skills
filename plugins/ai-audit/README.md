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

Eight categories:

| Category | What it catches | Examples |
|----------|----------------|----------|
| **A: Flagged terms** | Vocabulary that signals AI authorship | "delve", "leverage", "plays a role", "Importantly,", "..., highlighting that" |
| **B: Throat-clearing** | Filler that announces instead of doing | "It is worth noting that...", "In the realm of...", abstract limitation apologies |
| **C: Structural tells** | Patterns in how text is organized | Question-format headings, trailing restatements, synonym cycling, long subjects |
| **D: Nominalization** | Noun-phrase bloat where a verb would do | "the utilization of X" → "using X" |
| **E: Punctuation** | AI-correlated punctuation density | Em-dash overuse, semicolon chains, colons used as connectives |
| **F: Choppy prose** | Short sentences with the links between them removed, often left by earlier AI edits | "The margin is small. Both models detect most sites. The interval includes zero." |
| **G: Numbers and labels** | Number overload, undefined working names, terminology drift | "the ladder" in an abstract, "recall" and "detection rate" for one metric |
| **H: Word-level register** | Single words and phrases the checks above miss | a model that "knows", "keeps 0.53" without the metric, "label budget" |

Every flag comes with a confidence level (HIGH = a reviewer would notice, LOW = debatable) and a proposed rewrite. Each pattern is reported once, with all its line numbers, and LOW flags are capped so the report stays short enough to act on.

Fixes are checked too. Language models tend to fix one tell by adding another kind of hard-to-read text, such as a dropped "that" or stacked nouns, or by changing the claim. The skill checks its own rewrites for both.

## Style Profile (optional)

The skill works out of the box with generic academic prose as the target. For better rewrites, add a **Style Profile** section calibrated from 2–3 of the author's prior publications. The profile describes the author's sentence architecture, transition preferences, vocabulary habits, and punctuation style, so rewrites match their voice instead of producing bland committee prose.

See the Style Profile template in [SKILL.md](skills/ai-audit/SKILL.md) for the format.

## Scope

Works on `.tex` and `.md` manuscripts. Audits section by section (Introduction through Conclusions) and produces a per-flag report with a summary count. Does not modify files; all changes are proposed as rewrites for the author to accept or reject.

## Credits

The flagged-term list draws on widely circulated AI-vocabulary lists. The structural-tell checks (trailing restatements, question-format headings, abstract caveats, parenthetical interrupts) were identified empirically during a week of editing a real MDPI Remote Sensing submission, cross-referencing what manual review caught against what the automated audit missed.

Version 1.1 adds categories F to H and the rules for fixes, from use on remote sensing manuscripts since September 2026. The checks for anthropomorphic verbs, long subjects, stacked nouns and dropped "that" follow Clark, Martin and Mahowald (2026), [Why is AI-generated language so hard to understand?](https://arxiv.org/abs/2610.29162). The false-positive exemptions come from runs on published papers, including two written before language models (Kennedy et al. 2015, Hermosilla et al. 2018). On three Discussion sections (about 8,800 words), 1.1 gave 68 flags with 35% false positives, against 88 flags with 58% for 1.0; the rules behind most of the remaining false positives were then cut or narrowed. Expect some LOW flags on standard phrasing of your field.

MIT licensed.
