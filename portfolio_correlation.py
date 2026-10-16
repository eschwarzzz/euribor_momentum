"""Correlation of the Euribor frozen specification with the AlgoGators trend-following book.
Trend book: per-market daily P&L of backtest run TREND_FOLLOWING_20260505_010930_346 (34 CME markets, USD, Apr 2011 - Apr 2026), read from the
trend_risk project (phase2/pnl_panel.csv). Euribor: daily P&L of the frozen spec on one contract (price points), the EUR 50,000 account's
daily return, and the plain follow-the-ECB rule. Correlations at daily to annual frequency, by sub-period, with a block-bootstrap interval;
Euribor P&L in the trend book's worst and best months; Sharpe of risk-weighted combinations. Chart: results/fig11_bt50k_trend_correlation.png."""
import numpy as np, pandas as pd, os, sys, json, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT); D = f"{ROOT}/data"; R = f"{ROOT}/results"
from backtest import daily_pnl
TREND = "/Users/user/Desktop/trend_risk/Trend Following Risk Manager/phase2/pnl_panel.csv"
rng = np.random.default_rng(11)

# ---------- inputs ----------
T = pd.read_csv(TREND, index_col=0, parse_dates=True); rates = ["ZT", "ZF", "ZN", "UB"]; fx = [c for c in T.columns if c.startswith("6")]
F = pd.read_csv(f"{D}/features_monthly.csv", index_col=0, parse_dates=True); cont = pd.read_csv(f"{D}/euribor_futures_continuous.csv", index_col=0, parse_dates=True)
P = pd.read_csv(f"{R}/monthly_positions.csv", index_col=0, parse_dates=True); G = pd.read_csv(f"{R}/prior_group_scores.csv", index_col=0, parse_dates=True)
ecb = P["BM follow-the-ECB (-sign of DFR 3M change)"]; score = G[["R", "I", "S"]].mean(axis=1); frozen = pd.Series(np.where(score.abs() > 0.5, np.sign(score), ecb), index=F.index)
acct = pd.read_csv(f"{R}/bt50k_daily.csv", index_col=0, parse_dates=True)["ret"]
X = pd.DataFrame({"Whole trend book": T.sum(axis=1), "US rates sleeve": T[rates].sum(axis=1), "Currency sleeve": T[fx].sum(axis=1), "Everything except rates": T.drop(columns=rates).sum(axis=1),
                  "Frozen spec, 1 contract": daily_pnl(frozen, cont)[0], "Frozen spec, EUR 50k account": acct, "Follow-the-ECB, 1 contract": daily_pnl(ecb, cont)[0]}).loc[T.index[0]:"2026-08-31"].dropna()
TC = list(X.columns[:4]); EC = list(X.columns[4:]); E1 = EC[0]; TB = TC[0]
freqs = {"daily": X, "weekly": X.resample("W-FRI").sum(), "monthly": X.resample("ME").sum(), "quarterly": X.resample("QE").sum(), "annual": X.resample("YE").sum()}; M = freqs["monthly"]
pd.set_option("display.width", 220)
print(f"window {X.index[0].date()} to {X.index[-1].date()}: {len(X)} days, {len(M)} months; trend book rates sleeve = {rates}, currency sleeve = {fx}")

# ---------- 1. correlations by frequency ----------
BYF = pd.DataFrame({f"{k} (n={len(v)})": v.corr().loc[E1, TC] for k, v in freqs.items()}); print(f"\n[1] Correlation of '{E1}' with the trend book, by frequency:"); print(BYF.round(2).to_string())
MC = M.corr().loc[EC, TC]; print("\n[1b] Monthly correlations, all Euribor versions:"); print(MC.round(2).to_string())

# ---------- 2. sub-periods and block-bootstrap interval for the monthly correlation ----------
SUB = pd.DataFrame({f"{a}-{b}": dict(months=len(M.loc[a:b]), **{c: M.loc[a:b, E1].corr(M.loc[a:b, c]) for c in TC[:2]}) for a, b in [("2011", "2015"), ("2016", "2020"), ("2021", "2026")]}).T
print("\n[2] Monthly correlation by sub-period:"); print(SUB.round(2).to_string())
def boot_corr(a, b, n=10000, L=12):
    a, b = a.values, b.values; Tn = len(a); nb = int(np.ceil(Tn / L)); st = rng.integers(0, Tn, (n, nb)); ii = ((st[:, :, None] + np.arange(L)[None, None, :]).reshape(n, -1) % Tn)[:, :Tn]
    A, B = a[ii], b[ii]; A = A - A.mean(1, keepdims=True); B = B - B.mean(1, keepdims=True); return (A * B).sum(1) / np.sqrt((A ** 2).sum(1) * (B ** 2).sum(1))
BOOT = {c: boot_corr(M[E1], M[c]) for c in TC}; BI = pd.DataFrame({c: dict(observed=M[E1].corr(M[c]), p05=np.percentile(v, 5), p50=np.percentile(v, 50), p95=np.percentile(v, 95)) for c, v in BOOT.items()}).T
print("\n[2b] Block bootstrap (12-month blocks, 10,000 draws) of the monthly correlation:"); print(BI.round(2).to_string())

# ---------- 3. calendar years, and Euribor in the trend book's worst and best months ----------
A = freqs["annual"]; YR = pd.DataFrame({"trend_book_usd": A[TB], "trend_rates_usd": A["US rates sleeve"], "trend_fx_usd": A["Currency sleeve"], "euribor_bp": A[E1] * 100}); YR.index = YR.index.year
YR["trend_in_vol_units"] = A[TB].values / (M[TB].std() * np.sqrt(12)); YR["euribor_in_vol_units"] = A[E1].values / (M[E1].std() * np.sqrt(12))
print("\n[3] Calendar years (2011 from April, 2026 to April); vol units = year's P&L / own annualised volatility:"); print(YR.round(2).to_string())
def cond(idx): return dict(euribor_mean_bp=M.loc[idx, E1].mean() * 100, euribor_share_positive=(M.loc[idx, E1] > 0).mean(), trend_mean_usd=M.loc[idx, TB].mean())
CD = pd.DataFrame({"trend book's 15 worst months": cond(M[TB].nsmallest(15).index), "trend book's 15 best months": cond(M[TB].nlargest(15).index), "all months": cond(M.index)}).T
print("\n[3b] Euribor frozen spec, 1 contract, conditional on the trend book's month:"); print(CD.round(2).to_string())

# ---------- 4. combinations (each stream scaled to equal monthly volatility, then weighted) ----------
sh = lambda x: x.mean() / x.std() * np.sqrt(12); Z = M[[TB, E1]] / M[[TB, E1]].std()
def dd(x): c = x.cumsum(); return (c - c.cummax()).min() / (x.std() * np.sqrt(12))
CB = pd.DataFrame({f"{round(w*100)}/{round((1-w)*100)}": dict(sharpe=sh(w * Z[TB] + (1 - w) * Z[E1]), maxdd_in_annual_vols=dd(w * Z[TB] + (1 - w) * Z[E1])) for w in (1.0, 0.8, 0.5, 0.0)}).T
print("\n[4] Risk-weighted combinations, trend book / Euribor (monthly, Apr 2011 - Apr 2026):"); print(CB.round(2).to_string())

BYF.to_csv(f"{R}/trendcorr_by_frequency.csv"); MC.to_csv(f"{R}/trendcorr_monthly.csv"); YR.to_csv(f"{R}/trendcorr_by_year.csv"); M.to_csv(f"{R}/trendcorr_monthly_pnl.csv")
json.dump(dict(subperiods=SUB.to_dict("index"), bootstrap=BI.to_dict("index"), conditional=CD.to_dict("index"), combinations=CB.to_dict("index")), open(f"{R}/trendcorr.json", "w"), indent=1, default=float)

# ---------- chart ----------
SURF, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"; BLUE, VIOLET = "#2a78d6", "#4a3aa7"          # Euribor frozen spec = blue as in fig6-10; trend book = violet
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"], "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
                     "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF})
def style(ax):
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=1); ax.set_axisbelow(True); ax.tick_params(length=0)
fig, axes = plt.subplots(2, 1, figsize=(12, 8.4), dpi=200, gridspec_kw={"height_ratios": [1, 1.15]})
ax = axes[0]; style(ax); W = 36; rc = M[E1].rolling(W).corr(M[TB]); rr = M[E1].rolling(W).corr(M["US rates sleeve"]); band = 2 / np.sqrt(W)
ax.axhspan(-band, band, color=GRID, alpha=0.55, linewidth=0); ax.axhline(0, color=AXIS, linewidth=1)
ax.plot(rr.index, rr.values, color=INK2, linewidth=1.1, linestyle=(0, (4, 2)), label="with its US rates sleeve"); ax.plot(rc.index, rc.values, color=VIOLET, linewidth=2, solid_joinstyle="round", label="with the whole trend book")
ax.set_ylim(-0.8, 0.8); ax.set_ylabel("Correlation", fontsize=9); ax.legend(frameon=False, fontsize=8.5, loc="upper left", ncol=2)
ax.text(rc.dropna().index[0], -band + 0.03, "grey band = range expected from two unrelated series (±2 standard errors)", fontsize=8, color=MUTED, va="bottom")
ax.set_title(f"Euribor frozen spec against the trend-following book: rolling {W}-month correlation of monthly P&L (full-window value {M[E1].corr(M[TB]):+.2f})", loc="left", fontsize=11.5, fontweight="semibold", pad=8)
ax = axes[1]; style(ax); x = np.arange(len(YR)); bw = 0.36
ax.bar(x - bw / 2 - 0.02, YR["trend_in_vol_units"], width=bw, color=VIOLET, label="Trend-following book"); ax.bar(x + bw / 2 + 0.02, YR["euribor_in_vol_units"], width=bw, color=BLUE, label="Euribor frozen spec, 1 contract")
ax.axhline(0, color=AXIS, linewidth=1); ax.set_xticks(x); ax.set_xticklabels(YR.index); ax.set_ylabel("Year's P&L ÷ own annual volatility", fontsize=9); ax.legend(frameon=False, fontsize=8.5, loc="upper left", ncol=2)
ax.set_ylim(None, max(YR["trend_in_vol_units"].max(), YR["euribor_in_vol_units"].max()) * 1.25)
ax.set_title("They earn in different years: each year's P&L in units of the strategy's own annual volatility (2011 from April, 2026 to April)", loc="left", fontsize=11, fontweight="semibold", pad=8)
fig.subplots_adjust(left=0.065, right=0.985, top=0.94, bottom=0.05, hspace=0.3); fig.savefig(f"{R}/fig11_bt50k_trend_correlation.png"); plt.close(fig); print("\nfig11 written")
