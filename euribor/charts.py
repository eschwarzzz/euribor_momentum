"""Every figure in the reports. Figures 1-5 belong to REPORT.md, 6-8 to BACKTEST_50K.md, 9-11 to its appendix."""
import json

import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Rectangle

from . import plotting as P
from .config import (COMPOSITE, ECB_RULE, FIGURES, LONG_ONLY, OOS_END, OOS_START, OVERRIDE_THRESHOLD, PLACEBO, RESULTS, RIDGE_10,
                     SCORE_INPUTS, SIZING_VOL_END, TICK_COST)
from .data import load_continuous, load_features, load_pnl_curves, load_positions, load_results_table
from .plotting import plt
from .signals import factor_score, signed_zscores

INPUT_LABEL = {"r_dfr_chg3": "Deposit rate, 3M change", "i_hicp": "HICP, year on year", "i_core": "Core HICP, year on year",
               "i_unemp_chg6": "Unemployment, 6M change", "s_ciss": "CISS stress index"}


# ---------------------------------------------------------------- research report (figures 1-5)
def fig1_cumulative_pnl():
    curves = load_pnl_curves().loc["2008-01-01":OOS_END]
    keys = [(LONG_ONLY, "Long-only (benchmark)"), (ECB_RULE, "Follow-the-ECB rule (benchmark)"), (COMPOSITE, "Macro composite, prior signs"),
            (RIDGE_10, "Macro ridge, walk-forward"), (PLACEBO, "Placebo (shuffled target)")]
    fig, ax = plt.subplots(figsize=(11, 5.6), dpi=200)
    P.style(ax)
    ends = []
    for (key, label), colour in zip(keys, P.SERIES):
        cum = curves[key].cumsum() * 100
        ax.plot(cum.index, cum.values, color=colour, linewidth=2, solid_joinstyle="round", solid_capstyle="round", label=label)
        ends.append((cum.iloc[-1], label, colour))
    ax.axhline(0, color=P.AXIS, linewidth=1)
    ax.set_title("Synthetic 3M Euribor future (2nd contract): cumulative P&L, Jan 2008 to Aug 2026", loc="left", fontsize=12,
                 fontweight="semibold", pad=14)
    ax.set_ylabel("Basis points of price, one contract, after costs", fontsize=9.5)
    ax.yaxis.set_major_formatter(P.thousands)
    # end labels with collision nudging; text in ink, never in the series colour
    ends.sort(key=lambda t: t[0])
    ys = [e[0] for e in ends]
    lo, hi = ax.get_ylim()
    min_gap = (hi - lo) * 0.045
    for i in range(1, len(ys)):
        if ys[i] - ys[i - 1] < min_gap:
            ys[i] = ys[i - 1] + min_gap
    x_end = curves.index[-1]
    for (value, label, _), y_label in zip(ends, ys):
        nudged = abs(y_label - value) > 1e-9
        ax.annotate(f"{label}  {value:+,.0f}", xy=(x_end, value), xytext=(12, 0), textcoords="offset points", va="center", ha="left",
                    fontsize=8.5, color=P.INK2, arrowprops=dict(arrowstyle="-", color=P.AXIS, lw=0.8, shrinkA=0, shrinkB=2) if nudged else None)
        if nudged:
            offset = (y_label - value) / (hi - lo) * ax.get_window_extent().height * 0.72
            ax.annotate(f"{label}  {value:+,.0f}", xy=(x_end, value), xytext=(12, offset), textcoords="offset points", va="center",
                        ha="left", fontsize=8.5, color=P.INK2)
    ax.legend(loc="upper left", frameon=False, fontsize=8.5, ncol=1)
    ax.set_xlim(curves.index[0], curves.index[-1] + pd.DateOffset(days=30))
    fig.subplots_adjust(right=0.72, left=0.07, top=0.88, bottom=0.08)
    P.save(fig, FIGURES / "fig1_cumulative_pnl.png")


def fig2_group_sharpe():
    table = load_results_table()
    groups = [("R", "Rates / policy"), ("M", "Money supply"), ("D", "Debt holdings"), ("I", "Inflation"), ("S", "Sentiment / political")]
    prior = [table.loc[f"Prior group {g} only", "sharpe"] if f"Prior group {g} only" in table.index else np.nan for g, _ in groups]
    ridge = [table.loc[f"Ridge group {g} only", "sharpe"] for g, _ in groups]
    fig, ax = plt.subplots(figsize=(8.5, 4.6), dpi=200)
    P.style(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=P.GRID, linewidth=1)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_visible(True)
    ax.spines["left"].set_color(P.AXIS)
    ypos = np.arange(len(groups))[::-1] * 1.0
    h = 0.34

    def bar(y, w, colour):
        if np.isnan(w):
            return
        x0, width = min(0, w), abs(w)
        if width < 0.04:
            patch = Rectangle((x0, y - h / 2), width, h, linewidth=0, facecolor=colour)
        else:
            patch = FancyBboxPatch((x0, y - h / 2), width, h, boxstyle="round,pad=0,rounding_size=0.06", linewidth=0, facecolor=colour,
                                   mutation_aspect=0.25)
        ax.add_patch(patch)
        ax.text(w + (0.02 if w >= 0 else -0.02), y, f"{w:+.2f}", va="center", ha="left" if w >= 0 else "right", fontsize=8.5, color=P.INK2)

    for y, p_val, r_val in zip(ypos, prior, ridge):
        bar(y + h / 2 + 0.03, p_val, P.SERIES[0])
        bar(y - h / 2 - 0.03, r_val, P.SERIES[1])
    ax.set_yticks(ypos)
    ax.set_yticklabels([name for _, name in groups], fontsize=9.5, color=P.INK)
    ax.set_ylim(-0.7, len(groups) - 0.3)
    ax.set_xlim(-0.15, 0.85)
    ax.axvline(0, color=P.AXIS, linewidth=1)
    ax.set_title("Sharpe ratio by factor group, single-group models, 2008 to 2026", loc="left", fontsize=12, fontweight="semibold", pad=12)
    ax.set_xlabel("Sharpe ratio (after costs)", fontsize=9.5)
    ax.legend(handles=[Line2D([0], [0], color=P.SERIES[0], lw=6, label="Prior-sign composite (no fitting)"),
                       Line2D([0], [0], color=P.SERIES[1], lw=6, label="Ridge, walk-forward fitted")], loc="lower right", frameon=False, fontsize=8.5)
    fig.text(0.24, 0.03, "Debt holdings has no theory-pinned sign, so only the fitted version exists.", fontsize=8, color=P.MUTED)
    fig.subplots_adjust(left=0.24, right=0.97, top=0.86, bottom=0.19)
    P.save(fig, FIGURES / "fig2_group_sharpe.png")


def fig3_montecarlo():
    boot = pd.read_csv(RESULTS / "mc_bootstrap_sharpe.csv")
    nulls = json.load(open(RESULTS / "mc_nulls.json"))
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), dpi=200)
    ax = axes[0]
    P.style(ax)
    bins = np.linspace(-1.0, 1.8, 57)
    for key, colour in zip(["Long-only", "Follow-the-ECB", "Composite ±1", "Ridge a=10"], P.SERIES):
        h, e = np.histogram(boot[key], bins=bins, density=True)
        ax.plot((e[:-1] + e[1:]) / 2, h, color=colour, linewidth=2, label=key, solid_joinstyle="round")
    ax.axvline(0, color=P.AXIS, linewidth=1)
    ax.set_xlabel("Annualised Sharpe of a bootstrapped 224-month path", fontsize=9.5)
    ax.set_ylabel("Density", fontsize=9.5)
    ax.set_title("Sampling uncertainty: 10,000 block-bootstrap paths", loc="left", fontsize=11, fontweight="semibold")
    ax.legend(frameon=False, fontsize=8.5)
    # no-skill null for the composite, recomputed with its own seed for the histogram
    ax = axes[1]
    P.style(ax)
    F, y, _ = load_features()
    y_bp = y.loc[OOS_START:OOS_END] * 100
    pos = load_positions()[COMPOSITE].reindex(y_bp.index).fillna(0).values
    T = len(pos)
    rng = np.random.default_rng(7)

    def sharpe(p):
        p = pd.Series(p, index=y_bp.index)
        cost = p.diff().abs().fillna(p.abs()) * TICK_COST * 100 + p.abs() * 2 * TICK_COST * 100 / 3
        x = p * y_bp - cost
        return x.mean() / x.std() * np.sqrt(12)

    n_blocks = int(np.ceil(T / 12))
    perm = []
    for _ in range(5000):
        order = rng.permutation(n_blocks)
        idx = np.concatenate([np.arange(b * 12, min((b + 1) * 12, T)) for b in order])
        perm.append(sharpe(pos[idx]))
    perm = np.array(perm)
    observed = nulls["Composite ±1"]["observed"]
    ax.hist(perm, bins=np.linspace(-1.2, 1.2, 49), color=P.SERIES[2], alpha=0.35, edgecolor=P.SURFACE, linewidth=1,
            label="No-skill null: composite positions block-shuffled in time")
    ax.axvline(observed, color=P.SERIES[2], linewidth=2)
    ax.text(observed + 0.03, ax.get_ylim()[1] * 0.92, f"observed {observed:+.2f}\np = {(perm >= observed).mean():.3f}", fontsize=8.5,
            color=P.INK2, va="top")
    ax.set_xlabel("Annualised Sharpe", fontsize=9.5)
    ax.set_ylabel("Count of shuffled paths", fontsize=9.5)
    ax.set_title("Is the timing luck? 5,000 shuffled position paths", loc="left", fontsize=11, fontweight="semibold")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    fig.subplots_adjust(left=0.06, right=0.98, top=0.88, bottom=0.14, wspace=0.18)
    P.save(fig, FIGURES / "fig3_montecarlo.png")


def fig4_divergence():
    M = pd.read_csv(RESULTS / "divergence_monthly.csv", index_col=0, parse_dates=True)
    rel = pd.read_csv(RESULTS / "divergence_attribution.csv", index_col=0, parse_dates=True)["rel_pnl_bp"].reindex(M.index).fillna(0).cumsum()
    fig, axes = plt.subplots(2, 1, figsize=(11, 6.8), dpi=200, sharex=True)
    ax = axes[0]
    P.style(ax)
    ax.bar(M.index, M["share_disagree"] * 100, width=26, color=P.SERIES[0], linewidth=0)
    ax.set_ylabel("% of 44 paths against the ECB rule", fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_title("Where the strategy paths diverge from follow-the-ECB, and what the composite earned by diverging", loc="left",
                 fontsize=11.5, fontweight="semibold", pad=10)
    ax = axes[1]
    P.style(ax)
    ax.plot(rel.index, rel.values, color=P.SERIES[1], linewidth=2, solid_joinstyle="round")
    ax.axhline(0, color=P.AXIS, linewidth=1)
    ax.set_ylabel("Composite minus ECB rule, cumulative bp", fontsize=9)
    notes = [("2008-10-31", "Oct 2008: long into the cuts", 40), ("2011-10-31", "2011: long through the two hikes", 40),
             ("2022-02-28", "late 2021: short before the first hike", 22), ("2024-03-31", "2023-24: long a year too early", -60),
             ("2025-04-30", "2024-25: short into the cuts", -60)]
    for date, label, dy in notes:
        t = pd.Timestamp(date)
        ax.annotate(label, xy=(t, rel.loc[:t].iloc[-1]), xytext=(0, dy), textcoords="offset points", ha="center", fontsize=8, color=P.INK2,
                    arrowprops=dict(arrowstyle="-", color=P.AXIS, lw=0.8))
    fig.subplots_adjust(left=0.08, right=0.98, top=0.92, bottom=0.06, hspace=0.12)
    P.save(fig, FIGURES / "fig4_divergence.png")


def _shade_short_months(ax, ecb, colour, include_first=False):
    """Shade the months in which the ECB rule is short."""
    short = (ecb < 0).astype(int)
    edges = short.diff().fillna(short.iloc[0])
    starts, stops = ecb.index[edges == 1], ecb.index[edges == -1]
    if include_first and short.iloc[0] == 1:
        starts = starts.insert(0, ecb.index[0])
    if len(stops) < len(starts):
        stops = stops.append(pd.DatetimeIndex([ecb.index[-1]]))
    for a, b in zip(starts, stops):
        ax.axvspan(a, b, color=colour, alpha=0.10, linewidth=0)


def fig5_signal():
    F, _, _ = load_features()
    Z = signed_zscores(F, SCORE_INPUTS).loc["2002-01-31":]
    ecb = load_positions()[ECB_RULE].loc["2002-01-31":]
    score = factor_score(F).loc["2002-01-31":]
    fire = (score.abs() > OVERRIDE_THRESHOLD) & (np.sign(score) != ecb)
    fig, axes = plt.subplots(2, 1, figsize=(12, 7.4), dpi=200, sharex=True, gridspec_kw={"height_ratios": [1.15, 1]})
    ax = axes[0]
    P.style(ax)
    _shade_short_months(ax, ecb, P.SERIES[1], include_first=True)
    ax.axhspan(-0.5, 0.5, color=P.GRID, alpha=0.55, linewidth=0)
    ax.plot(score.index, score.values, color=P.SERIES[0], linewidth=2, solid_joinstyle="round", label="Five-input score (mean of signed, clipped z-scores)")
    ax.scatter(score.index[fire], score.values[fire], s=34, color=P.SERIES[2], zorder=5, edgecolor=P.SURFACE, linewidth=1.5,
               label="Override fires (|score| > 0.5 and against the rule)")
    ax.axhline(0, color=P.AXIS, linewidth=1)
    ax.set_ylim(-2.4, 2.6)
    ax.set_ylabel("Score (z-units)", fontsize=9)
    ax.set_title("The signal: risk-factor score, dead band, and the months it overrides the ECB rule", loc="left", fontsize=11.5,
                 fontweight="semibold", pad=10)
    ax.text(pd.Timestamp("2002-03-31"), 2.45, "orange shading = follow-the-ECB rule is short (last move was a hike); unshaded = rule is long",
            fontsize=8, color=P.INK2, va="top")
    ax.text(pd.Timestamp("2002-03-31"), -0.45, "dead band ±0.5: rule position kept", fontsize=8, color=P.MUTED, va="bottom")
    ax.legend(frameon=False, fontsize=8.5, loc="lower left")
    ax = axes[1]
    P.style(ax)
    for c, colour in zip(SCORE_INPUTS, P.SERIES):
        ax.plot(Z.index, Z[c].values, color=colour, linewidth=1.6, solid_joinstyle="round", label=INPUT_LABEL[c])
    ax.axhline(0, color=P.AXIS, linewidth=1)
    ax.set_ylabel("Signed z-score", fontsize=9)
    ax.set_ylim(-3.1, 3.1)
    ax.set_title("Its five inputs, each signed so that + argues for a higher price", loc="left", fontsize=11, fontweight="semibold", pad=8)
    ax.legend(frameon=False, fontsize=8.5, loc="lower left", ncol=5)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.93, bottom=0.05, hspace=0.16)
    P.save(fig, FIGURES / "fig5_signal.png")


# ---------------------------------------------------------------- account report (figures 6-10)
def load_account(tag):
    """Everything account.py left in results/ for one window (tag 'bt50k' or 'bt50k_5y')."""
    read = lambda name, **kw: pd.read_csv(RESULTS / f"{tag}_{name}.csv", **kw)     # noqa: E731
    return dict(d=read("daily", index_col=0, parse_dates=True), m=read("monthly", index_col=0, parse_dates=True),
                E=read("equity_curves", index_col=0, parse_dates=True), V=read("variants", index_col=0),
                mc=json.load(open(RESULTS / f"{tag}_mc.json")), B=read("bootstrap"), fan=read("bootstrap_fan"),
                perm=read("null_perm")["perm_sharpe"].values)


def _sizing_volatility():
    """60-day realised volatility and the constant sizing volatility (its 1999-2007 average), bp a year."""
    cont = load_continuous()
    v60 = cont["chg1"].rolling(60).std() * np.sqrt(252) * 100
    return v60, pd.Series(v60.loc[:SIZING_VOL_END].mean(), index=v60.index)


def fig6_equity(X):
    E = X["E"]
    fig, axes = plt.subplots(2, 1, figsize=(12, 7.2), dpi=200, sharex=True, gridspec_kw={"height_ratios": [2.4, 1]})
    ax = axes[0]
    P.style(ax)
    v1 = "v1 spec (as reported)"
    ax.plot(E.index, E[v1].values, color=P.MUTED, linewidth=1.4, linestyle=(0, (4, 2)), label="v1 spec, 10% vol target, no interest")
    for k in ["Long-only", "Follow-the-ECB", "Walk-forward threshold", "Frozen spec"]:
        ax.plot(E.index, E[k].values, color=P.STRATEGY_COLOUR[k], linewidth=2.2 if k == "Frozen spec" else 1.6, solid_joinstyle="round",
                label=P.display_name(k))
    ends = E.iloc[-1].sort_values()
    ypos = np.log(ends)
    for i in range(1, len(ypos)):
        if ypos.iloc[i] - ypos.iloc[i - 1] < 0.12:
            ypos.iloc[i] = ypos.iloc[i - 1] + 0.12
    for k in ends.index:
        label = "v1 spec" if k == v1 else P.display_name(k)
        ax.text(E.index[-1] + pd.offsets.Day(60), np.exp(ypos[k]), f"{label}  €{ends[k] / 1000:,.0f}k", fontsize=8.5, color=P.INK2, va="center")
    ax.axhline(50000, color=P.AXIS, linewidth=1)
    ax.set_yscale("log")
    ax.set_ylim(E.min().min() * 0.85, np.exp(ypos.max()) * 1.15)
    ax.set_yticks([t for t in [25000, 50000, 100000, 200000, 400000, 800000] if t <= E.max().max() * 1.3])
    ax.minorticks_off()
    ax.yaxis.set_major_formatter(P.euro_k)
    ax.set_xlim(E.index[0], E.index[-1] + pd.offsets.Day(1250))
    ax.set_xticks(pd.to_datetime([f"{y}-01-01" for y in range(2008, 2027, 2)]))
    ax.set_xticklabels(range(2008, 2027, 2))
    ax.legend(frameon=False, fontsize=8.5, loc="upper left", ncol=5)
    P.title(ax, "€50,000 account, per-euro sizing, January 2008 to August 2026 (after costs, cash at EONIA/€STR, synthetic prices; log scale)", 11.5)
    ax = axes[1]
    P.style(ax)
    eq = E["Frozen spec"]
    dd = (eq / eq.cummax() - 1) * 100
    ax.fill_between(dd.index, dd.values, 0, color=P.SERIES[0], alpha=0.25, linewidth=0)
    ax.plot(dd.index, dd.values, color=P.SERIES[0], linewidth=1.2)
    ax.yaxis.set_major_formatter(P.percent)
    trough = dd.idxmin()
    ax.set_ylim(dd.min() * 1.12, 0.5)
    ax.annotate(f"−{-dd.min():.1f}%, {trough:%b %Y}", (trough, dd.min()), xytext=(10, 2), textcoords="offset points", fontsize=8.5, color=P.INK2,
                va="center")
    P.title(ax, "Frozen spec: drawdown from the previous equity peak", 10.5)
    fig.subplots_adjust(left=0.065, right=0.985, top=0.94, bottom=0.05, hspace=0.16)
    P.save(fig, FIGURES / "fig6_bt50k_equity.png")


def fig_account(X, name, score_ylim, equity_title=None, pdf=None):
    """Signal, sizing volatility, contracts held and margin deployed; with an equity panel on top when ``equity_title`` is given."""
    ECB, SCORE = load_positions()[ECB_RULE], factor_score(load_features()[0])
    V60, VB = _sizing_volatility()
    d = X["d"]
    w0, w1 = d.index[0], d.index[-1]
    window = slice(w0 - pd.offsets.MonthEnd(1), w1)
    ecb, score = ECB.loc[window], SCORE.loc[window]
    fire = (score.abs() > OVERRIDE_THRESHOLD) & (np.sign(score) != ecb)
    v60, vb = V60.loc[w0:w1], VB.loc[w0:w1]
    with_equity = equity_title is not None
    n = 5 if with_equity else 4
    fig, axes = plt.subplots(n, 1, figsize=(12, 2.9 * n), dpi=200, sharex=True,
                             gridspec_kw={"height_ratios": ([1.35] if with_equity else []) + [1.25, 1, 1, 1]})
    axes = list(axes)
    if with_equity:
        ax = axes.pop(0)
        P.style(ax)
        E = X["E"]
        for k in ["Long-only", "Follow-the-ECB", "Frozen spec"]:
            ax.plot(E.index, E[k].values, color=P.STRATEGY_COLOUR[k], linewidth=2.2 if k == "Frozen spec" else 1.6, solid_joinstyle="round",
                    label=f"{P.display_name(k)}: €{E[k].iloc[-1] / 1000:,.1f}k")
        ax.axhline(50000, color=P.AXIS, linewidth=1)
        ax.yaxis.set_major_formatter(P.euro_k)
        ax.legend(frameon=False, fontsize=8.5, loc="upper left", ncol=3, title="final equity", title_fontsize=8, alignment="left")
        P.title(ax, equity_title, 11.5)
        ax.set_ylim(None, E.max().max() * 1.12)
    # signal
    ax = axes[0]
    P.style(ax)
    _shade_short_months(ax, ecb, P.SERIES[1])
    ax.axhspan(-0.5, 0.5, color=P.GRID, alpha=0.55, linewidth=0)
    ax.plot(score.index, score.values, color=P.SERIES[0], linewidth=2, solid_joinstyle="round", label="Five-input risk-factor score")
    ax.scatter(score.index[fire], score.values[fire], s=34, color=P.SERIES[2], zorder=5, edgecolor=P.SURFACE, linewidth=1.5,
               label="Override fires (|score| > 0.5 and against ECB rate momentum)")
    ax.axhline(0, color=P.AXIS, linewidth=1)
    ax.set_ylim(*score_ylim)
    ax.set_ylabel("Score (z-units)", fontsize=9)
    ax.legend(frameon=False, fontsize=8.5, loc="lower left", ncol=2)
    ax.text(w0 + (w1 - w0) * 0.008, score_ylim[1] - 0.03 * (score_ylim[1] - score_ylim[0]),
            "orange shading = ECB rate momentum is short; unshaded = it is long; grey band = dead band ±0.5, momentum position kept",
            fontsize=8, color=P.INK2, va="top")
    P.title(ax, "Signal: risk-factor score and the months it overrides ECB rate momentum", 11 if with_equity else 11.5)
    # volatility
    ax = axes[1]
    P.style(ax)
    ax.plot(v60.index, v60.values, color=P.MUTED, linewidth=1.1, label="60-day realised volatility")
    ax.plot(vb.index, vb.values, color=P.SERIES[0], linewidth=2, solid_joinstyle="round", label=f"Sizing volatility, fixed at the 1999–2007 average ({vb.iloc[0]:.0f} bp)")
    ax.set_ylabel("bp per year", fontsize=9)
    ax.set_ylim(0, v60.max() * (1.18 if with_equity else 1.0) * 1.03)
    ax.legend(frameon=False, fontsize=8.5, loc="upper center" if not with_equity else "upper left", ncol=2)
    P.title(ax, "Volatility of the 2nd Euribor contract (annualised, basis points of price)")
    # contracts
    ax = axes[2]
    P.style(ax)
    c = d["contracts"]
    ax.fill_between(c.index, c.clip(lower=0).values, 0, step="post", color=P.SERIES[0], alpha=0.85, linewidth=0, label="Long")
    ax.fill_between(c.index, c.clip(upper=0).values, 0, step="post", color=P.SERIES[1], alpha=0.85, linewidth=0, label="Short")
    ax.axhline(0, color=P.AXIS, linewidth=1)
    ax.set_ylabel("Contracts", fontsize=9)
    ax.set_ylim(None, c.max() * 1.3)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left", ncol=2)
    P.title(ax, "Position: whole contracts held (10% of current equity at the fixed sizing volatility, resized monthly)")
    # margin
    ax = axes[3]
    P.style(ax)
    mp, ms = d["margin_pct"] * 100, d["margin_stress_pct"] * 100
    ax.plot(ms.index, ms.values, color=P.INK2, linewidth=1.1, linestyle=(0, (4, 2)),
            label="If margin per contract had risen with volatility (floor = today's quote)")
    ax.plot(mp.index, mp.values, color=P.SERIES[0], linewidth=2, solid_joinstyle="round", label="At today's initial margin, €237 per contract")
    ax.set_ylim(0, max(ms.max(), mp.max()) * 1.35)
    ax.yaxis.set_major_formatter(P.percent)
    ax.set_ylabel("Share of account equity", fontsize=9)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left" if not with_equity else "upper center", ncol=1)
    tp = d["margin"].idxmax()
    ax.annotate(f"largest euro amount: €{d['margin'].max():,.0f} ({abs(d['contracts'].loc[tp]):.0f} contracts), {tp:%b %Y}", (tp, mp.loc[tp]),
                xytext=(w1, max(ms.max(), mp.max()) * 0.8), textcoords="data", ha="right", fontsize=8.5, color=P.INK2,
                arrowprops=dict(arrowstyle="-", color=P.AXIS, linewidth=1))
    P.title(ax, f"Margin deployed: average {mp.mean():.1f}% of equity, peak {mp.max():.1f}%; the other {100 - mp.max():.0f}%+ stays in cash")
    fig.subplots_adjust(left=0.07, right=0.985, top=0.96 if not with_equity else 0.965, bottom=0.035, hspace=0.2 if not with_equity else 0.24)
    fig.savefig(FIGURES / name)
    if pdf is not None:
        pdf.savefig(fig)
    plt.close(fig)
    print(name, "written")


def fig_mc(X, name, strategies, block, pdf=None):
    """Bootstrap Sharpe densities, equity fan, drawdown distribution and the no-skill null."""
    B, fan, perm, mc, d, m = X["B"], X["fan"], X["perm"], X["mc"], X["d"], X["m"]
    T = len(fan)
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), dpi=200)
    # Sharpe densities
    ax = axes[0, 0]
    P.style(ax)
    all_values = np.concatenate([B[f"{k}|sharpe"].values for k in strategies])
    bins = np.linspace(np.floor(np.percentile(all_values, 0.05) * 2) / 2, np.ceil(np.percentile(all_values, 99.95) * 2) / 2, 61)
    top = 0
    for k in strategies:
        h, e = np.histogram(B[f"{k}|sharpe"], bins=bins, density=True)
        centres = (e[:-1] + e[1:]) / 2
        median = B[f"{k}|sharpe"].median()
        top = max(top, h.max())
        ax.plot(centres, h, color=P.STRATEGY_COLOUR[k], linewidth=2, label=f"{P.display_name(k)}: median " + f"{median:+.2f}".replace("-", "−"),
                solid_joinstyle="round")
        ax.plot([median, median], [0, np.interp(median, centres, h)], color=P.STRATEGY_COLOUR[k], linewidth=1.4, linestyle=(0, (3, 2)))
    ax.plot([0, 0], [0, top * 1.04], color=P.AXIS, linewidth=1, zorder=1)
    ax.set_xlabel(f"Annualised Sharpe of a bootstrapped {T}-month path", fontsize=9.5)
    ax.set_ylabel("Density", fontsize=9.5)
    ax.set_ylim(None, top * 1.33)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left", ncol=2, title="dashed line = median of each distribution", title_fontsize=8, alignment="left")
    bs = mc["bootstrap_sharpe"]["Frozen spec"]
    P.title(ax, f"Sharpe: frozen spec median {bs['p50']:+.2f}, 90% interval {bs['p05']:+.2f} to {bs['p95']:+.2f}")
    # equity fan
    ax = axes[0, 1]
    P.style(ax)
    x = np.arange(1, T + 1) / 12
    actual = m["equity_start"].shift(-1).fillna(d["equity"].iloc[-1]).values
    ax.fill_between(x, fan["p05"], fan["p95"], color=P.BAND[0], linewidth=0, label="5th to 95th percentile")
    ax.fill_between(x, fan["p25"], fan["p75"], color=P.BAND[1], linewidth=0, label="25th to 75th percentile")
    ax.plot(x, fan["p50"], color=P.SERIES[0], linewidth=2, label="Median path")
    ax.plot(x, actual, color=P.INK, linewidth=1.4, label="Actual backtest path")
    lo, hi = min(fan["p05"].min(), actual.min()) * 0.8, max(fan["p95"].max(), actual.max()) * 1.25
    ticks = [t for t in [25000, 50000, 75000, 100000, 150000, 200000, 400000, 800000, 1600000, 3200000, 6400000]
             if lo <= t <= hi and (hi / lo < 6 or t not in (75000, 150000))]
    ax.axhline(50000, color=P.AXIS, linewidth=1)
    ax.set_yscale("log")
    ax.set_ylim(lo, hi)
    ax.set_yticks(ticks)
    ax.yaxis.set_major_formatter(P.euro_k)
    ax.minorticks_off()
    ax.set_xlabel("Years from start", fontsize=9.5)
    ax.set_ylabel("Account equity (log scale)", fontsize=9.5)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    bp = mc["bootstrap_pnl"]["Frozen spec"]
    P.title(ax, f"P&L: final equity €{bp['final_p05'] / 1000:,.0f}k to €{bp['final_p95'] / 1000:,.0f}k, median €{bp['final_p50'] / 1000:,.0f}k")
    # drawdown
    ax = axes[1, 0]
    P.style(ax)
    dd = B["Frozen spec|maxdd_pct"]
    month_end_equity = d["equity"].resample("ME").last()
    observed = ((month_end_equity / np.maximum(month_end_equity.cummax(), 50000) - 1).min()) * 100
    ax.hist(dd, bins=np.linspace(min(-30, np.floor(np.percentile(dd, 0.05) / 10) * 10), 0, 49), color=P.SERIES[0], alpha=0.35, edgecolor=P.SURFACE,
            linewidth=1)
    ax.axvline(observed, color=P.INK, linewidth=1.6)
    ax.set_ylim(None, ax.get_ylim()[1] * 1.12)
    ax.text(observed - 0.015 * ax.get_xlim()[0], ax.get_ylim()[1] * 0.97, f"backtest −{-observed:.1f}%\n(month-end)", fontsize=8.5, color=P.INK2,
            va="top", ha="left")
    ax.xaxis.set_major_formatter(P.percent)
    ax.set_xlabel("Worst peak-to-trough drawdown on a bootstrapped path (month-end equity)", fontsize=9.5)
    ax.set_ylabel("Count of paths", fontsize=9.5)
    P.title(ax, f"Drawdown: median −{-bp['maxdd_p50']:.0f}%, 1 path in 20 worse than −{-bp['maxdd_p05']:.0f}%")
    # no-skill null
    ax = axes[1, 1]
    P.style(ax)
    null = mc["nulls"]["Frozen spec"]
    lim = max(1.2, np.ceil((max(np.abs(perm).max(), null["observed"]) + 0.1) * 5) / 5)
    ax.hist(perm, bins=np.linspace(-lim, lim, 49), color=P.SERIES[0], alpha=0.35, edgecolor=P.SURFACE, linewidth=1)
    ax.axvline(null["observed"], color=P.INK, linewidth=1.6)
    ax.set_ylim(None, ax.get_ylim()[1] * 1.22)
    ax.text(null["observed"] - 0.05 * lim, ax.get_ylim()[1] * 0.97,
            f"observed {null['observed']:+.2f}\n{int(round(null['p_perm'] * len(perm)))} of {len(perm):,} shuffles as high", fontsize=8.5,
            color=P.INK2, va="top", ha="right")
    ax.set_xlabel(f"Annualised Sharpe with the long/short path shuffled in time ({block}-month blocks)", fontsize=9.5)
    ax.set_ylabel("Count of shuffled paths", fontsize=9.5)
    P.title(ax, "Is the timing luck? No-skill null for the frozen spec")
    fig.subplots_adjust(left=0.065, right=0.985, top=0.95, bottom=0.07, wspace=0.2, hspace=0.3)
    fig.savefig(FIGURES / name)
    if pdf is not None:
        pdf.savefig(fig)
    plt.close(fig)
    print(name, "written")


# ---------------------------------------------------------------- appendix B (figure 11)
def fig11_trend_correlation():
    """Rolling correlation with the trend-following book and both strategies' yearly P&L in own-volatility units."""
    M = pd.read_csv(RESULTS / "trendcorr_monthly_pnl.csv", index_col=0, parse_dates=True)
    YR = pd.read_csv(RESULTS / "trendcorr_by_year.csv", index_col=0)
    euribor, book, rates = "Frozen spec, 1 contract", "Whole trend book", "US rates sleeve"
    fig, axes = plt.subplots(2, 1, figsize=(12, 8.4), dpi=200, gridspec_kw={"height_ratios": [1, 1.15]})
    ax = axes[0]
    P.style(ax)
    W = 36
    rc, rr = M[euribor].rolling(W).corr(M[book]), M[euribor].rolling(W).corr(M[rates])
    band = 2 / np.sqrt(W)
    ax.axhspan(-band, band, color=P.GRID, alpha=0.55, linewidth=0)
    ax.axhline(0, color=P.AXIS, linewidth=1)
    ax.plot(rr.index, rr.values, color=P.INK2, linewidth=1.1, linestyle=(0, (4, 2)), label="with its US rates sleeve")
    ax.plot(rc.index, rc.values, color=P.VIOLET, linewidth=2, solid_joinstyle="round", label="with the whole trend book")
    ax.set_ylim(-0.8, 0.8)
    ax.set_ylabel("Correlation", fontsize=9)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left", ncol=2)
    ax.text(rc.dropna().index[0], -band + 0.03, "grey band = range expected from two unrelated series (±2 standard errors)", fontsize=8,
            color=P.MUTED, va="bottom")
    ax.set_title(f"Euribor frozen spec against the trend-following book: rolling {W}-month correlation of monthly P&L "
                 f"(full-window value {M[euribor].corr(M[book]):+.2f})", loc="left", fontsize=11.5, fontweight="semibold", pad=8)
    ax = axes[1]
    P.style(ax)
    x, bw = np.arange(len(YR)), 0.36
    ax.bar(x - bw / 2 - 0.02, YR["trend_in_vol_units"], width=bw, color=P.VIOLET, label="Trend-following book")
    ax.bar(x + bw / 2 + 0.02, YR["euribor_in_vol_units"], width=bw, color=P.SERIES[0], label="Euribor frozen spec, 1 contract")
    ax.axhline(0, color=P.AXIS, linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(YR.index)
    ax.set_ylabel("Year's P&L ÷ own annual volatility", fontsize=9)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left", ncol=2)
    ax.set_ylim(None, max(YR["trend_in_vol_units"].max(), YR["euribor_in_vol_units"].max()) * 1.25)
    ax.set_title("They earn in different years: each year's P&L in units of the strategy's own annual volatility (2011 from April, 2026 to April)",
                 loc="left", fontsize=11, fontweight="semibold", pad=8)
    fig.subplots_adjust(left=0.065, right=0.985, top=0.94, bottom=0.05, hspace=0.3)
    P.save(fig, FIGURES / "fig11_bt50k_trend_correlation.png")


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig1_cumulative_pnl()
    fig2_group_sharpe()
    if (RESULTS / "mc_bootstrap_sharpe.csv").exists():
        fig3_montecarlo()
    if (RESULTS / "divergence_monthly.csv").exists():
        fig4_divergence()
    fig5_signal()
    if (RESULTS / "bt50k_daily.csv").exists():
        full, five = load_account("bt50k"), load_account("bt50k_5y")
        fig6_equity(full)
        fig_account(full, "fig7_bt50k_signal_vol_margin.png", (-2.2, 2.7))
        fig_mc(full, "fig8_bt50k_montecarlo.png", ["Frozen spec", "Follow-the-ECB", "Long-only", "Walk-forward threshold"], 12)
        with PdfPages(FIGURES / "bt50k_5y_pages.pdf") as pdf:       # the two five-year pages in one file
            fig_account(five, "fig9_bt50k_5y_account.png", (-2.2, 1.0), pdf=pdf,
                        equity_title="Last five years: a new €50,000 account, September 2021 to August 2026 (per-euro sizing, after costs)")
            fig_mc(five, "fig10_bt50k_5y_montecarlo.png", ["Frozen spec", "Follow-the-ECB", "Long-only", "Walk-forward threshold"], 6, pdf=pdf)
    if (RESULTS / "trendcorr_monthly_pnl.csv").exists():
        fig11_trend_correlation()


if __name__ == "__main__":
    main()
