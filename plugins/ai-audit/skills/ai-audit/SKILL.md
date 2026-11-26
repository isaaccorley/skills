---
name: ai-audit
description: Flag AI-generated language patterns in academic manuscripts (flagged vocabulary, throat-clearing, structural tells, choppy prose, word-level register, punctuation signatures) so authors can fix them before a reviewer or detector does. Works on any .tex or .md manuscript. Optionally accepts a Style Profile to match rewrites to the author's voice.
---

# AI Language Audit

Audit the manuscript at `$ARGUMENTS` for writing patterns that flag as AI-generated. If no path is given, ask for one.

Read the file, then audit the abstract, headings and captions, then each section (Introduction, Methods, Results, Discussion, Conclusions) one at a time. For each section, apply all categories below. After all sections, provide a summary count of flags by category and confidence level.

Focus on **patterns and density**, not isolated occurrences. A word appearing once is normal; the same construction in every paragraph is a tell.

**All rewrites must match the author's voice.** If a Style Profile is provided below, use it as the target. If not, infer register and sentence style from the manuscript itself; do not produce generic academic prose.

**Protect the flow.** A fix must leave the paragraph at least as easy to follow as before. Keep the links between sentences ("because", "so", "but"), and add one where the relation is left for the reader to guess. Split a sentence only when it exceeds about 40 words, carries two unrelated claims, or a rule below asks for it. When in doubt, flag without rewriting.

**Keep the function words.** A fix may add words. It must not shorten a sentence by dropping an optional "that" or stacking nouns: language models produce more of these compressed forms than people do, and they make text harder to read (Clark, Martin and Mahowald 2026, arXiv:2610.29162). Cutting throat-clearing, deleting a restating sentence or merging staccato sentences is not compression.

---

## Style Profile (optional: fill in or delete)

Calibrate this section from 2 or 3 of the author's prior publications. Read them and note:

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
| robust (as a bare quality adjective: "a robust assessment") | Vague quality claim | reliable, strong, rigorous; or say what it is robust to |
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
| play(s) a role / play(s) a key role (about the paper's own result) | Avoids naming the causal effect | name the effect: "affects", "determines", "matters for" |
| consequently (sentence opener) | Mechanical sequential marker | "so" inline, "therefore" inline, or restructure |
| finally (as a lone sequence marker, not closing an explicit First/Second list) | Ordinal scaffold; the reader sees it's last | cut |
| it is worth investigating / worth exploring | Vague aspiration variant | name what should be investigated and why |
| not merely X but Y / not X per se, but Y | False contrast | state Y; add X only if a reader would assume it |
| ..., confirming / underscoring / highlighting / revealing that ... (participial tail; not "indicating that") | Tail claims more than the clause shows | a separate clause with its own subject ("which shows that"), or cut |
| represents a shift / a step change / actionable / frontier (about the paper's own work) | Importance inflation | state the result and let the reader judge |

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
- Limitation apologies ("These results are based on...", "It should be emphasized that these findings are limited to...") in the Abstract, or more than one such sentence in the Conclusions (one closing scope sentence is normal)
- Any sentence that announces what the paper is about to do instead of doing it. Exceptions: Introduction roadmaps, one roadmap sentence in a long Discussion, and a one-sentence opener of a list or a Limitations subsection ("Several factors contribute.").

## Category C: Structural tells

Flag these patterns:

- **Rule of Three compulsion**: every list or argument decomposes into exactly 3 items. Flag a triad only when two items overlap, one item is vaguer than the others, or it closes a future-work or implication sentence. Lists of distinct causes, aspects or examples are not padding.
- **Metronomic cadence**: 5+ consecutive sentences within ±5 words of each other. Check per paragraph.
- **Self-repetition across sections**: a sentence recycled between sections (typically the Discussion opening and the Conclusions), or the same result reported three or more times. Restating the main finding in Abstract and Conclusions is normal; flag verbatim copies longer than about 15 words.
- **Mirror structure**: subsections that follow the same rhetorical template (question, punchy answer, evidence, hedge). Flag only when four or more share the template, or when the answer is a fragment.
- **Verbal tics**: the same hedge or frame phrase repeated across sections ("One reading is that" opening each interpretation). Keep it where it qualifies a specific claim, cut the rest. Standard connectives ("therefore", "by contrast") are not tics.
- **Dramatic fragment answers**: "Not X." as a standalone sentence answering a setup question. Limit: once per paper.
- **Uniform paragraph length**: all paragraphs approximately the same word count (~150-200 words each). Vary length by function.
- **Synonym cycling**: 3+ synonyms for the same concept within one paragraph to avoid "repetition." In technical writing, consistent terminology is a virtue.
- **Question-format headings**: "Do X outperform Y?" or "What separates the models?" as subsection labels in Results or Discussion. Flag any heading ending in "?" outside of the Introduction's research-question list.
- **Trailing restatement sentences**: a paragraph's final sentence paraphrases its opening claim without adding new information. Test: can the last sentence be deleted without losing content? Do not flag a section-closing sentence that turns the result into a practical implication.
- **Abstract caveats**: more than one sentence of limitations or caveats in the abstract.
- **Parenthetical qualification interrupts**: main clause interrupted by a long (>8 words) aside: "X, while/although Y, is Z." Move the qualification to the front ("Although Y, X is Z") or join with "but". Short parentheticals and definitions at first use are fine.
- **Long subjects** (LOW unless over about 25 words): 16 or more words between the head noun of the subject and its verb, so the reader holds the subject until the verb arrives. Citations, figure references and the usual specification of a dataset or model do not count. Fix: move the modifier in front or give it its own sentence.

## Category D: Nominalization and passive bloat

Flag noun-phrase inflation where a verb would do and the noun phrase hides who acts. A nominal subject that names a measured quantity ("The concentration of gains in F1 indicates ...") is normal scientific prose.

- "the utilization of X" → "using X"
- "is not the determining factor" → "does not determine"
- "the implementation of X" → "we implemented X"
- "the observation that" → "we observed" or just state the observation

## Category E: Punctuation patterns

- Em dashes (the U+2014 character, LaTeX `---`, or a spaced en dash used as a parenthetical dash; not numeric ranges): flag if more than 2 total. Many authors consider them an AI tell; some style guides ban them outright.
- Semicolons: count only those joining clauses (not citation separators or list items). Flag above about 2 per 1,000 words of prose, and any semicolon that starts a new topic or sits in a sentence longer than about 40 words.
- Colon-list sequences: flag if 2+ consecutive paragraphs open with a colon followed by a list.

## Category F: Choppy prose and missing links

The opposite failure, often produced by earlier rounds of AI editing that split every long sentence. Flag:

- **Staccato runs**: 3+ consecutive sentences under about 12 words that state facts without saying how they connect ("The margin is small. Both models detect most sites. The interval includes zero.").
- **Missing link**: a sentence whose relation to the previous one (cause, contrast, consequence, example) the reader must infer.
- **Verdict fragments**: a short sentence that labels a result instead of explaining it ("This is probability drift.") when the explanation is not in the same sentence.

Fix: merge into fewer, longer sentences that state the reasoning. Do not add words beyond the connective and what the merge needs.

## Category G: Numbers and internal labels

- **Number overload**: a Results or Discussion paragraph that re-narrates more than about four values already shown in a table or figure. Numbers that each support their own clause are evidence, not overload. Fix: keep the number that carries the claim, point to the table for the rest.
- **Undefined internal labels**: working names coined during the experiments that a reader of the target journal would not know and the text has not defined ("ladder", "arm", "window H"). Search the whole manuscript for a definition before flagging. Fix: the plain description, or flag for the author to define once. In the abstract and captions, flag any such name: a reader who has read only the abstract must understand every sentence.
- **Terminology drift**: two names for the same referent in one section, or a defined term replaced elsewhere by a synonym ("recall" where the text defined "detection rate"). Fix: the defined term. Count once per term pair. (Synonym cycling inside one paragraph is C.)

## Category H: Word-level register

These tells sit in single words and short phrases, which the sentence-shape checks above miss. Check every sentence of the abstract, headings, captions and section openings, and search the body for the patterns below.

- **Anthropomorphic verbs for inanimate subjects**: a verb of intention or cognition the subject cannot have (a model "knows" or "wants", a design "intends", a section "decides"), or another action it cannot do in any standard technical sense (a signal "survives"). Language models write these far more often than people do (Clark et al. 2026). Fix: the plain verb, or the people who act ("in Section 6 we refit"). Test: would a reviewer in the field write this verb with this subject? Verbs the field's papers already give to methods and data (a model learns, a sensor detects, the results suggest or indicate), reporting verbs ("Table 3 shows") and the verbs of software ("the function returns") are fine. When unsure, report LOW.
- **Coined compound labels**: hyphenated or stacked nouns the field does not use ("label budget"). Flag a compound when a reader cannot rebuild its meaning from its parts, or when three or more nouns are stacked without a preposition. A transparent compound of field words, explained once, is fine.
- **Numbers without their quantity**: "keeps 0.53", "adds 0.05" where the metric is not named in the same sentence or earlier in the paragraph. Fix: "an F1 of 0.53"; naming the metric once per paragraph is enough. Write "percentage points", not "points", for differences in percent.
- **Elliptic comparisons and dangling referents**: "whereas the embeddings are not", "detection does", "improves model X" for "improves the accuracy of model X". Fix: repeat the verb and object, or split into two sentences. Do not flag a pro-form resolved in the same sentence.
- **Idioms and spoken phrasing**: idioms whose literal reading is false or that hide a quantity ("is not free", "unlocks gains"), and conversational phrases ("the makers of", "fed it"). Fix: the literal statement. Dead metaphors standard in scientific English ("bottleneck", "trade-off") are fine.
- **Dropped optional "that"** (LOW): object relative and complement clauses without "that" are normal English. Flag only when two fall in one sentence or when the reader first misparses the sentence ("we found the classes the model confuses overlap"). Report as one pattern.

Count each flag once: a term the reader must look up is G; a term clear from its words but unused in the field is H. Otherwise, count it under the category whose fix it needs.

## Do NOT flag

- Standard academic transitions used once or twice ("however", "in contrast", "yet")
- Legitimate hedging on genuinely uncertain claims (single site, overlapping CIs, limited sample, single seed)
- Discipline-standard terms in their technical sense, and phrasing that is normal in the target field's published papers. When unsure, report it once as a LOW pattern, not per occurrence.
- Normal paper structure phrases used sparingly ("We contribute", "This paper presents")
- **Protected terms and passages**: vocabulary or sentences the author has decided to keep (a glossary next to the manuscript, or a list passed with the request). List them at the top of the report.

---

## Reporting rules

Keep the report short enough to act on; more than about 50 flags on a full paper is too many.

- **One flag per pattern.** A pattern is one word or one construction. Report it once with every line number and one example fix.
- **HIGH flags in full; LOW flags capped** at about 15 per paper, ranked by position (abstract, headings, captions and section openings first, then the body). Summarise the rest as one line per category.
- Audit a frozen copy and quote line numbers of the file as it was when the audit started.
- **Factual mismatches are not flags.** A sentence that its own paper contradicts (a number that differs between sections, a result true for one model written as true for all) goes under "Content notes" after the flags.

## Output format

For each flag:

- **[Original]** the sentence (with section reference if applicable); for a pattern, all line numbers
- **[Category]** which rule (A-H) and one-line reason
- **[Fix]** a rewrite, "[cut]" if the sentence should be deleted, or "[no fix]" when the author should decide
- **[Confidence]** HIGH (a reviewer or detector would notice) or LOW (debatable)

After all sections, provide:

```
## Summary
- Category A (flagged terms): N flags (H high, L low)
- Category B (throat-clearing): N flags
- Category C (structural tells): N flags
- Category D (nominalization): N flags
- Category E (punctuation): N flags
- Category F (choppy prose): N flags
- Category G (numbers and labels): N flags
- Category H (word-level register): N flags
- Total: N flags to address (patterns counted once)
- Content notes: N
```

Before reporting, check every fix: it keeps the claim of the original (no merging into a different claim, no generalising beyond the evidence), does not swap one flagged word for another of the same kind, and passes F (no staccato run), H (no anthropomorphic verb, no dropped "that", no noun stack) and the long-subject rule. A fix that fails one of these is not a fix.
