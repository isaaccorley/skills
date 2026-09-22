# Approved visual examples

These eight synthetic examples are the approved house-style references. Open the
closest image before composing a figure. Reuse their visual decisions, adapting
scientific content and physical size to the new paper.

- [Curves](curves.png): paired panels, fine strokes, modest markers, light bands.
- [Grouped bars](bars.png): solid fills, wide bars, small within-group gaps, and compact grouping.
- [Cost–quality scatter](scatter.png): direct labels at 9 pt, ticks at 8 pt, axis labels at 10 pt.
- [Diagram](diagram.png): drawn mechanics, restrained fills, aligned stages.
- [Category comparison](category.png): aligned rows, small markers, compact legend.
- [Distributions](distributions.png): light densities with observations and a compact CDF.
- [Annotated heatmaps](heatmaps.png): readable numbers with contrast-aware dark/white text.
- [Spatial fields](fields.png): close panel packing, shared scales and clear residuals.

For grouped magnitude comparisons, use opaque bars with a small separation within
each group and enough width to avoid excessive space between groups. The example
uses 24 pt bars and a 1.5 pt within-group gap for five groups across 5.5 inches.
Recompute that geometry for a different panel width or group count.

For cost–quality relationships, retain the scatter layout. Sparse direct labels
can be larger than dense chart text. Reposition individual labels to prevent
collisions before reducing font size or changing the chart type.

For annotated heatmaps, use `cell_text_color()` against the actual cell fill.
Use dark text on coral and light cells, and white only on sufficiently dark fills.
The approved example uses 7.2 pt unsigned cell values. Verify at printed size.

All examples contain synthetic data. They do not supply findings, metric limits,
aggregation rules, or uncertainty estimates for a new manuscript. Follow the
caption guide to communicate the new figure's supported takeaway.
