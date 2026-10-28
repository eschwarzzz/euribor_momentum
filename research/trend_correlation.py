"""Correlation of the Euribor frozen specification with the AlgoGators trend-following book (appendix B).

The trend book is the per-market daily P&L panel of one backtest run (34 CME markets, USD, April 2011 to April
2026). It is not part of this repository: point ``--panel`` or the ``TREND_PANEL`` environment variable at the
``pnl_panel.csv`` file. The outputs it leaves in results/ (trendcorr_*.csv, trendcorr.json) are committed, so the
appendix and figure 11 can be rebuilt without it.
"""
import argparse
import json
import os

import numpy as np
import pandas as pd

from euribor.backtest import daily_pnl
from euribor.config import ECB_RULE, RESULTS, SPEC
from euribor.data import load_continuous, load_positions

DEFAULT_PANEL = os.environ.get("TREND_PANEL", "/Users/user/Desktop/trend_risk/Trend Following Risk Manager/phase2/pnl_panel.csv")
RATES = ["ZT", "ZF", "ZN", "UB"]


def block_bootstrap_correlation(a, b, rng, n=10000, block=12):
    a, b = a.values, b.values
    T = len(a)
    n_blocks = int(np.ceil(T / block))
    starts = rng.integers(0, T, (n, n_blocks))
    idx = ((starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n, -1) % T)[:, :T]
    A, B = a[idx], b[idx]
    A, B = A - A.mean(1, keepdims=True), B - B.mean(1, keepdims=True)
    return (A * B).sum(1) / np.sqrt((A ** 2).sum(1) * (B ** 2).sum(1))


def main(panel_path=DEFAULT_PANEL):
    pd.set_option("display.width", 220)
    rng = np.random.default_rng(11)
    T = pd.read_csv(panel_path, index_col=0, parse_dates=True)
    fx = [c for c in T.columns if c.startswith("6")]
    cont = load_continuous()
    P = load_positions()
    ecb, frozen = P[ECB_RULE], P[SPEC]
    account = pd.read_csv(RESULTS / "bt50k_daily.csv", index_col=0, parse_dates=True)["excess"]
    X = pd.DataFrame({"Whole trend book": T.sum(axis=1), "US rates sleeve": T[RATES].sum(axis=1), "Currency sleeve": T[fx].sum(axis=1),
                      "Everything except rates": T.drop(columns=RATES).sum(axis=1), "Frozen spec, 1 contract": daily_pnl(frozen, cont)[0],
                      "Frozen spec, EUR 50k account": account, "Follow-the-ECB, 1 contract": daily_pnl(ecb, cont)[0]}).loc[T.index[0]:"2026-08-31"].dropna()
    trend_cols, euribor_cols = list(X.columns[:4]), list(X.columns[4:])
    E1, TB = euribor_cols[0], trend_cols[0]
    freqs = {"daily": X, "weekly": X.resample("W-FRI").sum(), "monthly": X.resample("ME").sum(), "quarterly": X.resample("QE").sum(),
             "annual": X.resample("YE").sum()}
    M = freqs["monthly"]
    print(f"window {X.index[0].date()} to {X.index[-1].date()}: {len(X)} days, {len(M)} months; trend book rates sleeve = {RATES}, currency sleeve = {fx}")

    # 1. correlations by frequency
    BYF = pd.DataFrame({f"{k} (n={len(v)})": v.corr().loc[E1, trend_cols] for k, v in freqs.items()})
    print(f"\n[1] Correlation of '{E1}' with the trend book, by frequency:")
    print(BYF.round(2).to_string())
    MC = M.corr().loc[euribor_cols, trend_cols]
    print("\n[1b] Monthly correlations, all Euribor versions:")
    print(MC.round(2).to_string())
    # 2. sub-periods and bootstrap
    SUB = pd.DataFrame({f"{a}-{b}": dict(months=len(M.loc[a:b]), **{c: M.loc[a:b, E1].corr(M.loc[a:b, c]) for c in trend_cols[:2]})
                        for a, b in [("2011", "2015"), ("2016", "2020"), ("2021", "2026")]}).T
    print("\n[2] Monthly correlation by sub-period:")
    print(SUB.round(2).to_string())
    boot = {c: block_bootstrap_correlation(M[E1], M[c], rng) for c in trend_cols}
    BI = pd.DataFrame({c: dict(observed=M[E1].corr(M[c]), p05=np.percentile(v, 5), p50=np.percentile(v, 50), p95=np.percentile(v, 95))
                       for c, v in boot.items()}).T
    print("\n[2b] Block bootstrap (12-month blocks, 10,000 draws) of the monthly correlation:")
    print(BI.round(2).to_string())
    # 3. calendar years and conditional months
    A = freqs["annual"]
    YR = pd.DataFrame({"trend_book_usd": A[TB], "trend_rates_usd": A["US rates sleeve"], "trend_fx_usd": A["Currency sleeve"], "euribor_bp": A[E1] * 100})
    YR.index = YR.index.year
    YR["trend_in_vol_units"] = A[TB].values / (M[TB].std() * np.sqrt(12))
    YR["euribor_in_vol_units"] = A[E1].values / (M[E1].std() * np.sqrt(12))
    print("\n[3] Calendar years (2011 from April, 2026 to April); vol units = year's P&L / own annualised volatility:")
    print(YR.round(2).to_string())

    def conditional(idx):
        return dict(euribor_mean_bp=M.loc[idx, E1].mean() * 100, euribor_share_positive=(M.loc[idx, E1] > 0).mean(), trend_mean_usd=M.loc[idx, TB].mean())

    CD = pd.DataFrame({"trend book's 15 worst months": conditional(M[TB].nsmallest(15).index), "trend book's 15 best months": conditional(M[TB].nlargest(15).index),
                       "all months": conditional(M.index)}).T
    print("\n[3b] Euribor frozen spec, 1 contract, conditional on the trend book's month:")
    print(CD.round(2).to_string())
    # 4. risk-weighted combinations
    sharpe = lambda x: x.mean() / x.std() * np.sqrt(12)      # noqa: E731
    Z = M[[TB, E1]] / M[[TB, E1]].std()

    def drawdown(x):
        c = x.cumsum()
        return (c - c.cummax()).min() / (x.std() * np.sqrt(12))

    CB = pd.DataFrame({f"{round(w * 100)}/{round((1 - w) * 100)}": dict(sharpe=sharpe(w * Z[TB] + (1 - w) * Z[E1]), maxdd_in_annual_vols=drawdown(w * Z[TB] + (1 - w) * Z[E1]))
                       for w in (1.0, 0.8, 0.5, 0.0)}).T
    print("\n[4] Risk-weighted combinations, trend book / Euribor (monthly, Apr 2011 - Apr 2026):")
    print(CB.round(2).to_string())

    BYF.to_csv(RESULTS / "trendcorr_by_frequency.csv")
    MC.to_csv(RESULTS / "trendcorr_monthly.csv")
    YR.to_csv(RESULTS / "trendcorr_by_year.csv")
    M.to_csv(RESULTS / "trendcorr_monthly_pnl.csv")
    json.dump(dict(subperiods=SUB.to_dict("index"), bootstrap=BI.to_dict("index"), conditional=CD.to_dict("index"), combinations=CB.to_dict("index")),
              open(RESULTS / "trendcorr.json", "w"), indent=1, default=float)
    from euribor.charts import fig11_trend_correlation
    fig11_trend_correlation()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--panel", default=DEFAULT_PANEL, help="path to the trend book's per-market daily P&L panel (pnl_panel.csv)")
    main(parser.parse_args().panel)
