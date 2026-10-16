import pandas as pd, numpy as np, matplotlib, os
matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT = os.path.dirname(os.path.abspath(__file__)); R = f"{ROOT}/results"
SURF, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"; S = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"], "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK, "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF})
def style(ax):
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=1); ax.set_axisbelow(True); ax.tick_params(length=0)
P = pd.read_csv(f"{R}/monthly_positions.csv", index_col=0, parse_dates=True); G = pd.read_csv(f"{R}/prior_group_scores.csv", index_col=0, parse_dates=True).loc["2002-01-31":]
ecb = P["BM follow-the-ECB (-sign of DFR 3M change)"].loc["2002-01-31":]; score = G[["R", "I", "S"]].mean(axis=1)
fire = (score.abs() > 0.5) & (np.sign(score) != ecb)
fig, axes = plt.subplots(2, 1, figsize=(12, 7.4), dpi=200, sharex=True, gridspec_kw={"height_ratios": [1.15, 1]})
ax = axes[0]; style(ax)
short = (ecb < 0).astype(int); edges = short.diff().fillna(short.iloc[0])
starts = ecb.index[(edges == 1)]; ends = ecb.index[(edges == -1)]
if short.iloc[0] == 1: starts = starts.insert(0, ecb.index[0])
if len(ends) < len(starts): ends = ends.append(pd.DatetimeIndex([ecb.index[-1]]))
for a, b in zip(starts, ends): ax.axvspan(a, b, color=S[1], alpha=0.10, linewidth=0)
ax.axhspan(-0.5, 0.5, color=GRID, alpha=0.55, linewidth=0)
ax.plot(score.index, score.values, color=S[0], linewidth=2, solid_joinstyle="round", label="R+I+S composite score (mean of clipped z-scores)")
ax.scatter(score.index[fire], score.values[fire], s=34, color=S[2], zorder=5, edgecolor=SURF, linewidth=1.5, label="Override fires (|score| > 0.5 and against the rule)")
ax.axhline(0, color=AXIS, linewidth=1); ax.set_ylim(-3, 2.2); ax.set_ylabel("Score (z-units)", fontsize=9)
ax.set_title("The signal: composite score, dead band, and the months it overrides the ECB rule", loc="left", fontsize=11.5, fontweight="semibold", pad=10)
ax.text(pd.Timestamp("2002-03-31"), 1.95, "orange shading = follow-the-ECB rule is short (last move was a hike); unshaded = rule is long", fontsize=8, color=INK2, va="top")
ax.text(pd.Timestamp("2002-03-31"), -0.45, "dead band ±0.5: rule position kept", fontsize=8, color=MUTED, va="bottom")
ax.legend(frameon=False, fontsize=8.5, loc="lower left")
ax = axes[1]; style(ax)
for g, lab, col in [("R", "Rates / policy", S[0]), ("I", "Inflation", S[1]), ("S", "Sentiment / stress", S[2])]:
    ax.plot(G.index, G[g].values, color=col, linewidth=2, solid_joinstyle="round", label=lab)
ax.axhline(0, color=AXIS, linewidth=1); ax.set_ylabel("Group score (z-units)", fontsize=9); ax.set_ylim(-3.1, 3.1)
ax.set_title("Its three components", loc="left", fontsize=11, fontweight="semibold", pad=8); ax.legend(frameon=False, fontsize=8.5, loc="lower left", ncol=3)
fig.subplots_adjust(left=0.07, right=0.98, top=0.93, bottom=0.05, hspace=0.16); fig.savefig(f"{R}/fig5_signal.png"); plt.close(fig); print("fig5 written")
