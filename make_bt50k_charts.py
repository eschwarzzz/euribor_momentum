"""Charts for the EUR 50,000 account backtest. Full window: fig6 equity and drawdown, fig7 signal / volatility / contracts / margin, fig8 Monte Carlo.
Last five years (fresh account from Sep 2021): fig9 account page, fig10 Monte Carlo."""
import pandas as pd, numpy as np, matplotlib, json, os
matplotlib.use("Agg"); import matplotlib.pyplot as plt; from matplotlib.ticker import FuncFormatter; from matplotlib.backends.backend_pdf import PdfPages
ROOT = os.path.dirname(os.path.abspath(__file__)); R = f"{ROOT}/results"
SURF, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"; S = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]; BAND = ["#cde2fb", "#9ec5f4"]
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"], "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
                     "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF})
def style(ax):
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=1); ax.set_axisbelow(True); ax.tick_params(length=0)
def title(ax, t, size=11): ax.set_title(t, loc="left", fontsize=size, fontweight="semibold", pad=8)
keur = FuncFormatter(lambda v, _: f"€{v/1000:,.0f}k"); pct = FuncFormatter(lambda v, _: f"{v:.0f}%".replace("-", "−"))
COL = {"Frozen spec": S[0], "Follow-the-ECB": S[1], "Long-only": S[2], "Walk-forward threshold": S[3]}; NAME = {"Follow-the-ECB": "ECB rate momentum"}; dn = lambda k: NAME.get(k, k)       # colour follows the strategy in every figure
P = pd.read_csv(f"{R}/monthly_positions.csv", index_col=0, parse_dates=True); G = pd.read_csv(f"{R}/prior_group_scores.csv", index_col=0, parse_dates=True)
ECB = P["BM follow-the-ECB (-sign of DFR 3M change)"]; SCORE = G[["R", "I", "S"]].mean(axis=1)
cont = pd.read_csv(f"{ROOT}/data/euribor_futures_continuous.csv", index_col=0, parse_dates=True); V60 = cont["chg1"].rolling(60).std() * np.sqrt(252) * 100; VB = 0.7 * V60 + 0.3 * V60.expanding(250).mean()
def load(tag):
    return dict(d=pd.read_csv(f"{R}/{tag}_daily.csv", index_col=0, parse_dates=True), m=pd.read_csv(f"{R}/{tag}_monthly.csv", index_col=0, parse_dates=True), E=pd.read_csv(f"{R}/{tag}_equity_curves.csv", index_col=0, parse_dates=True),
                V=pd.read_csv(f"{R}/{tag}_variants.csv", index_col=0), mc=json.load(open(f"{R}/{tag}_mc.json")), B=pd.read_csv(f"{R}/{tag}_bootstrap.csv"), fan=pd.read_csv(f"{R}/{tag}_bootstrap_fan.csv"),
                perm=pd.read_csv(f"{R}/{tag}_null_perm.csv")["perm_sharpe"].values)
FULL = load("bt50k"); FIVE = load("bt50k_5y")

# ---------- fig6: equity and drawdown, full window ----------
E = FULL["E"]; fig, axes = plt.subplots(2, 1, figsize=(12, 7.2), dpi=200, sharex=True, gridspec_kw={"height_ratios": [2.4, 1]})
ax = axes[0]; style(ax)
for k in ["Long-only", "Follow-the-ECB", "Walk-forward threshold", "Frozen spec"]:
    ax.plot(E.index, E[k].values, color=COL[k], linewidth=2.2 if k == "Frozen spec" else 1.6, solid_joinstyle="round", label=dn(k))
ends = E.iloc[-1].sort_values(); ypos = ends.copy()
for i in range(1, len(ypos)):
    if ypos.iloc[i] - ypos.iloc[i - 1] < 13000: ypos.iloc[i] = ypos.iloc[i - 1] + 13000
for k in ends.index: ax.text(E.index[-1] + pd.offsets.Day(60), ypos[k], f"{dn(k)}  €{ends[k]/1000:,.0f}k", fontsize=8.5, color=INK2, va="center")
ax.axhline(50000, color=AXIS, linewidth=1); ax.yaxis.set_major_formatter(keur); ax.set_xlim(E.index[0], E.index[-1] + pd.offsets.Day(1250)); ax.set_xticks(pd.to_datetime([f"{y}-01-01" for y in range(2008, 2027, 2)])); ax.set_xticklabels(range(2008, 2027, 2)); ax.legend(frameon=False, fontsize=8.5, loc="upper left", ncol=4)
title(ax, "€50,000 account, 10% volatility target, January 2008 to August 2026 (after costs, synthetic prices)", 11.5)
ax = axes[1]; style(ax); eq = E["Frozen spec"]; dd = (eq / eq.cummax() - 1) * 100
ax.fill_between(dd.index, dd.values, 0, color=S[0], alpha=0.25, linewidth=0); ax.plot(dd.index, dd.values, color=S[0], linewidth=1.2)
ax.yaxis.set_major_formatter(pct); t0 = dd.idxmin(); ax.set_ylim(dd.min() * 1.12, 0.5); ax.annotate(f"−{-dd.min():.1f}%, {t0:%b %Y}", (t0, dd.min()), xytext=(10, 2), textcoords="offset points", fontsize=8.5, color=INK2, va="center")
title(ax, "Frozen spec: drawdown from the previous equity peak", 10.5)
fig.subplots_adjust(left=0.065, right=0.985, top=0.94, bottom=0.05, hspace=0.16); fig.savefig(f"{R}/fig6_bt50k_equity.png"); plt.close(fig); print("fig6 written")

# ---------- signal, volatility, contracts, margin (optionally with an equity panel on top) ----------
def fig_account(X, out, score_ylim, equity=None, pdf=None):
    d = X["d"]; w0, w1 = d.index[0], d.index[-1]; w = slice(w0 - pd.offsets.MonthEnd(1), w1); ecb = ECB.loc[w]; score = SCORE.loc[w]; fire = (score.abs() > 0.5) & (np.sign(score) != ecb); v60 = V60.loc[w0:w1]; vb = VB.loc[w0:w1]
    n = 5 if equity else 4; fig, axes = plt.subplots(n, 1, figsize=(12, 2.9 * n), dpi=200, sharex=True, gridspec_kw={"height_ratios": ([1.35] if equity else []) + [1.25, 1, 1, 1]}); axes = list(axes)
    if equity:
        ax = axes.pop(0); style(ax); E = X["E"]
        for k in ["Long-only", "Follow-the-ECB", "Frozen spec"]: ax.plot(E.index, E[k].values, color=COL[k], linewidth=2.2 if k == "Frozen spec" else 1.6, solid_joinstyle="round", label=f"{dn(k)}: €{E[k].iloc[-1]/1000:,.1f}k")
        ax.axhline(50000, color=AXIS, linewidth=1); ax.yaxis.set_major_formatter(keur); ax.legend(frameon=False, fontsize=8.5, loc="upper left", ncol=3, title="final equity", title_fontsize=8, alignment="left"); title(ax, equity, 11.5)
        ax.set_ylim(None, E.max().max() * 1.12)
    ax = axes[0]; style(ax)
    short = (ecb < 0).astype(int); edges = short.diff().fillna(short.iloc[0]); starts = ecb.index[edges == 1]; stops = ecb.index[edges == -1]
    if len(stops) < len(starts): stops = stops.append(pd.DatetimeIndex([ecb.index[-1]]))
    for a, b in zip(starts, stops): ax.axvspan(a, b, color=S[1], alpha=0.10, linewidth=0)
    ax.axhspan(-0.5, 0.5, color=GRID, alpha=0.55, linewidth=0); ax.plot(score.index, score.values, color=S[0], linewidth=2, solid_joinstyle="round", label="Risk-factor composite score")
    ax.scatter(score.index[fire], score.values[fire], s=34, color=S[2], zorder=5, edgecolor=SURF, linewidth=1.5, label="Override fires (|score| > 0.5 and against ECB rate momentum)")
    ax.axhline(0, color=AXIS, linewidth=1); ax.set_ylim(*score_ylim); ax.set_ylabel("Score (z-units)", fontsize=9); ax.legend(frameon=False, fontsize=8.5, loc="lower left", ncol=2)
    ax.text(w0 + (w1 - w0) * 0.008, score_ylim[1] - 0.03 * (score_ylim[1] - score_ylim[0]), "orange shading = ECB rate momentum is short; unshaded = it is long; grey band = dead band ±0.5, momentum position kept", fontsize=8, color=INK2, va="top")
    title(ax, "Signal: risk-factor score and the months it overrides ECB rate momentum", 11 if equity else 11.5)
    ax = axes[1]; style(ax)
    ax.plot(v60.index, v60.values, color=MUTED, linewidth=1.1, label="60-day realised volatility"); ax.plot(vb.index, vb.values, color=S[0], linewidth=2, solid_joinstyle="round", label="Sizing volatility (70% 60-day + 30% long-run mean)")
    ax.set_ylabel("bp per year", fontsize=9); ax.set_ylim(0, v60.max() * (1.18 if equity else 1.0) * 1.03); ax.legend(frameon=False, fontsize=8.5, loc="upper center" if not equity else "upper left", ncol=2)
    title(ax, "Volatility of the 2nd Euribor contract (annualised, basis points of price)")
    ax = axes[2]; style(ax); c = d["contracts"]
    ax.fill_between(c.index, c.clip(lower=0).values, 0, step="post", color=S[0], alpha=0.85, linewidth=0, label="Long"); ax.fill_between(c.index, c.clip(upper=0).values, 0, step="post", color=S[1], alpha=0.85, linewidth=0, label="Short")
    ax.axhline(0, color=AXIS, linewidth=1); ax.set_ylabel("Contracts", fontsize=9); ax.set_ylim(None, c.max() * 1.3); ax.legend(frameon=False, fontsize=8.5, loc="upper left", ncol=2)
    title(ax, "Position: whole contracts held (10% volatility target on current equity, resized monthly)")
    ax = axes[3]; style(ax); mp = d["margin_pct"] * 100; ms = d["margin_stress_pct"] * 100
    ax.plot(ms.index, ms.values, color=INK2, linewidth=1.1, linestyle=(0, (4, 2)), label="If margin per contract had risen with volatility (floor = today's quote)")
    ax.plot(mp.index, mp.values, color=S[0], linewidth=2, solid_joinstyle="round", label="At today's initial margin, €237 per contract")
    ax.set_ylim(0, max(ms.max(), mp.max()) * 1.35); ax.yaxis.set_major_formatter(pct); ax.set_ylabel("Share of account equity", fontsize=9); ax.legend(frameon=False, fontsize=8.5, loc="upper left" if not equity else "upper center", ncol=1)
    tp = d["margin"].idxmax(); ax.annotate(f"largest euro amount: €{d['margin'].max():,.0f} ({abs(d['contracts'].loc[tp]):.0f} contracts), {tp:%b %Y}", (tp, mp.loc[tp]), xytext=(w1, mp.max() * 1.12), textcoords="data", ha="right", fontsize=8.5, color=INK2,
                arrowprops=dict(arrowstyle="-", color=AXIS, linewidth=1))
    title(ax, f"Margin deployed: average {mp.mean():.1f}% of equity, peak {mp.max():.1f}%; the other {100 - mp.max():.0f}%+ stays in cash")
    fig.subplots_adjust(left=0.07, right=0.985, top=0.96 if not equity else 0.965, bottom=0.035, hspace=0.2 if not equity else 0.24); fig.savefig(f"{R}/{out}"); pdf is not None and pdf.savefig(fig); plt.close(fig); print(out, "written")

# ---------- Monte Carlo: Sharpe densities, equity fan, drawdown, no-skill null ----------
def fig_mc(X, out, strategies, block, pdf=None):
    B, fan, perm, mc, d, m, V = X["B"], X["fan"], X["perm"], X["mc"], X["d"], X["m"], X["V"]; T = len(fan)
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), dpi=200)
    ax = axes[0, 0]; style(ax); allv = np.concatenate([B[f"{k}|sharpe"].values for k in strategies]); bins = np.linspace(np.floor(np.percentile(allv, 0.05) * 2) / 2, np.ceil(np.percentile(allv, 99.95) * 2) / 2, 61); top = 0
    for k in strategies:
        h, e = np.histogram(B[f"{k}|sharpe"], bins=bins, density=True); c = (e[:-1] + e[1:]) / 2; med = B[f"{k}|sharpe"].median(); top = max(top, h.max())
        ax.plot(c, h, color=COL[k], linewidth=2, label=f"{dn(k)}: median " + f"{med:+.2f}".replace("-", "−"), solid_joinstyle="round"); ax.plot([med, med], [0, np.interp(med, c, h)], color=COL[k], linewidth=1.4, linestyle=(0, (3, 2)))
    ax.plot([0, 0], [0, top * 1.04], color=AXIS, linewidth=1, zorder=1); ax.set_xlabel(f"Annualised Sharpe of a bootstrapped {T}-month path", fontsize=9.5); ax.set_ylabel("Density", fontsize=9.5); ax.set_ylim(None, top * 1.33)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left", ncol=2, title="dashed line = median of each distribution", title_fontsize=8, alignment="left")
    bs = mc["bootstrap_sharpe"]["Frozen spec"]; title(ax, f"Sharpe: frozen spec median {bs['p50']:+.2f}, 90% interval {bs['p05']:+.2f} to {bs['p95']:+.2f}")
    ax = axes[0, 1]; style(ax); x = np.arange(1, T + 1) / 12; act = m["equity_start"].shift(-1).fillna(d["equity"].iloc[-1]).values
    ax.fill_between(x, fan["p05"], fan["p95"], color=BAND[0], linewidth=0, label="5th to 95th percentile"); ax.fill_between(x, fan["p25"], fan["p75"], color=BAND[1], linewidth=0, label="25th to 75th percentile")
    ax.plot(x, fan["p50"], color=S[0], linewidth=2, label="Median path"); ax.plot(x, act, color=INK, linewidth=1.4, label="Actual backtest path")
    lo, hi = min(fan["p05"].min(), act.min()) * 0.8, max(fan["p95"].max(), act.max()) * 1.25; ticks = [t for t in [25000, 50000, 75000, 100000, 150000, 200000, 400000, 800000] if lo <= t <= hi and (hi / lo < 6 or t not in (75000, 150000))]
    ax.axhline(50000, color=AXIS, linewidth=1); ax.set_yscale("log"); ax.set_ylim(lo, hi); ax.set_yticks(ticks); ax.yaxis.set_major_formatter(keur); ax.minorticks_off()
    ax.set_xlabel("Years from start", fontsize=9.5); ax.set_ylabel("Account equity (log scale)", fontsize=9.5); ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    bp = mc["bootstrap_pnl"]["Frozen spec"]; title(ax, f"P&L: final equity €{bp['final_p05']/1000:,.0f}k to €{bp['final_p95']/1000:,.0f}k, median €{bp['final_p50']/1000:,.0f}k")
    ax = axes[1, 0]; style(ax); dd = B["Frozen spec|maxdd_pct"]; e = d["equity"].resample("ME").last(); obs = ((e / np.maximum(e.cummax(), 50000) - 1).min()) * 100
    ax.hist(dd, bins=np.linspace(min(-30, np.floor(np.percentile(dd, 0.05) / 10) * 10), 0, 49), color=S[0], alpha=0.35, edgecolor=SURF, linewidth=1); ax.axvline(obs, color=INK, linewidth=1.6); ax.set_ylim(None, ax.get_ylim()[1] * 1.12)
    ax.text(obs - 0.015 * ax.get_xlim()[0], ax.get_ylim()[1] * 0.97, f"backtest −{-obs:.1f}%\n(month-end)", fontsize=8.5, color=INK2, va="top", ha="left"); ax.xaxis.set_major_formatter(pct)
    ax.set_xlabel("Worst peak-to-trough drawdown on a bootstrapped path (month-end equity)", fontsize=9.5); ax.set_ylabel("Count of paths", fontsize=9.5)
    title(ax, f"Drawdown: median −{-bp['maxdd_p50']:.0f}%, 1 path in 20 worse than −{-bp['maxdd_p05']:.0f}%")
    ax = axes[1, 1]; style(ax); nl = mc["nulls"]["Frozen spec"]; lim = max(1.2, np.ceil((max(np.abs(perm).max(), nl["observed"]) + 0.1) * 5) / 5)
    ax.hist(perm, bins=np.linspace(-lim, lim, 49), color=S[0], alpha=0.35, edgecolor=SURF, linewidth=1); ax.axvline(nl["observed"], color=INK, linewidth=1.6); ax.set_ylim(None, ax.get_ylim()[1] * 1.22)
    ax.text(nl["observed"] - 0.05 * lim, ax.get_ylim()[1] * 0.97, f"observed {nl['observed']:+.2f}\n{int(round(nl['p_perm'] * len(perm)))} of {len(perm):,} shuffles as high", fontsize=8.5, color=INK2, va="top", ha="right")
    ax.set_xlabel(f"Annualised Sharpe with the long/short path shuffled in time ({block}-month blocks)", fontsize=9.5); ax.set_ylabel("Count of shuffled paths", fontsize=9.5)
    title(ax, "Is the timing luck? No-skill null for the frozen spec")
    fig.subplots_adjust(left=0.065, right=0.985, top=0.95, bottom=0.07, wspace=0.2, hspace=0.3); fig.savefig(f"{R}/{out}"); pdf is not None and pdf.savefig(fig); plt.close(fig); print(out, "written")

fig_account(FULL, "fig7_bt50k_signal_vol_margin.png", (-3, 2.2))
fig_mc(FULL, "fig8_bt50k_montecarlo.png", ["Frozen spec", "Follow-the-ECB", "Long-only", "Walk-forward threshold"], 12)
with PdfPages(f"{R}/bt50k_5y_pages.pdf") as pdf:          # the two five-year pages in one file: account, then the Sharpe / Monte Carlo analysis
    fig_account(FIVE, "fig9_bt50k_5y_account.png", (-1.9, 1.15), equity="Last five years: a new €50,000 account, September 2021 to August 2026 (10% volatility target, after costs)", pdf=pdf)
    fig_mc(FIVE, "fig10_bt50k_5y_montecarlo.png", ["Frozen spec", "Follow-the-ECB", "Long-only"], 6, pdf=pdf)
