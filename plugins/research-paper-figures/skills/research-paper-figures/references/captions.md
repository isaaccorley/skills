# Captions that guide the reader

Many readers skim only figures and tables. Write captions for that reader: make
the central takeaway understandable without the surrounding paper. The caption
should guide interpretation, not narrate every axis, row, cell, or legend entry.

## Build the caption around the message

Lead with the supported result or relationship the reader should notice. A short
bold lead is useful, followed by one or two sentences explaining the evidence
and why that observation matters. The lead can identify a method schematic when
there is no empirical finding, but still explain the mechanism or design choice.

Then add only the facts needed to read the evidence correctly: meanings of
unfamiliar encodings, evaluation conditions, aggregation, uncertainty, sample size,
normalization, or a material limitation. These details support the takeaway;
they should not displace it. Do not repeat what clear labels already say.

For multiple panels, connect them into one argument. Explain what the contrast
reveals, then identify panels only where necessary. For tables, state the pattern
across methods/settings and any meaningful exception. Avoid a prose tour of rows,
a list of best numbers, or merely saying that bold denotes best performance.

## Examples of the distinction

A curve caption that only inventories content:

> Accuracy versus training epoch for three methods. Shaded areas show SD.

A caption that guides interpretation, when the data support it:

> **The proposed model reaches the plateau earlier.** Its early training advantage
> narrows as the baselines converge, suggesting that the main benefit is training
> efficiency. Curves show means and ±1 SD over five seeds.

A table caption that only restates the table:

> Results for four models on six datasets. Best results are bold.

A takeaway-first alternative, when supported:

> **The improvement is concentrated in low-data settings.** The proposed model
> leads on the smallest datasets, while larger datasets show little separation
> from the strongest baseline. Scores are means over five matched splits.

A schematic caption can guide without inventing a result:

> **One representation supports several downstream decisions.** Training shares
> the encoder across task heads; inference selects a head while reusing the same
> features. Dashed borders identify components kept fixed during adaptation.

These are examples of reasoning structure, not stock wording or reusable claims.
Read the actual figure/table before choosing a takeaway. Do not claim significance,
causality, generality, or practical importance beyond what the evidence establishes.
Mixed or negative results still deserve a clear message. If the result supports
no stronger claim than equivalence within visible variability, say that plainly.

Before delivery, read only the figure/table and caption. Check whether a reader
can identify the comparison, the main observation, and its limits without finding
an explanation in the body. Keep the caption concise, but do not enforce an
arbitrary word count or remove an essential caveat to make it shorter.
