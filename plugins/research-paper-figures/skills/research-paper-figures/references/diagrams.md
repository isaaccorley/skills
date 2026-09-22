# Method diagrams

Use `assets/method-diagram.tex` with `assets/figure-style.tex` as a generic drawn
pipeline. Adapt every operation, dependency, and label to the actual method.
Two stages fit training/inference or preparation/analysis, but one stage is fine.

Retain thin warm-gray boxes, 2 pt corner radii, white/pale fills, small Times text,
and restrained coral emphasis. Main flow is 0.55 pt with a 3 pt Stealth tip;
secondary paths 0.4 pt with 2.2 pt tips. Group related or frozen operations with
a dashed enclosure and a white-backed border label. Use type colors for multiple
inputs only when they communicate recurring meaning.

Draw recognizable operations: samples, vector slots, processing layers, merge
nodes, query/output fields. Use brief labels underneath or alongside them. Do not
put explanatory paragraphs inside boxes. Align stage rows and branch endpoints;
keep arrows out of text and use one main reading direction.

Absolute coordinates suit intricate glyphs; relative positioning suits simple
pipelines. State the canvas width and any resizing factor. The generic example is
13.8 cm wide and designed for a 5.5-inch text block. Its labels are 6.5–8 pt.
For a narrow column, stack operations rather than halving all text sizes.

Render the diagram inside its captioned paper context. Inspect tiny math labels,
arrow endpoints, border tags, crossings, and the whitespace between stages.
The synthetic example illustrates visual composition; its operations are not
assumptions about the semantics of a different method.
