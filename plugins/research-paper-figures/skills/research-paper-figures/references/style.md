# House style

## Color and typography

| Role | Value |
| --- | --- |
| Primary emphasis | coral `#FF4F2C` |
| Related variant or secondary emphasis | brown `#3B1E1C` |
| Calm comparison | blue `#4A78B5`, periwinkle `#80A0D8` |
| Other categories | green `#3E9C7A`, ochre `#C9973F`, purple `#9A7AB0`, teal `#17707E` |
| Structural gray | `#D8D3C6` |
| Pale local fill | ivory `#F4F4EB` |
| Text/axes | warm `#241A18` in Python; neutral `#1A1A1A` in TikZ |
| Ordered four-step ramp | `#B8CDE2`, `#7FA5C8`, `#4A78B5`, `#24496D` |

These roles are generic. Brown need not mean teachers, coral need not mean a
neural model, and blue need not mean a spatial holdout. Establish meanings for
the new paper and keep them consistent. A signed scale can use blue–ivory–coral
around a meaningful center. A nonnegative magnitude can use ivory–coral–brown.
Do not force brand colors onto RGB imagery or quantities with established scales.

Use Times New Roman/Times in Python; the helper reports substitutes. Use `ptm`
for TikZ text without resetting the document's body font. Python math uses `cm`.
Text is compact, dark, and mostly regular weight. Bold is for short panel headings.

## Geometry and strokes

- Reference full width: 5.5 in. This is a default, not a universal venue width.
- Paired panels: each `0.485\linewidth`, with flexible space between them.
- Compact axes: 1.75 in tall; hero comparisons: 2.3 in; plot beside table: 1.5 in.
- Bottom/left axes only, 0.5–0.6 pt stroke. Outward ticks, 0.4 pt stroke.
- Data lines 0.9 pt; primary curve 1.1 pt. Circle radius ~1.5 pt in TikZ,
  marker diameter ~3 pt in Python. Open squares/circles distinguish comparisons.
- Faint major grid, 0.35 pt, on the metric axis only. Reference line 0.6 pt.
- Chart labels 9 pt, ticks 7 pt, legends 7 pt. Dense category panel headings
  8.4 pt bold, labels 7.6 pt, ticks 6.1 pt, legend 7.2 pt.
- One shared legend for comparable panels. No frame; compact rows. A horizontal
  legend strip can use thin rules above and below, with open sides.
- For a few separated curves, direct labels are often clearer than a legend.
  Place them against the new values, not copied coordinates from another plot.

Prefer simple margins with explicit space for axis labels and legends. Shrinking
text is the last response to a crowded composition. Adjust the chart, shorten
labels, wrap names, or split the figure first. Avoid heavy boxes, shadows, large
rounded cards, enormous markers, background tints, and unexplained decorations.

## Page and export

Use a short bold takeaway first, then its interpretation and necessary measurement
facts. The reader should learn what to notice and why it matters, rather than
read a restatement of visible values or axis labels. This also applies to tables. Captions need no fixed word count. The first sentence can identify a
schematic instead of making a results claim. Keep panels close enough to read as
a unit and align their plot areas, not merely their file edges.

`export()` writes PDF/SVG at the source canvas size by default. `crop=True` is
useful for tightly packed figures but changes the PDF's physical width. Measure
with `pdfinfo`; account for the inclusion scale. Raster layers export at 300 dpi.
Render at final width and enlarged size to check readability and defects separately.

## Annotated heatmaps

Cell values must remain readable at paper width. Use `cell_text_color()` against
an actual cell's colormap color; it compares sRGB contrast after linearization.
Do not use a threshold on raw RGB brightness: it selects white too early on
coral, making numbers difficult to read. Dark text suits coral/light cells;
white is reserved for genuinely dark fills. Use at least 7 pt for dense
unsigned cell values, and verify them in the exported figure. Signed values may
need a wider cell before they can support the same size.

## Bars and sparse scatter labels

Use solid fills for grouped bars. Avoid pale or transparent-looking bar interiors;
reserve translucent fills for uncertainty bands or density overlays. Make bars
wide enough that the gap between groups does not dominate the plot. In a 5.5-inch
figure with five two-bar groups, 24 pt bars and a 1.5 pt within-group gap are a
useful starting point. Recompute widths when group count or panel width changes.

For sparse cost–quality scatter plots, retain the relationship on the two axes.
Use direct labels around 9 pt, ticks around 8 pt, and axis labels around 10 pt.
These sparse figures can support larger text than dense comparison matrices.
Move labels around their points before reducing type size or changing chart type.
