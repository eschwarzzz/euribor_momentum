import pandas as pd, numpy as np, matplotlib, os
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
ROOT = os.path.dirname(os.path.abspath(__file__)); R = f"{ROOT}/results"
SURF, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]     # validated categorical slots 1-5, fixed order
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"], "axes.edgecolor": AXIS, "axes.labelcolor": INK2,
                     "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK, "axes.titlecolor": INK, "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF})
def style(ax):
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_linewidth(1); ax.grid(axis="y", color=GRID, linewidth=1); ax.set_axisbelow(True); ax.tick_params(length=0)

# ---- Figure 1: cumulative P&L, OOS window ----
C = pd.read_csv(f"{R}/daily_pnl_curves.csv", index_col=0, parse_dates=True).loc["2008-01-01":"2026-08-31"]
keys = [("BM long-only 2nd contract", "Long-only (benchmark)"), ("BM follow-the-ECB (-sign of DFR 3M change)", "Follow-the-ECB rule (benchmark)"),
        ("Prior composite, sign (R+M+I+S)", "Macro composite, prior signs"), ("Ridge all factors (a=10), sign", "Macro ridge, walk-forward"), ("PLACEBO ridge on shuffled target", "Placebo (shuffled target)")]
fig, ax = plt.subplots(figsize=(11, 5.6), dpi=200); style(ax)
ends = []
for (k, lab), col in zip(keys, SERIES):
    cum = C[k].cumsum() * 100; ax.plot(cum.index, cum.values, color=col, linewidth=2, solid_joinstyle="round", solid_capstyle="round", label=lab); ends.append((cum.iloc[-1], lab, col))
ax.axhline(0, color=AXIS, linewidth=1)
ax.set_title("Synthetic 3M Euribor future (2nd contract): cumulative P&L, Jan 2008 to Aug 2026", loc="left", fontsize=12, fontweight="semibold", pad=14)
ax.set_ylabel("Basis points of price, one contract, after costs", fontsize=9.5)
ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: f"{v:,.0f}"))
# end labels with simple collision nudging, text in ink (never series color)
ends.sort(key=lambda t: t[0]); ys = [e[0] for e in ends]; yr = ax.get_ylim(); mind = (yr[1] - yr[0]) * 0.045
for i in range(1, len(ys)):
    if ys[i] - ys[i-1] < mind: ys[i] = ys[i-1] + mind
x_end = C.index[-1]
for (v, lab, col), yl in zip(ends, ys):
    ax.annotate(f"{lab}  {v:+,.0f}", xy=(x_end, v), xytext=(12, 0), textcoords="offset points", va="center", ha="left", fontsize=8.5, color=INK2,
                arrowprops=dict(arrowstyle="-", color=AXIS, lw=0.8, shrinkA=0, shrinkB=2) if abs(yl - v) > 1e-9 else None)
    if abs(yl - v) > 1e-9:
        ax.annotate(f"{lab}  {v:+,.0f}", xy=(x_end, v), xytext=(12, (yl - v) / (yr[1] - yr[0]) * ax.get_window_extent().height * 0.72), textcoords="offset points", va="center", ha="left", fontsize=8.5, color=INK2)
ax.legend(loc="upper left", frameon=False, fontsize=8.5, ncol=1); ax.set_xlim(C.index[0], C.index[-1] + pd.DateOffset(days=30))
fig.subplots_adjust(right=0.72, left=0.07, top=0.88, bottom=0.08); fig.savefig(f"{R}/fig1_cumulative_pnl.png"); plt.close(fig)

# ---- Figure 2: Sharpe by factor group (prior-sign vs fitted) ----
Res = pd.read_csv(f"{R}/results_main.csv", index_col=0)
groups = [("R", "Rates / policy"), ("M", "Money supply"), ("D", "Debt holdings"), ("I", "Inflation"), ("S", "Sentiment / political")]
prior = [Res.loc[f"Prior group {g} only", "sharpe"] if f"Prior group {g} only" in Res.index else np.nan for g, _ in groups]
ridge = [Res.loc[f"Ridge group {g} only", "sharpe"] for g, _ in groups]
fig, ax = plt.subplots(figsize=(8.5, 4.6), dpi=200); style(ax); ax.grid(axis="y", visible=False); ax.grid(axis="x", color=GRID, linewidth=1)
ax.spines["bottom"].set_visible(False); ax.spines["left"].set_visible(True); ax.spines["left"].set_color(AXIS)
ypos = np.arange(len(groups))[::-1] * 1.0; h = 0.34
def rbar(ax, y, w, col):
    if np.isnan(w): return
    x0 = min(0, w); width = abs(w)
    if width < 0.04: p = matplotlib.patches.Rectangle((x0, y - h/2), width, h, linewidth=0, facecolor=col)
    else: p = FancyBboxPatch((x0, y - h/2), width, h, boxstyle="round,pad=0,rounding_size=0.06", linewidth=0, facecolor=col, mutation_aspect=0.25)
    ax.add_patch(p)
    ax.text(w + (0.02 if w >= 0 else -0.02), y, f"{w:+.2f}", va="center", ha="left" if w >= 0 else "right", fontsize=8.5, color=INK2)
for yp, pv, rv in zip(ypos, prior, ridge):
    rbar(ax, yp + h/2 + 0.03, pv, SERIES[0]); rbar(ax, yp - h/2 - 0.03, rv, SERIES[1])
ax.set_yticks(ypos); ax.set_yticklabels([n for _, n in groups], fontsize=9.5, color=INK); ax.set_ylim(-0.7, len(groups) - 0.3); ax.set_xlim(-0.15, 0.85)
ax.axvline(0, color=AXIS, linewidth=1)
ax.set_title("Sharpe ratio by factor group, single-group models, 2008 to 2026", loc="left", fontsize=12, fontweight="semibold", pad=12)
ax.set_xlabel("Sharpe ratio (after costs)", fontsize=9.5)
from matplotlib.lines import Line2D
ax.legend(handles=[Line2D([0], [0], color=SERIES[0], lw=6, label="Prior-sign composite (no fitting)"), Line2D([0], [0], color=SERIES[1], lw=6, label="Ridge, walk-forward fitted")], loc="lower right", frameon=False, fontsize=8.5)
fig.text(0.24, 0.03, "Debt holdings has no theory-pinned sign, so only the fitted version exists.", fontsize=8, color=MUTED)
fig.subplots_adjust(left=0.24, right=0.97, top=0.86, bottom=0.19); fig.savefig(f"{R}/fig2_group_sharpe.png"); plt.close(fig)
print("charts written")
