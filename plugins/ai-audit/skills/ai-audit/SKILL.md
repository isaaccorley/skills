---
name: ai-audit
description: Flag AI-generated language patterns in academic manuscripts — hedging tics, structural tells, flagged vocabulary, and punctuation signatures — so authors can fix them before a reviewer or detector does. Works on any .tex or .md manuscript. Optionally accepts a Style Profile to match rewrites to the author's voice.
---

# AI Language Audit

Audit the manuscript at `$ARGUMENTS` for writing patterns that flag as AI-generated. If no path is given, ask for one.

Read the file, then audit each section (Introduction, Methods, Results, Discussion, Conclusions) one at a time. For each section, apply all categories below. After all sections, provide a summary count of flags by category and confidence level.

Focus on **patterns and density**, not isolated occurrences. A word appearing once is normal; the same construction in every paragraph is a tell.

**All rewrites must match the author's voice.** If a Style Profile is provided below, use it as the target. If not, infer register and sentence style from the manuscript itself — do not produce generic academic prose.

---

## Style Profile (optional — fill in or delete)

Calibrate this section from 2–3 of the author's prior publications. Read them and note:

- **Sentence architecture**: average length, variation, short-vs-long mix.
- **Transitions**: which connectives the author actually uses ("but", "however", "yet"?) vs. avoids.
- **Discussion style**: does the author use bold topic-label paragraphs, numbered subsections, or flowing prose?
- **Conclusions style**: numbered inline findings "(1) ...; (2) ...;" or flowing paragraphs?
- **Vocabulary preferences**: words the author reaches for vs. words they never use.
- **Register**: how blunt or hedged? Willing to make direct claims, or cautious throughout?
- **Punctuation habits**: em-dash frequency, semicolon density, parenthetical style.

If you don't have prior publications to calibrate from, delete this section entirely. The audit categories below work without it; rewrites will just target standard clear academic prose instead of a specific voice.

---

## Category A: Flagged terms

Check for these. Replace with a precise alternative **unless** the term is used in its literal technical sense (e.g., "landscape" in geography, "robust" in statistics, "navigate" in wayfinding):

| Term | Why flagged | Alternatives |
|------|------------|-------------|
| delve | Overused "explore" substitute | examine, investigate, analyze |
| tapestry | Cliché metaphor | network, interplay, system |
| pivotal | Importance inflation | important, significant, central |
| crucial (non-technical) | Same | essential, necessary, critical |
| foster | Vague verb | promote, develop, cultivate |
| showcase | Non-academic register | demonstrate, illustrate, present |
| testament | Cliché | evidence, indicator |
| navigate (non-literal) | Vague | manage, address, handle |
| leverage | Business jargon | use, employ, apply |
| realm | Archaic | domain, field, area |
| embark | Overwrought | begin, start, undertake |
| underscore | Overused emphasis | emphasize, highlight, stress |
| multifaceted | Vague complexity | complex, varied, diverse |
| nuanced (vacuous) | Often empty | subtle, detailed, fine-grained |
| comprehensive (unjustified) | Often unjustified | thorough, extensive, broad |
| robust (non-statistical) | Vague quality claim | reliable, strong, rigorous |
| intricate | Same as multifaceted | complex, detailed, elaborate |
| cornerstone | Cliché metaphor | foundation, basis, core element |
| paradigm (non-technical) | Overused | framework, model, approach |
| synergy | Business jargon | interaction, combined effect |
| holistic | Vague | integrated, whole-system |
| streamline | Non-academic | simplify, optimize |
| cutting-edge | Cliché | recent, advanced, state-of-the-art |
| groundbreaking | Inflation | novel, innovative, original |
| landscape (non-literal) | Vague | field, domain, context |
| furthermore/moreover | AI-rhythm tell when repeated | use at most once total; otherwise restructure |
| bridges/closes the gap | Cliché | (rephrase to say what it actually does) |
| promising direction/avenue | Vague aspiration | (name the specific next step) |
| play(s) a role / play(s) a key role | Avoids naming the causal effect | name the effect: "affects", "determines", "matters for" |
| consequently (sentence opener) | Mechanical sequential marker | "so" inline, "therefore" inline, or restructure |
| finally (as sequence marker) | Ordinal scaffold; the reader sees it's last | cut; or "A last caveat:" if enumeration is intentional |
| it is worth investigating / worth exploring | Vague aspiration variant | name what should be investigated and why |

## Category B: Throat-clearing and scaffolding

Delete or rewrite these. Cut to the actual point:

- "In the realm of..."
- "It is worth noting that..." / "It should be noted that..."
- "It is important to highlight..."
- "We address this gap"
- "These results suggest a concrete recommendation:"
- "This section discusses..." / "The following paragraph examines..."
- "In order to..." (replace with "To...")
- "When it comes to..."
- "It goes without saying that..."
- "We now turn our attention to..."
- "...but should be noted" / "...which should be noted" (end-of-sentence hedge; state the implication or cut)
- "These results are based on..." / "It should be emphasized that these findings are limited to..." when used in the Abstract or Conclusions (limitation apologies belong in Discussion, not in space reserved for findings)
- Any sentence that announces what the paper is about to do instead of doing it (exception: Introduction roadmap sentences are standard)

## Category C: Structural tells

Flag these patterns:

- **Rule of Three compulsion**: every list or argument decomposes into exactly 3 items. Two strong points beat three padded ones. Flag when padding is visible.
- **Metronomic cadence**: 5+ consecutive sentences within ±5 words of each other. Check per paragraph.
- **Self-repetition across sections**: near-identical phrasing recycled between abstract, discussion, and conclusions. The same sentence should not appear twice in different sections.
- **Mirror structure**: every paragraph or subsection follows the same rhetorical template (question, punchy answer, evidence, hedge). Vary the approach.
- **Dramatic fragment answers**: "Not X." as a standalone sentence answering a setup question. Limit: once per paper.
- **Uniform paragraph length**: all paragraphs approximately the same word count (~150-200 words each). Vary length by function: short for emphasis, longer for complex arguments.
- **Synonym cycling**: 3+ synonyms for the same concept within one paragraph to avoid "repetition." In technical writing, consistent terminology is a virtue.
- **Question-format Discussion headings**: "Do X outperform Y?" or "What separates the models?" as subsection labels in Discussion or Results. Academic papers use declarative topic phrases ("Pretraining data composition"), not conversational questions. Flag any bold heading or `\subsection` ending in "?" outside of the Introduction's research-question list.
- **Trailing restatement sentences**: A paragraph's final sentence paraphrases its opening claim without adding new information. Test: can the last sentence be deleted without losing content? If yes, flag it for cutting.
- **Abstract caveats**: More than one sentence of limitations or caveats in the abstract. Abstracts state findings; limitations belong in Discussion. A single brief qualifier is fine; a full caveat sentence is not.
- **Parenthetical qualification interrupts**: Main clause interrupted by a long (>8 words) qualifying aside set off by commas: "X, while/although Y, is Z." Restructure with "but" or split into two sentences. Short parentheticals ("X, as expected, is Y") are fine.

## Category D: Nominalization and passive bloat

Flag noun-phrase inflation where a verb would do:

- "the utilization of X" → "using X"
- "is not the determining factor" → "does not determine"
- "the implementation of X" → "we implemented X"
- "the observation that" → "we observed" or just state the observation
- "plays a pivotal role in" → "affects" or "drives"

## Category E: Punctuation patterns

- Em dashes (— or LaTeX ---): flag if more than 2 total. Many authors consider them an AI tell; some style guides ban them outright.
- Semicolons: flag if more than 2 per 1000 words of prose.
- Colon-list sequences: flag if 2+ consecutive paragraphs open with a colon followed by a list.

## Do NOT flag

- Standard academic transitions used once or twice ("however", "in contrast", "yet")
- Legitimate hedging on genuinely uncertain claims (single site, overlapping CIs, limited sample, single seed)
- Discipline-standard terms in their technical sense
- Normal paper structure phrases used sparingly ("We contribute", "This paper presents")

---

## Output format

For each flag:

- **[Original]** the sentence (with section reference if applicable)
- **[Category]** which rule (A/B/C/D/E) and one-line reason
- **[Fix]** a rewrite, or "[cut]" if the sentence should be deleted
- **[Confidence]** HIGH (a reviewer or detector would notice) or LOW (debatable)

After all sections, provide:

```
## Summary
- Category A (flagged terms): N flags (H high, L low)
- Category B (throat-clearing): N flags
- Category C (structural tells): N flags
- Category D (nominalization): N flags
- Category E (punctuation): N flags
- Total: N flags to address
```
