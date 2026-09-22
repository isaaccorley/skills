"""Serif category comparison from an already aggregated CSV.

Required columns: panel,method,condition,score,xlabel.
Row order determines panel/method/condition order. The first condition is an
open diamond; later conditions use the source paper's ordered blue fills.
Each panel must contain the same methods/conditions, with one score per cell.
Example: python category-comparison.py results.csv --highlight Proposed --output figs/results
This script does not estimate uncertainty or infer aggregation from raw runs.
"""

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from figstyle import INK, ACCENT, RELATED, ORDERED, apply_style

SPLIT_COLORS = (INK, *ORDERED)


def load(path: Path):
    with path.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    required = {'panel', 'method', 'condition', 'score', 'xlabel'}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f'CSV must contain nonempty rows with {sorted(required)}')
    panels = list(dict.fromkeys(row['panel'] for row in rows))
    methods = list(dict.fromkeys(row['method'] for row in rows))
    conditions = list(dict.fromkeys(row['condition'] for row in rows))
    if len(panels) > 3 or len(conditions) > 5:
        raise ValueError('Template supports up to 3 panels and 5 conditions; recompose for more.')
    values = {}
    labels = {}
    for row in rows:
        key = (row['panel'], row['method'], row['condition'])
        if key in values:
            raise ValueError(f'Duplicate cell: {key}; aggregate runs explicitly first.')
        value = float(row['score'])
        if not np.isfinite(value):
            raise ValueError(f'Nonfinite score: {key}')
        values[key] = value
        if row['panel'] in labels and labels[row['panel']] != row['xlabel']:
            raise ValueError('Each panel must have one consistent xlabel.')
        labels[row['panel']] = row['xlabel']
    for panel in panels:
        for method in methods:
            for condition in conditions:
                if (panel, method, condition) not in values:
                    raise ValueError(f'Missing cell: {(panel, method, condition)}')
    return panels, methods, conditions, values, labels


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--highlight', required=True)
    parser.add_argument('--related', nargs='*', default=[])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--width', type=float, default=5.5)
    parser.add_argument('--height', type=float, default=None)
    args = parser.parse_args()
    panels, methods, conditions, values, labels = load(args.csv)
    if args.highlight not in methods:
        raise ValueError('Highlight must be an actual method name in the CSV.')
    if set(args.related) - set(methods):
        raise ValueError('Related names must be actual method names in the CSV.')
    apply_style()
    # Source is 5.5 x 3.45 in for 18 methods. Keep its typography for new row counts.
    height = args.height or max(2.3, 3.45 + 0.12 * (len(methods) - 18))
    fig, axes = plt.subplots(
        1, len(panels), figsize=(args.width, height), squeeze=False,
        gridspec_kw={'wspace': 0.18}, facecolor='white',
    )
    axes = axes.ravel()
    fig.subplots_adjust(left=0.18, right=0.995, bottom=max(0.2, 0.68 / height), top=0.88)
    for index, (ax, panel) in enumerate(zip(axes, panels, strict=True)):
        ax.spines[['top', 'right']].set_visible(False)
        for name in ['left', 'bottom']:
            ax.spines[name].set_color(INK)
            ax.spines[name].set_linewidth(0.6)
        ax.tick_params(axis='both', colors=INK, width=0.5, length=2.5, labelsize=6.1)
        ax.grid(axis='x', color='#D8D3C6', linewidth=0.45)
        ax.grid(axis='y', visible=False)
        ax.set_axisbelow(True)
        for row, method in enumerate(methods):
            scores = [values[panel, method, condition] for condition in conditions]
            color = ACCENT if method == args.highlight else RELATED if method in args.related else INK
            ax.plot(scores, np.full(len(scores), row), color='#B8B8B8', linewidth=1.15, zorder=1)
            for ci, score in enumerate(scores):
                ax.scatter(
                    score, row, s=27 if method == args.highlight else 19,
                    marker='D' if ci == 0 else 'o',
                    facecolors='white' if ci == 0 else SPLIT_COLORS[ci],
                    edgecolors=color, linewidths=0.7, zorder=2,
                )
            if method == args.highlight:
                ax.axhspan(row - 0.46, row + 0.46, color=ACCENT, alpha=0.08, zorder=0)
        ax.set_yticks(np.arange(len(methods)), methods if index == 0 else [])
        ax.set_ylim(len(methods) - 0.5, -0.5)
        ax.set_title(panel, fontsize=8.4, fontweight='bold', color=INK, pad=5)
        ax.set_xlabel(labels[panel], fontsize=7.6, color=INK, labelpad=3)
        # Limits derive from the new values; never inherit another experiment's metric bounds.
        ax.margins(x=0.12)
        if ax.get_xlim()[0] < 0 < ax.get_xlim()[1]:
            ax.axvline(0, color='#B8B8B8', linewidth=0.55, zorder=0)
        for spine in ax.spines.values():
            spine.set_zorder(3)
    # Share the numeric range when panels use the same metric label.
    for label in set(labels.values()):
        group = [ax for ax, panel in zip(axes, panels, strict=True) if labels[panel] == label]
        bounds = [ax.get_xlim() for ax in group]
        lo, hi = min(bound[0] for bound in bounds), max(bound[1] for bound in bounds)
        for ax in group:
            ax.set_xlim(lo, hi)
    handles = [
        plt.Line2D([], [], marker='D' if i == 0 else 'o', linestyle='', markersize=4,
                   markerfacecolor='white' if i == 0 else SPLIT_COLORS[i],
                   markeredgecolor=INK, markeredgewidth=0.55, label=condition)
        for i, condition in enumerate(conditions)
    ]
    center_x = (axes[0].get_position().x0 + axes[-1].get_position().x1) / 2
    legend = fig.legend(
        handles=handles, ncol=len(conditions), loc='lower center',
        bbox_to_anchor=(center_x, 0), frameon=False,
        fontsize=7.2, handletextpad=0.4, columnspacing=1.2,
    )
    fig.canvas.draw()
    box = legend.get_window_extent().transformed(fig.transFigure.inverted())
    for y in (box.y0 - 0.006, box.y1 + 0.006):
        fig.add_artist(plt.Line2D(
            [box.x0 - 0.01, box.x1 + 0.01], [y, y], transform=fig.transFigure,
            color=INK, linewidth=0.6,
        ))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for ext in ('pdf', 'svg'):
        fig.savefig(args.output.with_suffix('.' + ext), bbox_inches='tight', facecolor='white')
    print(f'Wrote {args.output}.pdf and .svg; measure cropped width before LaTeX inclusion.')
    plt.close(fig)


if __name__ == '__main__':
    main()
