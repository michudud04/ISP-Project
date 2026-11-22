"""Shared matplotlib style: one fixed colour per entity, recessive chrome, thin marks.

Colours are assigned by entity and never by rank, so R1 is always blue in every
figure. The first three categorical slots pass all-pairs colour-vision-deficiency
checks; use at most three colours together and move further comparisons into
small multiples.
"""

from __future__ import annotations

import logging

import matplotlib as mpl

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]

PLOT_COLORS = {"R1": CATEGORICAL[0], "S1": CATEGORICAL[1], "S2": CATEGORICAL[2]}
PLOT_LABELS = {"R1": "R1 reference (open field)", "S1": "S1 under PV", "S2": "S2 under PV"}

# Sequential (one hue, light -> dark) and diverging (blue <-> red, grey midpoint)
SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
DIVERGING = ["#184f95", "#3987e5", "#9ec5f4", "#f0efec", "#f4a3a3", "#e34948", "#a32a2a"]


def apply() -> None:
    """Set matplotlib rcParams for every figure in the session."""
    # Font fallback probes DejaVu Sans for a semibold weight it lacks and logs a
    # warning per figure; the title still renders in Segoe UI Semibold.
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "figure.dpi": 110,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
        "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
        "font.size": 9.5,
        "text.color": INK,
        "axes.labelcolor": INK_SECONDARY,
        "axes.titlesize": 11,
        "axes.titleweight": "semibold",
        "axes.titlelocation": "left",
        "axes.titlecolor": INK,
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "grid.linestyle": "-",
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "xtick.labelcolor": INK_SECONDARY,
        "ytick.labelcolor": INK_SECONDARY,
        "axes.prop_cycle": mpl.cycler(color=CATEGORICAL),
        "lines.linewidth": 1.6,
        "lines.markersize": 4,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "figure.titlesize": 12,
        "figure.titleweight": "semibold",
    })
