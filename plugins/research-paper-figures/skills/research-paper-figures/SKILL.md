---
name: research-paper-figures
description: "Create publication figures with TikZ/pgfplots or Python using precise serif typography, coral emphasis, warm neutrals, thin axes, compact panels, and integrated LaTeX layouts. Use for research plots, method diagrams, figure restyling, and paper-ready comparisons with new data."
---

# Research paper figures

Use the bundled house style for any paper or dataset. Preserve its typography,
color relationships, stroke weights, and page density; adapt the scientific
content, chart type, dimensions, and layout to the task. User or venue requirements
can override the defaults. No particular model, domain, or experiment is assumed.

Start with the [preferred visual examples](examples/preferred/examples.md) and
read [references/style.md](references/style.md), then the relevant guide:
[charts](references/charts.md), [diagrams](references/diagrams.md), or
[LaTeX layouts](references/latex-layouts.md). For every caption, use
[caption guidance](references/captions.md), including when describing tables.

## Reusable assets

| Task | Starting point |
| --- | --- |
| Python chart | `assets/figstyle.py`: `apply_style()`, `COLORS`, `export()` |
| Native LaTeX chart | `assets/figure-style.tex`: `paperaxis`, `focus`, `comparison` |
| Aligned category comparison | `assets/category-comparison.py`, supplied CSV |
| Drawn method schematic | `assets/method-diagram.tex`, adapt operations and labels |
| Synthetic examples / visual tuning | `scripts/build_gallery.py --output PATH` |

Copy the style file beside the project's figure scripts and use its runtime.
The gallery requires Python 3.10+, the packages in `requirements.txt`, a LaTeX
distribution with pgfplots/standalone, and Poppler's `pdftoppm`.
The gallery scripts demonstrate curve bands, compact solid bars, labeled scatter plots, distributions,
heatmaps, spatial fields, and multi-panel composition. Treat their seeded random
data as test fixtures, never as manuscript results. The bundled examples are
synthetic and do not define the method or domain of a new figure.

## Working sequence

1. Read the new data and identify the plotted quantity, units, aggregation,
   and comparison. Choose a chart that exposes that relationship. Do not inherit
   metric limits or interpretive claims from an example.
2. Read the target paper's width at the insertion point. Without a paper, use
   5.5 in for a full figure and state that assumption. Two paired panels usually
   occupy `0.485\linewidth` each. Use the provided style rather than recreating
   colors and typography from memory.
3. Draw at the intended printed size. Keep serif text, coral emphasis, thin
   structure, small differentiated markers, and compact legends. Use color roles
   consistently across figures, while allowing multiple categories and protocols.
4. Export PDF, plus SVG or a rendered preview. Keep axes and text vector; raster
   data layers are appropriate for images, dense fields, and dense point maps.
5. Compile the actual paper or a harness with the same width. Render and inspect
   both figure and page. Correct overlaps, clipped labels, uneven panel baselines,
   insufficient contrast, tiny text, and awkward caption spacing. Deliver source,
   figure, data provenance, and a ready-to-use LaTeX inclusion/caption.

## Visual and scientific checks

- White page/axes; ivory and warm gray are local fills. Times text; Computer
  Modern math in Python, document math in TikZ. Report font fallback.
- Measure cropping/resizing: `printed font size = source font size × inclusion
  width / exported width`. Aim for 7–9 pt chart text, 6–7 pt dense labels. Do not
  shrink a wide diagram into a narrow column without recomposing it.
- Panel headings are allowed. A figure-wide title belongs in the caption. Lead captions with the supported
  takeaway and its interpretation, not an inventory of rows, axes, or legend items.
  Use panel letters when useful for references, not as mandatory decoration.
- Pair hue with marker, dash, position, or direct labels. Pale accents suit fills;
  they need darker outlines for small markers. No rainbow categorical cycle.
- Distinguish observations, seed means, folds, SD, SE, and confidence intervals.
  Preserve the experiment's aggregation and dependencies. No automatic CI helper
  makes that scientific choice. Name any shown uncertainty in the caption.
- Share limits for genuinely comparable quantities; preserve zero baselines for
  magnitude bars. A heatmap's center, log axis, smoothing, or normalization must
  reflect the data and be documented.
- When a rendered example exposes a reusable layout defect, fix its generator
  and rerun. Do not hand-edit exported graphics as the final solution.
