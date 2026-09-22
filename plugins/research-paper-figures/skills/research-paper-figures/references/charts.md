# Chart selection and adaptation

| Relationship | Useful starting form | Scientific detail to preserve |
| --- | --- | --- |
| Change across training or scale | curves, optional bands | x units; seed aggregation; interval definition |
| Component ablation | bars or paired point differences | zero baseline for magnitudes; pairing for differences |
| Quality versus cost | scatter, optional frontier | optimization directions; whether lines are guides |
| Methods across categories/conditions | aligned dot-and-line panels | shared method order; comparable scales; condition order |
| Variation across samples | box/violin plus observations | sample unit; density smoothing; quartile convention |
| A matrix or sweep | annotated heatmap | normalization; missing cells; center for signed values |
| Spatial field | raster or contour panels | coordinates; common extent; common scale when comparable |

## Category comparison

`assets/category-comparison.py` accepts a CSV with columns:
`panel,method,condition,score,xlabel`. It requires one finite pre-aggregated score
per cell and the same methods/conditions in every panel. Order of first appearance
sets order. The first condition is an open diamond and later conditions filled
circles in increasing blue darkness. Use this encoding only for ordered conditions.

```sh
python category-comparison.py results.csv --highlight Proposed --related Variant --output figs/results
```

The initial canvas is 5.5 × 3.45 in for 18 rows and three equal-width panels.
Left method names, horizontal gray connectors, darker marker outlines, coral
highlight row at 8% opacity, and a ruled shared legend form the template. Fewer
rows shorten the canvas while preserving room below the axes for labels/legend.
Adjust margins for long names; alter the composition for more than three panels.
Different metrics can have different limits, but the same metric should use
common limits when cross-panel distances are intended to be compared.

## Uncertainty and data

The style does not choose an estimator. Decide what each point and interval
means from the source experiment. A seed-level SD band represents run variation;
a confidence interval concerns an estimate and needs a suitable procedure. A
paired comparison should retain that pairing. Do not synthesize seed-level data
from a published aggregate. Describe any omission or unavailable uncertainty
without inventing observations.

For new values, recompute limits, tick positions, direct labels, frontier membership,
bar baselines, color normalization, and label contrast. Keep style parameters
fixed unless content exposes a real layout problem.

## Executable examples

`scripts/gallery_python.py` and `scripts/gallery_tikz.py` generate several chart
types from seed-controlled synthetic arrays. They demonstrate plotting mechanics
and layout; their claims, limits, ordering, and random data are not defaults for
new research. The gallery is explicitly a visual test, not scientific evidence.
