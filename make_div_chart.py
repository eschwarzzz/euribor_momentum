import pandas as pd, numpy as np, matplotlib, os
matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT = os.path.dirname(os.path.abspath(__file__)); R = f"{ROOT}/results"
SURF, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"; S = ["#2a78d6", "#eb6834", "#1baf7a"]
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"], "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK, "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF})
def style(ax):
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=1); ax.set_axisbelow(True); ax.tick_params(length=0)
M = pd.read_csv(f"{R}/divergence_monthly.csv", index_col=0, parse_dates=True)
fig, axes = plt.subplots(2, 1, figsize=(11, 6.8), dpi=200, sharex=True)
ax = axes[0]; style(ax)
ax.bar(M.index, M["share_disagree"] * 100, width=26, color=S[0], linewidth=0)
ax.set_ylabel("% of 44 paths against the ECB rule", fontsize=9); ax.set_ylim(0, 100)
ax.set_title("Where the strategy paths diverge from follow-the-ECB, and what the composite earned by diverging", loc="left", fontsize=11.5, fontweight="semibold", pad=10)
ax = axes[1]; style(ax)
rel = pd.read_csv(f"{R}/divergence_attribution.csv", index_col=0, parse_dates=True)["rel_pnl_bp"].reindex(M.index).fillna(0).cumsum()
ax.plot(rel.index, rel.values, color=S[1], linewidth=2, solid_joinstyle="round"); ax.axhline(0, color=AXIS, linewidth=1)
ax.set_ylabel("Composite minus ECB rule, cumulative bp", fontsize=9)
for d, lab, dy in [("2008-10-31", "Oct 2008: long into the cuts", 40), ("2011-10-31", "2011: long through the two hikes", 40), ("2022-02-28", "late 2021: short before the first hike", 22), ("2024-03-31", "2023-24: long a year too early", -60), ("2025-04-30", "2024-25: short into the cuts", -60)]:
    t = pd.Timestamp(d); v = rel.loc[:t].iloc[-1]
    ax.annotate(lab, xy=(t, v), xytext=(0, dy), textcoords="offset points", ha="center", fontsize=8, color=INK2, arrowprops=dict(arrowstyle="-", color=AXIS, lw=0.8))
fig.subplots_adjust(left=0.08, right=0.98, top=0.92, bottom=0.06, hspace=0.12); fig.savefig(f"{R}/fig4_divergence.png"); plt.close(fig); print("fig4 written")
