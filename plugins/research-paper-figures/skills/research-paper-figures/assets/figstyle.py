"""Compact serif figure defaults. Copy beside a paper's plotting scripts."""

from pathlib import Path
import warnings

import matplotlib as mpl
import matplotlib.font_manager as fm
from matplotlib.colors import LinearSegmentedColormap, to_rgb

COLORS = {
    'coral': '#ff4f2c', 'brown': '#3b1e1c', 'periwinkle': '#80a0d8',
    'ivory': '#f4f4eb', 'blue': '#4a78b5', 'green': '#3e9c7a',
    'purple': '#9a7ab0', 'ochre': '#c9973f', 'rose': '#b5476b',
    'olive': '#6e8b3d', 'teal': '#17707e', 'indigo': '#5b4b9e',
    'rust': '#a8552a', 'gray': '#6e6e6e', 'soft': '#d8d3c6',
    'ink': '#241a18', 'lightblue': '#a7d0dc', 'lightgreen': '#cff29e',
}
ACCENT = COLORS['coral']
RELATED = COLORS['brown']
INK = COLORS['ink']
SOFT = COLORS['soft']
ORDERED = ('#b8cde2', '#7fa5c8', '#4a78b5', '#24496d')
CATEGORICAL = tuple(COLORS[n] for n in ('coral', 'blue', 'green', 'ochre', 'purple', 'teal'))
WARM = LinearSegmentedColormap.from_list('warm_magnitude', [COLORS['ivory'], ACCENT, RELATED])
SIGNED = LinearSegmentedColormap.from_list('signed_residual', [COLORS['blue'], COLORS['ivory'], ACCENT])
TEXT_WIDTH = 5.5


def apply_style() -> str:
    """Apply the house style and return the actual text font selected."""
    candidates = ('Times New Roman', 'Times', 'TeX Gyre Termes', 'Nimbus Roman', 'Liberation Serif')
    installed = {font.name for font in fm.fontManager.ttflist}
    chosen = next((name for name in candidates if name in installed), 'DejaVu Serif')
    if chosen not in candidates[:2]:
        warnings.warn(f'Figure font fallback: {chosen}; inspect its rendered metrics.', stacklevel=2)
    mpl.rcParams.update({
        'font.family': 'serif', 'font.serif': [chosen], 'font.size': 8,
        'mathtext.fontset': 'cm', 'text.color': INK,
        'axes.labelcolor': INK, 'axes.edgecolor': INK,
        'axes.labelsize': 9, 'axes.titlesize': 8.4, 'axes.titleweight': 'bold',
        'axes.spines.top': False, 'axes.spines.right': False, 'axes.linewidth': 0.6,
        'axes.prop_cycle': mpl.cycler(color=CATEGORICAL), 'axes.axisbelow': True,
        'axes.grid': True, 'axes.grid.axis': 'y',
        'grid.color': SOFT, 'grid.linewidth': 0.35,
        'xtick.color': INK, 'ytick.color': INK,
        'xtick.labelsize': 7, 'ytick.labelsize': 7,
        'xtick.direction': 'out', 'ytick.direction': 'out',
        'xtick.major.width': 0.4, 'ytick.major.width': 0.4,
        'xtick.major.size': 2.5, 'ytick.major.size': 2.5,
        'lines.linewidth': 0.9, 'lines.markersize': 3,
        'legend.fontsize': 7, 'legend.frameon': False,
        'legend.handlelength': 1.6, 'legend.handletextpad': 0.4,
        'legend.columnspacing': 1.2, 'legend.labelspacing': 0.2,
        'figure.facecolor': 'white', 'axes.facecolor': 'white',
        'savefig.facecolor': 'white', 'savefig.transparent': False,
        'figure.dpi': 150, 'savefig.dpi': 300,
        'pdf.fonttype': 42, 'ps.fonttype': 42, 'svg.fonttype': 'none',
    })
    return chosen


def tint(color: str, strength: float) -> tuple[float, float, float]:
    """Mix a color with white; strength 0 is white and 1 is the original."""
    if not 0 <= strength <= 1:
        raise ValueError('Tint strength must be between zero and one.')
    return tuple(1 - strength * (1 - channel) for channel in to_rgb(color))


def export(fig, stem: str | Path, crop: bool = False) -> list[Path]:
    """Export a vector PDF/SVG pair; retain physical canvas size by default."""
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    paths = [stem.with_suffix('.pdf'), stem.with_suffix('.svg')]
    for path in paths:
        fig.savefig(path, bbox_inches='tight' if crop else None)
    print(f'Figure: {stem}; source width {fig.get_figwidth():.3f} in; crop={crop}')
    return paths


def cell_text_color(background) -> str:
    """Choose dark or white annotation text from actual sRGB contrast."""
    def luminance(color):
        channels = to_rgb(color)
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))

    back = luminance(background)
    def contrast(color):
        fore = luminance(color)
        return (max(back, fore) + 0.05) / (min(back, fore) + 0.05)

    choice = max((INK, 'white'), key=contrast)
    return choice if contrast(choice) >= 4.5 else max(('black', 'white'), key=contrast)
