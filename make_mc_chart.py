import pandas as pd, numpy as np, matplotlib, json, os
matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT = os.path.dirname(os.path.abspath(__file__)); R = f"{ROOT}/results"
SURF, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"], "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
                     "text.color": INK, "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF})
def style(ax):
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=1); ax.set_axisbelow(True); ax.tick_params(length=0)
boot = pd.read_csv(f"{R}/mc_bootstrap_sharpe.csv"); nulls = json.load(open(f"{R}/mc_nulls.json"))
fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), dpi=200)
ax = axes[0]; style(ax); bins = np.linspace(-1.0, 1.8, 57)
for k, col in zip(["Long-only", "Follow-the-ECB", "Composite ±1", "Ridge a=10"], SERIES):
    h, e = np.histogram(boot[k], bins=bins, density=True); ax.plot((e[:-1] + e[1:]) / 2, h, color=col, linewidth=2, label=k, solid_joinstyle="round")
ax.axvline(0, color=AXIS, linewidth=1); ax.set_xlabel("Annualised Sharpe of a bootstrapped 224-month path", fontsize=9.5); ax.set_ylabel("Density", fontsize=9.5)
ax.set_title("Sampling uncertainty: 10,000 block-bootstrap paths", loc="left", fontsize=11, fontweight="semibold"); ax.legend(frameon=False, fontsize=8.5)
ax = axes[1]; style(ax)
# null for the composite: block-permuted positions vs the same returns (recomputed here for the histogram)
import sys; sys.path.insert(0, ROOT)
from backtest import COST
P = pd.read_csv(f"{R}/monthly_positions.csv", index_col=0, parse_dates=True); F = pd.read_csv(f"{ROOT}/data/features_monthly.csv", index_col=0, parse_dates=True)
yy = F["y_next"].loc["2008-01-31":"2026-08-31"] * 100; pos = P["Prior composite, sign (R+M+I+S)"].reindex(yy.index).fillna(0).values; T = len(pos); rng = np.random.default_rng(7)
def sh(p):
    p = pd.Series(p, index=yy.index); c = p.diff().abs().fillna(p.abs()) * COST * 100 + p.abs() * 2 * COST * 100 / 3; x = p * yy - c; return x.mean() / x.std() * np.sqrt(12)
nb = int(np.ceil(T / 12)); perm = []
for i in range(5000):
    order = rng.permutation(nb); idx = np.concatenate([np.arange(b * 12, min((b + 1) * 12, T)) for b in order]); perm.append(sh(pos[idx]))
perm = np.array(perm); obs = nulls["Composite ±1"]["observed"]
ax.hist(perm, bins=np.linspace(-1.2, 1.2, 49), color=SERIES[2], alpha=0.35, edgecolor=SURF, linewidth=1, label="No-skill null: composite positions block-shuffled in time")
ax.axvline(obs, color=SERIES[2], linewidth=2); ax.text(obs + 0.03, ax.get_ylim()[1] * 0.92, f"observed {obs:+.2f}\np = {(perm >= obs).mean():.3f}", fontsize=8.5, color=INK2, va="top")
ax.set_xlabel("Annualised Sharpe", fontsize=9.5); ax.set_ylabel("Count of shuffled paths", fontsize=9.5)
ax.set_title("Is the timing luck? 5,000 shuffled position paths", loc="left", fontsize=11, fontweight="semibold"); ax.legend(frameon=False, fontsize=8.5, loc="upper left")
fig.subplots_adjust(left=0.06, right=0.98, top=0.88, bottom=0.14, wspace=0.18); fig.savefig(f"{R}/fig3_montecarlo.png"); plt.close(fig); print("fig3 written")
