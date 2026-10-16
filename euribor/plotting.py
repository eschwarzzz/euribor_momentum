"""Shared chart style: a warm off-white surface, ink greys and four fixed series colours.

The colour of a strategy is the same in every figure: frozen spec blue, ECB rate momentum orange,
long-only green, walk-forward threshold yellow. Text is always ink, never a series colour.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
BAND = ["#cde2fb", "#9ec5f4"]
VIOLET = "#4a3aa7"
STRATEGY_COLOUR = {"Frozen spec": SERIES[0], "Follow-the-ECB": SERIES[1], "Long-only": SERIES[2], "Walk-forward threshold": SERIES[3]}
DISPLAY_NAME = {"Follow-the-ECB": "ECB rate momentum"}

plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.titlecolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
    "text.color": INK, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
})

euro_k = FuncFormatter(lambda v, _: f"€{v / 1000:,.0f}k")
percent = FuncFormatter(lambda v, _: f"{v:.0f}%".replace("-", "−"))
thousands = FuncFormatter(lambda v, _: f"{v:,.0f}")


def display_name(key):
    return DISPLAY_NAME.get(key, key)


def style(ax):
    """Horizontal grid only, no left/top/right spines, no tick marks."""
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_linewidth(1)
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def title(ax, text, size=11, pad=8):
    ax.set_title(text, loc="left", fontsize=size, fontweight="semibold", pad=pad)


def save(fig, path):
    fig.savefig(path)
    plt.close(fig)
    print(path.name, "written")
