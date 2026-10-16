"""EUR 50,000 account backtest of the frozen specification, with its Monte Carlo set in account terms.

Sizing: at each month-end, contracts = round(target x equity / (sigma x point value)), where sigma is
70% of the trailing 60-day realised volatility plus 30% of its expanding long-run mean (annualised, price
points). Positions are resized monthly with the signal, whole contracts only. Costs are per side in bp, a roll
costs two sides, initial margin is held flat through history and cash earns nothing.

The Monte Carlo set mirrors montecarlo.py: block bootstrap of Sharpe, final equity and drawdown; circular-shift
and block-permutation nulls on the direction path (position sizes stay with their dates); deflated Sharpe.
The last-five-years section opens a fresh account on 1 September 2021.
"""
import json
import warnings

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, skew

from .backtest import daily_pnl, metrics
from .config import (ACCOUNT_COST_BP, ACCOUNT_START, ACCOUNT_START_5Y, ECB_RULE, INITIAL_MARGIN_EUR, OOS_END, POINT_VALUE_EUR,
                     RESULTS, SUBPERIODS, TREND_12M)
from .data import load_continuous, load_features, load_group_scores, load_pnl_curves, load_positions, sharpe_monthly
from .montecarlo import deflated_sharpe, expected_max_sharpe
from .signals import frozen_spec, risk_score, walk_forward_threshold

warnings.filterwarnings("ignore")

CAPITAL = 50_000.0
TARGET_VOL = 0.10
COST = ACCOUNT_COST_BP / 100          # price points per contract per side
N_BOOT = 10_000
QUANTILES = [5, 25, 50, 75, 95]
FULL_KEYS = {"Frozen spec": "Frozen spec, 10% vol target", "Walk-forward threshold": "Walk-forward threshold, 10% vol",
             "Follow-the-ECB": "Follow-the-ECB only, 10% vol", "Long-only": "Long-only, 10% vol"}
FIVE_KEYS = {k: v for k, v in FULL_KEYS.items() if k != "Walk-forward threshold"}


# ---------------------------------------------------------------- simulation
def instrument(cont):
    """Daily inputs for the 2nd contract: price change, roll flag, 60-day vol and the blended sizing vol (points per year)."""
    vol60 = cont["chg1"].rolling(60).std() * np.sqrt(252)
    roll = ((cont["exp1"] != cont["exp1"].shift(1)) & (np.arange(len(cont)) > 0)).astype(float)
    return dict(chg=cont["chg1"].fillna(0.0), roll=roll, vol60=vol60, vol=0.7 * vol60 + 0.3 * vol60.expanding(250).mean())


def simulate(pos_m, inst, decision_index, target=TARGET_VOL, vol=None, fixed=None, cost=COST, start=ACCOUNT_START, end=OOS_END,
             capital=CAPITAL):
    """Run the account. ``pos_m`` is the direction decided at each month-end (in ``decision_index``) and held from the next day.

    Returns a daily frame (contracts, pnl, fees, equity, margin) and a monthly decision frame.
    """
    chg, roll, vol60 = inst["chg"], inst["roll"], inst["vol60"]
    vol = inst["vol"] if vol is None else vol
    days = chg.loc[start:end].index
    decisions = [t for t in decision_index if pd.Timestamp(start) - pd.offsets.MonthEnd(1) <= t < pd.Timestamp(end)]
    equity, previous = capital, 0.0
    daily_rows, monthly_rows = [], []
    for t in decisions:
        month_days = days[(days > t) & (days <= t + pd.offsets.MonthEnd(1))]
        if len(month_days) == 0:
            continue
        sigma = vol.loc[:t].iloc[-1]
        signal = pos_m.get(t, 0.0)
        signal = 0.0 if pd.isna(signal) else float(signal)
        n = float(fixed) if fixed is not None else np.round(target * equity / (sigma * POINT_VALUE_EUR))
        n = n * abs(signal) if abs(signal) <= 1 else n
        contracts = np.sign(signal) * n
        equity_start = equity
        c, r = chg.loc[month_days].values, roll.loc[month_days].values
        fees = np.zeros(len(month_days))
        fees[0] = abs(contracts - previous) * cost * POINT_VALUE_EUR
        fees += r * abs(contracts) * 2 * cost * POINT_VALUE_EUR
        pnl = contracts * c * POINT_VALUE_EUR - fees
        for day, x, fee in zip(month_days, pnl, fees):
            equity += x
            daily_rows.append((day, contracts, x, fee, equity))
        monthly_rows.append(dict(date=t, signal=signal, sigma_bp=sigma * 100, contracts=contracts, equity_start=equity_start,
                                 traded=abs(contracts - previous), pnl=equity - equity_start, ret=(equity - equity_start) / equity_start,
                                 fees=fees.sum(), risk_fcst=abs(contracts) * sigma * POINT_VALUE_EUR / equity_start, chg_pts=c.sum(),
                                 rolls=r.sum()))
        previous = contracts
    d = pd.DataFrame(daily_rows, columns=["date", "contracts", "pnl", "fees", "equity"]).set_index("date")
    d["ret"] = d["pnl"] / d["equity"].shift(1).fillna(capital)
    d["margin"] = d["contracts"].abs() * INITIAL_MARGIN_EUR
    d["margin_pct"] = d["margin"] / d["equity"]
    v = vol60.reindex(d.index)
    d["margin_stress"] = d["contracts"].abs() * INITIAL_MARGIN_EUR * np.maximum(1.0, v / v.iloc[-1])
    d["margin_stress_pct"] = d["margin_stress"] / d["equity"]
    return d, pd.DataFrame(monthly_rows).set_index("date")


def stats(d, m, capital=CAPITAL):
    """Account statistics from the daily and monthly frames."""
    r, eq, mr = d["ret"], d["equity"], m["ret"]
    n = len(r)
    drawdown = eq / eq.cummax() - 1
    return dict(final_equity=eq.iloc[-1], pnl_eur=eq.iloc[-1] - capital, cagr_pct=((eq.iloc[-1] / capital) ** (252 / n) - 1) * 100,
                vol_pct=r.std() * np.sqrt(252) * 100, sharpe=r.mean() / r.std() * np.sqrt(252), sharpe_monthly=mr.mean() / mr.std() * np.sqrt(12),
                maxdd_pct=drawdown.min() * 100, maxdd_eur=(eq - eq.cummax()).min(), worst_month_pct=mr.min() * 100,
                best_month_pct=mr.max() * 100, hit_pct=(mr > 0).mean() * 100, avg_contracts=d["contracts"].abs().mean(),
                max_contracts=d["contracts"].abs().max(), avg_margin_pct=d["margin_pct"].mean() * 100,
                peak_margin_pct=d["margin_pct"].max() * 100, peak_margin_stress_pct=d["margin_stress_pct"].max() * 100,
                fees_eur=d["fees"].sum(), contracts_traded=m["traded"].sum() + 2 * (m["rolls"] * m["contracts"].abs()).sum())


def by_year(d, m, five_year=False):
    g = d.groupby(d.index.year)
    table = {"pnl_eur": g["pnl"].sum(), "ret_pct": g["ret"].apply(lambda x: (1 + x).prod() - 1) * 100, "equity_end": g["equity"].last(),
             "avg_contracts": g["contracts"].mean()}
    if five_year:
        table["avg_margin_pct"] = g["margin_pct"].mean() * 100
    else:
        table["sigma_bp"] = m["sigma_bp"].groupby(m.index.year + (m.index.month == 12)).mean()
    table["peak_margin_pct"] = g["margin_pct"].max() * 100
    return pd.DataFrame(table)


def drawdown_episode(eq):
    """Worst drawdown: depth, peak date, trough date, recovery date (or None) and longest run under water in days."""
    dd = eq / eq.cummax() - 1
    trough = dd.idxmin()
    peak = eq.loc[:trough].idxmax()
    recovered = eq.loc[trough:][eq.loc[trough:] >= eq.loc[peak]].index
    under_water = int((dd < 0).astype(int).groupby((dd == 0).cumsum()).sum().max())
    return dd.min(), peak, trough, (recovered[0] if len(recovered) else None), under_water


# ---------------------------------------------------------------- Monte Carlo in account terms
def bootstrap_paths(M, rng, capital=CAPITAL, n=N_BOOT, block=12):
    """Vectorised circular block bootstrap of monthly account returns; the same resampled months for every strategy."""
    T = len(M)
    n_blocks = int(np.ceil(T / block))
    starts = rng.integers(0, T, (n, n_blocks))
    idx = ((starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n, -1) % T)[:, :T]
    boot, paths = {}, {}
    for k in M.columns:
        x = M[k].values[idx]
        equity = capital * np.cumprod(1 + x, axis=1)
        peak = np.maximum.accumulate(np.concatenate([np.full((n, 1), capital), equity], axis=1), axis=1)[:, 1:]
        boot[k] = pd.DataFrame({"sharpe": x.mean(1) / x.std(1) * np.sqrt(12), "final_equity": equity[:, -1],
                                "cagr_pct": ((equity[:, -1] / capital) ** (12 / T) - 1) * 100, "maxdd_pct": (equity / peak - 1).min(1) * 100,
                                "eq_1y": equity[:, 11], "eq_5y": equity[:, 59]})
        paths[k] = equity
    return boot, paths


def bootstrap_sharpe_table(boot, strategies):
    """Sharpe percentiles and probability of beating the two reference strategies."""
    B = pd.DataFrame({k: dict(mean=boot[k]["sharpe"].mean(), **{f"p{p:02d}": np.percentile(boot[k]["sharpe"], p) for p in QUANTILES},
                              prob_gt0=(boot[k]["sharpe"] > 0).mean()) for k in boot}).T
    for k in strategies:
        B.loc[k, "prob_beats_longonly"] = (boot[k]["sharpe"] > boot["Long-only"]["sharpe"]).mean()
        B.loc[k, "prob_beats_ecb"] = (boot[k]["sharpe"] > boot["Follow-the-ECB"]["sharpe"]).mean()
    return B


def pnl_summary(boot, capital=CAPITAL):
    """Percentiles of final equity, CAGR, drawdown and 1- and 5-year P&L from the bootstrap paths."""
    out = {}
    for k, b in boot.items():
        pct = lambda col, p: np.percentile(b[col], p)        # noqa: E731
        out[k] = dict(final_p05=pct("final_equity", 5), final_p25=pct("final_equity", 25), final_p50=pct("final_equity", 50),
                      final_p75=pct("final_equity", 75), final_p95=pct("final_equity", 95), prob_end_below_start=(b["final_equity"] < capital).mean(),
                      cagr_p05=pct("cagr_pct", 5), cagr_p50=pct("cagr_pct", 50), cagr_p95=pct("cagr_pct", 95),
                      maxdd_p50=pct("maxdd_pct", 50), maxdd_p05=pct("maxdd_pct", 5), maxdd_p01=pct("maxdd_pct", 1),
                      prob_dd_gt20=(b["maxdd_pct"] < -20).mean(), prob_dd_gt30=(b["maxdd_pct"] < -30).mean(),
                      pnl1y_p05=pct("eq_1y", 5) - capital, pnl1y_p50=pct("eq_1y", 50) - capital, pnl1y_p95=pct("eq_1y", 95) - capital,
                      prob_loss_1y=(b["eq_1y"] < capital).mean(), pnl5y_p05=pct("eq_5y", 5) - capital, pnl5y_p50=pct("eq_5y", 50) - capital,
                      pnl5y_p95=pct("eq_5y", 95) - capital, prob_loss_5y=(b["eq_5y"] < capital).mean())
    return pd.DataFrame(out).T


def null_test(m, rng, block=12, n_perm=3000, cost=COST):
    """No-skill nulls: the direction path is shifted or block-shuffled in time while contracts-per-euro stay on their dates."""
    sign = np.sign(m["contracts"]).values
    weight = (m["contracts"].abs() / m["equity_start"]).values
    move, rolls = m["chg_pts"].values, m["rolls"].values
    T = len(m)

    def returns(s):
        p = s * weight
        traded = np.abs(np.diff(p, prepend=0.0))
        return p * move * POINT_VALUE_EUR - traded * cost * POINT_VALUE_EUR - rolls * np.abs(p) * 2 * cost * POINT_VALUE_EUR

    observed = sharpe_monthly(returns(sign))
    shifts = np.array([sharpe_monthly(returns(np.roll(sign, s))) for s in range(6, T - 6)])
    n_blocks = int(np.ceil(T / block))
    perm = np.empty(n_perm)
    for i in range(n_perm):
        order = rng.permutation(n_blocks)
        idx = np.concatenate([np.arange(b * block, min((b + 1) * block, T)) for b in order])
        perm[i] = sharpe_monthly(returns(sign[idx]))
    summary = dict(observed=observed, shift_mean=shifts.mean(), shift_sd=shifts.std(), p_shift=(shifts >= observed).mean(),
                   perm_mean=perm.mean(), perm_sd=perm.std(), perm_p95=np.percentile(perm, 95), p_perm=(perm >= observed).mean())
    return summary, perm


def deflated_table(M, trial_sr, n_trials_total=70):
    """Deflated Sharpe for the number of variants on file (45) and for the total number of trials run in the project (70)."""
    sr0_file = expected_max_sharpe(trial_sr)
    sr0_total = expected_max_sharpe(trial_sr, n_trials_total)
    rows = {k: dict(sharpe=sharpe_monthly(M[k]), skew=skew(M[k]), kurt=kurtosis(M[k], fisher=False),
                    dsr_45=deflated_sharpe(M[k], sr0_file), dsr_70=deflated_sharpe(M[k], sr0_total)) for k in M.columns}
    return pd.DataFrame(rows).T, sr0_file * np.sqrt(12), sr0_total * np.sqrt(12)


def save_monte_carlo(tag, boot, paths, perm, mc_json):
    cols = ["sharpe", "final_equity", "maxdd_pct", "eq_1y", "eq_5y"]
    pd.DataFrame({f"{k}|{c}": boot[k][c] for k in boot for c in cols}).to_csv(RESULTS / f"{tag}_bootstrap.csv", index=False)
    pd.DataFrame({f"p{p:02d}": np.percentile(paths["Frozen spec"], p, axis=0) for p in QUANTILES}).to_csv(RESULTS / f"{tag}_bootstrap_fan.csv", index=False)
    pd.DataFrame({"perm_sharpe": perm}).to_csv(RESULTS / f"{tag}_null_perm.csv", index=False)
    json.dump(mc_json, open(RESULTS / f"{tag}_mc.json", "w"), indent=1, default=float)


def print_variants(S):
    print(S[["final_equity", "pnl_eur", "cagr_pct", "vol_pct", "sharpe", "sharpe_monthly", "maxdd_pct", "maxdd_eur", "worst_month_pct",
             "hit_pct"]].round(2).to_string())
    print(S[["avg_contracts", "max_contracts", "avg_margin_pct", "peak_margin_pct", "peak_margin_stress_pct", "fees_eur",
             "contracts_traded"]].round(2).to_string())


# ---------------------------------------------------------------- the two windows
def main():
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 30)
    F, _, _ = load_features()
    idx = F.index
    cont = load_continuous()
    P, G = load_positions(), load_group_scores()
    ecb = P[ECB_RULE]
    score = risk_score(G)
    frozen = frozen_spec(ecb, score)
    gov, ois = instrument(cont), instrument(load_continuous(ois=True))
    vol60 = gov["vol60"]
    pos_wf, tau_path = walk_forward_threshold(ecb, score, cont, years=range(2007, 2027))
    ones = pd.Series(1.0, index=idx)

    def run(variants, start):
        """Simulate every variant; a variant's own ``start`` or ``inst`` overrides the defaults."""
        runs = {}
        for name, spec in variants.items():
            kw = dict(spec)
            kw.setdefault("inst", gov)
            kw.setdefault("start", start)
            runs[name] = simulate(decision_index=idx, **kw)
        return runs, pd.DataFrame({k: stats(*v) for k, v in runs.items()}).T

    variants = {
        "Frozen spec, 10% vol target": dict(pos_m=frozen),
        "Walk-forward threshold, 10% vol": dict(pos_m=pos_wf),
        "Follow-the-ECB only, 10% vol": dict(pos_m=ecb),
        "Long-only, 10% vol": dict(pos_m=ones),
        "12M trend, 10% vol": dict(pos_m=P[TREND_12M]),
        "Frozen, 5% vol target": dict(pos_m=frozen, target=0.05),
        "Frozen, 15% vol target": dict(pos_m=frozen, target=0.15),
        "Frozen, 20% vol target": dict(pos_m=frozen, target=0.20),
        "Frozen, 60-day vol only (no long-run blend)": dict(pos_m=frozen, vol=vol60),
        "Frozen, fixed 1 contract": dict(pos_m=frozen, fixed=1),
        "Frozen, fixed 3 contracts": dict(pos_m=frozen, fixed=3),
        "Frozen, cost 0.5 bp/side": dict(pos_m=frozen, cost=0.005),
        "Frozen, cost 1 bp/side": dict(pos_m=frozen, cost=0.01),
        "Frozen, cost 2 bp/side": dict(pos_m=frozen, cost=0.02),
        "Frozen, start Jan 2002": dict(pos_m=frozen, start="2002-01-01"),
        "Frozen, OIS-spliced prices 2005-14": dict(pos_m=frozen, inst=ois),
        "Follow-the-ECB, OIS-spliced prices": dict(pos_m=ecb, inst=ois),
    }
    runs, S = run(variants, ACCOUNT_START)
    print(f"walk-forward tau path: {tau_path}")
    print(f"\n[0] Account results, EUR 50,000 start, Jan 2008 - Aug 2026, cost {ACCOUNT_COST_BP} bp per side:")
    print_variants(S)
    d, m = runs["Frozen spec, 10% vol target"]
    unit = metrics(*daily_pnl(frozen, cont, cost=COST), start=ACCOUNT_START, end=OOS_END)
    print(f"\nunit-position check on this window: Sharpe {unit['sharpe']:+.2f}, {unit['ann_ret_bp']:+.0f} bp/yr, vol {unit['ann_vol_bp']:.0f} bp, "
          f"max DD {unit['maxdd_bp']:.0f} bp")
    yr = by_year(d, m)
    print("\n[0b] Frozen spec by calendar year (contracts signed, + long / - short):")
    print(yr.round(1).to_string())
    sub = {k: {name: (lambda x: x.mean() / x.std() * np.sqrt(252))(runs[k][0]["ret"].loc[a:b]) for name, (a, b) in SUBPERIODS.items()}
           for k in list(variants)[:4]}
    SUBT = pd.DataFrame(sub).T
    print("\n[0c] Sub-period Sharpe (account returns):")
    print(SUBT.round(2).to_string())
    depth, peak, trough, recovered, under = drawdown_episode(d["equity"])
    print(f"\nworst drawdown: {depth * 100:.1f}% from {peak.date()} to {trough.date()}, recovered {recovered.date() if recovered is not None else 'not yet'}; "
          f"longest time under water {under} trading days")
    total, log_ret = m["pnl"].sum(), np.log1p(d["ret"])
    print(f"concentration: best 5 months = {m['pnl'].nlargest(5).sum() / total:.0%} of total P&L, best 10 = {m['pnl'].nlargest(10).sum() / total:.0%}; "
          f"share of log growth 2008-12 {log_ret.loc['2008':'2012'].sum() / log_ret.sum():.0%}, 2013-21 {log_ret.loc['2013':'2021'].sum() / log_ret.sum():.0%}, "
          f"2022-26 {log_ret.loc['2022':].sum() / log_ret.sum():.0%}")
    print(f"direction flips {int((np.sign(m['contracts']).diff().abs() > 0).sum())}, months with a resize {int((m['traded'] > 0).sum())} of {len(m)}; "
          f"margin EUR mean {d['margin'].mean():,.0f}, peak {d['margin'].max():,.0f} on {d['margin'].idxmax().date()}; "
          f"last position {m['contracts'].iloc[-1]:+.0f} contracts on equity {m['equity_start'].iloc[-1]:,.0f}")
    print(f"realised vs target: account vol {S.loc['Frozen spec, 10% vol target', 'vol_pct']:.1f}% vs 10%; forecast risk at entry mean "
          f"{m['risk_fcst'].mean() * 100:.1f}%, range {m['risk_fcst'].min() * 100:.1f}-{m['risk_fcst'].max() * 100:.1f}%; "
          f"months flat (0 contracts) {(m['contracts'] == 0).sum()}")

    # Monte Carlo, full window
    rng = np.random.default_rng(42)
    M = pd.DataFrame({k: runs[v][1]["ret"] for k, v in FULL_KEYS.items()})
    print(f"\nmonthly account returns: {len(M)} months, monthly-based Sharpe:", M.apply(sharpe_monthly).round(2).to_dict())
    boot, paths = bootstrap_paths(M, rng)
    B = bootstrap_sharpe_table(boot, ["Frozen spec", "Walk-forward threshold"])
    print(f"\n[1] Block bootstrap (12-month blocks, {N_BOOT:,} paths of {len(M)} months) of realised Sharpe:")
    print(B.round(2).to_string())
    PLT = pnl_summary(boot)
    print("\n[1b] Bootstrap of the P&L path from EUR 50,000 (final equity after 224 months, drawdown, 1-year and 5-year P&L):")
    print(PLT.round(3).T.to_string())
    nulls, perms = {}, {}
    for name in ["Frozen spec", "Walk-forward threshold", "Follow-the-ECB"]:
        nulls[name], perms[name] = null_test(runs[FULL_KEYS[name]][1], rng)
    print("\n[2] No-skill nulls (direction shifted / block-permuted against the same returns and sizes), p = share of null Sharpes >= observed:")
    print(pd.DataFrame(nulls).T.round(3).to_string())
    curves = load_pnl_curves()
    trial_sr = curves.loc["2008-01-31":OOS_END].resample("ME").sum().apply(lambda s: s.mean() / s.std()).dropna()
    DS, sr0_file, sr0_total = deflated_table(M, trial_sr)
    print(f"\n[3] Deflated Sharpe: expected max Sharpe under the null = {sr0_file:.2f} ({len(trial_sr)} trials) / {sr0_total:.2f} (70 trials), annualised")
    print(DS.round(2).to_string())

    d.to_csv(RESULTS / "bt50k_daily.csv")
    m.to_csv(RESULTS / "bt50k_monthly.csv")
    S.to_csv(RESULTS / "bt50k_variants.csv")
    yr.to_csv(RESULTS / "bt50k_by_year.csv")
    SUBT.to_csv(RESULTS / "bt50k_subperiods.csv")
    pd.DataFrame({k: runs[v][0]["equity"] for k, v in FULL_KEYS.items()}).to_csv(RESULTS / "bt50k_equity_curves.csv")
    save_monte_carlo("bt50k", boot, paths, perms["Frozen spec"],
                     dict(bootstrap_sharpe=B.to_dict("index"), bootstrap_pnl=PLT.to_dict("index"), nulls=nulls, deflated=DS.to_dict("index"),
                          tau_path=tau_path, unit_check={k: float(v) for k, v in unit.items()}, cost_bp=ACCOUNT_COST_BP))

    # Last five years: a fresh account from 1 September 2021
    rng5 = np.random.default_rng(5)
    assert (pos_wf.loc["2021-08-31":OOS_END] == frozen.loc["2021-08-31":OOS_END]).all(), "walk-forward threshold should be 0.5 throughout"
    keep = ["Frozen spec, 10% vol target", "Follow-the-ECB only, 10% vol", "Long-only, 10% vol", "12M trend, 10% vol", "Frozen, 5% vol target",
            "Frozen, 15% vol target", "Frozen, 20% vol target", "Frozen, 60-day vol only (no long-run blend)", "Frozen, fixed 1 contract",
            "Frozen, fixed 3 contracts", "Frozen, cost 0.5 bp/side", "Frozen, cost 1 bp/side", "Frozen, cost 2 bp/side"]
    variants5 = {k: variants[k] for k in keep}
    variants5["Follow-the-ECB, fixed 3 contracts"] = dict(pos_m=ecb, fixed=3)     # separates the override's edge from the sizing effect
    runs5, S5 = run(variants5, ACCOUNT_START_5Y)
    print("\n\n===== LAST FIVE YEARS: fresh EUR 50,000 account, Sep 2021 - Aug 2026 (walk-forward threshold is 0.5 throughout = frozen spec) =====")
    print_variants(S5)
    d5, m5 = runs5["Frozen spec, 10% vol target"]
    unit5 = metrics(*daily_pnl(frozen, cont, cost=COST), start=ACCOUNT_START_5Y, end=OOS_END)
    unit5_ecb = metrics(*daily_pnl(ecb, cont, cost=COST), start=ACCOUNT_START_5Y, end=OOS_END)
    print(f"\nunit-position check: frozen Sharpe {unit5['sharpe']:+.2f}, {unit5['ann_ret_bp']:+.0f} bp/yr, vol {unit5['ann_vol_bp']:.0f} bp, "
          f"max DD {unit5['maxdd_bp']:.0f} bp | follow-the-ECB Sharpe {unit5_ecb['sharpe']:+.2f}, {unit5_ecb['ann_ret_bp']:+.0f} bp/yr")
    x = d["ret"].loc[ACCOUNT_START_5Y:]
    print(f"same window inside the 2008-start account: Sharpe {x.mean() / x.std() * np.sqrt(252):+.2f}, return {((1 + x).prod() - 1) * 100:+.1f}%")
    yr5 = by_year(d5, m5, five_year=True)
    print("\nby calendar year (2021 = Sep-Dec, 2026 = Jan-Aug):")
    print(yr5.round(1).to_string())
    depth5, peak5, trough5, rec5, _ = drawdown_episode(d5["equity"])
    total5 = m5["pnl"].sum()
    fired = ((score.abs() > 0.5) & (np.sign(score) != ecb)).loc["2021-08-31":"2026-07-31"].sum()
    print(f"worst drawdown {depth5 * 100:.1f}% from {peak5.date()} to {trough5.date()}, recovered {rec5.date() if rec5 is not None else 'not yet'}; "
          f"best 5 months = {m5['pnl'].nlargest(5).sum() / total5:.0%} of P&L; direction flips {int((np.sign(m5['contracts']).diff().abs() > 0).sum())}; "
          f"override months {int(fired)}; margin EUR mean {d5['margin'].mean():,.0f}, peak {d5['margin'].max():,.0f}; fees {d5['fees'].sum():,.0f}")
    print(m5[["signal", "sigma_bp", "contracts", "equity_start", "ret"]].round(3).to_string())
    roll60 = M["Frozen spec"].rolling(60).apply(sharpe_monthly)
    print(f"rolling 60-month Sharpe of the 2008-start account: latest {roll60.iloc[-1]:+.2f}, min {roll60.min():+.2f}, median {roll60.median():+.2f}, "
          f"max {roll60.max():+.2f}, share of windows below the latest {(roll60.dropna() < roll60.iloc[-1]).mean():.0%} of {roll60.notna().sum()}")
    M5 = pd.DataFrame({k: runs5[v][1]["ret"] for k, v in FIVE_KEYS.items()})
    print(f"\nmonthly account returns: {len(M5)} months, monthly-based Sharpe:", M5.apply(sharpe_monthly).round(2).to_dict())
    daily_sharpe = lambda x: x.mean() / x.std() * np.sqrt(252)      # noqa: E731
    sy5 = pd.DataFrame({k: runs5[v][0]["ret"].groupby(runs5[v][0].index.year).apply(daily_sharpe) for k, v in FIVE_KEYS.items()})
    sy5.loc["all 60 months"] = [S5.loc[v, "sharpe"] for v in FIVE_KEYS.values()]
    for label, pos in [("Frozen spec, 1 contract", frozen), ("Follow-the-ECB, 1 contract", ecb)]:
        pnl = daily_pnl(pos, cont, cost=COST)[0].loc[ACCOUNT_START_5Y:OOS_END]
        sy5[label] = list(pnl.groupby(pnl.index.year).apply(daily_sharpe)) + [daily_sharpe(pnl)]
    print("Sharpe by calendar year (account returns at a 10% vol target; last two columns one fixed contract):")
    print(sy5.round(2).to_string())
    sy5.to_csv(RESULTS / "bt50k_5y_sharpe_by_year.csv")
    boot5, paths5 = bootstrap_paths(M5, rng5)
    B5 = bootstrap_sharpe_table(boot5, ["Frozen spec"])
    print(f"[1] Block bootstrap (12-month blocks, {N_BOOT:,} paths of {len(M5)} months) of realised Sharpe:")
    print(B5.round(2).to_string())
    PLT5 = pnl_summary(boot5)
    print("[1b] Bootstrap of the P&L path (final equity after 60 months, drawdown, 1-year P&L):")
    print(PLT5.round(3).T.to_string())
    nulls5, perms5 = {}, {}
    for name in ["Frozen spec", "Follow-the-ECB"]:
        nulls5[name], perms5[name] = null_test(runs5[FIVE_KEYS[name]][1], rng5, block=6)
    print("[2] No-skill nulls, 6-month blocks:")
    print(pd.DataFrame(nulls5).T.round(3).to_string())
    DS5, _, _ = deflated_table(M5, trial_sr)
    print("[3] Deflated Sharpe on 60 months:")
    print(DS5.round(2).to_string())

    d5.to_csv(RESULTS / "bt50k_5y_daily.csv")
    m5.to_csv(RESULTS / "bt50k_5y_monthly.csv")
    S5.to_csv(RESULTS / "bt50k_5y_variants.csv")
    yr5.to_csv(RESULTS / "bt50k_5y_by_year.csv")
    pd.DataFrame({k: runs5[v][0]["equity"] for k, v in FIVE_KEYS.items()}).to_csv(RESULTS / "bt50k_5y_equity_curves.csv")
    save_monte_carlo("bt50k_5y", boot5, paths5, perms5["Frozen spec"],
                     dict(bootstrap_sharpe=B5.to_dict("index"), bootstrap_pnl=PLT5.to_dict("index"), nulls=nulls5, deflated=DS5.to_dict("index"),
                          unit_check={k: float(v) for k, v in unit5.items()}, unit_check_ecb={k: float(v) for k, v in unit5_ecb.items()},
                          cost_bp=ACCOUNT_COST_BP))


if __name__ == "__main__":
    main()
