"""One-contract backtest engine and the full set of strategy variants.

Positions are decided at month-end and applied from the next trading day. P&L is in price points of one
contract (0.01 = one basis point), after a per-side cost on every change of position and a two-side cost on
every quarterly roll. Fitted models are walk-forward: refit every month on an expanding window and never see
the month they predict.
"""
import warnings

import numpy as np
import pandas as pd
from sklearn.linear_model import Lasso, LogisticRegression, Ridge

from .config import (COMPOSITE, COMPOSITE_SCALED, ECB_RULE, ECB_RULE_DFR, LOGIT, LONG_ONLY, MIN_TRAIN_MONTHS, OOS_END, OOS_START,
                     RESULTS, RIDGE_10, RIDGE_100, SCORE5, SPEC, SPEC_V1, SPEC_V1_BOTH, SUBPERIODS, TICK_COST, TREND_12M, TREND_3M,
                     PLACEBO)
from .data import core_feature_columns, load_continuous, load_features
from .signals import factor_score, follow_the_ecb, follow_the_ecb_dfr, frozen_spec, prior_composite, risk_score

warnings.filterwarnings("ignore")


def daily_pnl(pos_m, cont, rank=1, cost=TICK_COST):
    """Daily P&L (points) and daily positions from month-end positions ``pos_m`` on contract ``rank``."""
    change = cont[f"chg{rank}"].fillna(0.0)
    expiry = cont[f"exp{rank}"]
    days = pd.DataFrame({"date": change.index})
    decided = pos_m.dropna().rename("pos").rename_axis("date").reset_index()
    pos_d = pd.merge_asof(days, decided, on="date", allow_exact_matches=False).set_index("date")["pos"].fillna(0.0)
    traded = pos_d.diff().abs().fillna(pos_d.abs())
    roll = (expiry != expiry.shift(1)) & (np.arange(len(expiry)) > 0)
    pnl = pos_d * change - traded * cost - roll.astype(float) * pos_d.abs() * 2 * cost
    return pnl, pos_d


def metrics(pnl, pos_d, start=OOS_START, end=OOS_END):
    """Summary statistics over [start, end]: annualised return and vol (bp), Sharpe, drawdown, 10%-vol scaling, hit rate."""
    pnl = pnl.loc[start:end]
    pos_d = pos_d.loc[start:end]
    n = len(pnl)
    empty = dict(ann_ret_bp=np.nan, ann_vol_bp=np.nan, sharpe=np.nan, maxdd_bp=np.nan, cagr_vt=np.nan, maxdd_vt=np.nan,
                 hit=np.nan, months=0, t_stat=np.nan, exposure=np.nan)
    if n < 60 or pnl.std() == 0:
        return empty
    ann_ret = pnl.mean() * 252
    ann_vol = pnl.std() * np.sqrt(252)
    sharpe = ann_ret / ann_vol
    cum = pnl.cumsum()
    maxdd = (cum - cum.cummax()).min()
    leverage = 0.10 / (ann_vol / 100)
    equity = (1 + leverage * pnl / 100).cumprod()
    cagr_vt = equity.iloc[-1] ** (252 / n) - 1
    maxdd_vt = (equity / equity.cummax() - 1).min()
    monthly = pnl.resample("ME").sum()
    held = pos_d.resample("ME").last().reindex(monthly.index)
    monthly = monthly[held.abs() > 0]
    return dict(ann_ret_bp=ann_ret * 100, ann_vol_bp=ann_vol * 100, sharpe=sharpe, maxdd_bp=maxdd * 100,
                cagr_vt=cagr_vt * 100, maxdd_vt=maxdd_vt * 100, hit=(monthly > 0).mean() * 100, months=len(monthly),
                t_stat=sharpe * np.sqrt(n / 252), exposure=pos_d.abs().mean())


def walk_forward(F, y, cols, model="ridge", alpha=10.0, min_train=MIN_TRAIN_MONTHS, oos_start=OOS_START,
                 shuffle_seed=None, sizing="sign"):
    """Monthly refit on all months whose target is known; predict the current month.

    Features are standardised on the training window; predictions are divided by the in-sample prediction
    standard deviation so that ``sizing="scaled"`` positions are comparable across refits.
    ``shuffle_seed`` permutes the training target (placebo).
    """
    X = F[cols].copy()
    idx = X.index
    preds = pd.Series(np.nan, index=idx)
    coefs = {}
    rng = np.random.default_rng(shuffle_seed) if shuffle_seed is not None else None
    for t in idx:
        if t < pd.Timestamp(oos_start):
            continue
        train = idx <= t - pd.offsets.MonthEnd(1)          # y_s is known by t
        Xtr, ytr = X[train], y[train]
        ok = Xtr.notna().all(axis=1) & ytr.notna()
        Xtr, ytr = Xtr[ok], ytr[ok]
        if len(Xtr) < min_train or X.loc[t].isna().any():
            continue
        if rng is not None:
            ytr = pd.Series(rng.permutation(ytr.values), index=ytr.index)
        mu, sd = Xtr.mean(), Xtr.std().replace(0, 1)
        Z = (Xtr - mu) / sd
        if model == "ridge":
            m = Ridge(alpha=alpha).fit(Z, ytr)
        elif model == "lasso":
            m = Lasso(alpha=alpha, max_iter=20000).fit(Z, ytr)
        elif model == "logit":
            m = LogisticRegression(C=alpha, max_iter=2000).fit(Z, (ytr > 0).astype(int))
        else:
            raise ValueError(model)
        in_sample = m.predict(Z) if model != "logit" else m.predict_proba(Z)[:, 1] * 2 - 1
        pred_sd = np.std(in_sample) if np.std(in_sample) > 0 else 1.0
        coefs[t] = dict(zip(cols, m.coef_.ravel()))
        z = (X.loc[[t]] - mu) / sd
        p = m.predict(z)[0] if model != "logit" else m.predict_proba(z)[0, 1] * 2 - 1
        preds[t] = p / pred_sd
    pos = np.sign(preds) if sizing == "sign" else preds.clip(-2, 2)
    return pos, preds, pd.DataFrame(coefs).T


def subperiod_table(curves, keys):
    """Sharpe of selected variants by sub-period, plus the 2002-07 quasi-in-sample window."""
    rows = []
    for k in keys:
        pnl = curves[k]
        always_on = pnl.abs() * 0 + 1
        for name, (s, e) in SUBPERIODS.items():
            mm = metrics(pnl, always_on, start=s, end=e)
            rows.append(dict(variant=k, period=name, sharpe=mm["sharpe"], ann_ret_bp=mm["ann_ret_bp"]))
        mm = metrics(pnl, always_on, start="2002-06-30", end="2007-12-31")
        rows.append(dict(variant=k, period="2002-07 (pre-OOS)", sharpe=mm["sharpe"], ann_ret_bp=mm["ann_ret_bp"]))
    table = pd.DataFrame(rows).pivot(index="variant", columns="period", values="sharpe")
    return table.loc[keys, ["2002-07 (pre-OOS)"] + list(SUBPERIODS)]


def run_variants(F, y, y0, cont):
    """Run every variant. Returns the results table, sub-period table, ridge coefficients, group scores, curves and positions."""
    core = core_feature_columns(F)
    extended = core + [c for c in F.columns if c.startswith("u_") or c.startswith("d_tic")]
    user_set = [c for c in core if c[0] in "rmds"]
    print("core features:", len(core), "| first month with all core features:", F[core].dropna().index.min().date())
    results, curves, positions = {}, {}, {}

    def add(name, pos_m, rank=1, note="", cost=TICK_COST):
        pnl, pos_d = daily_pnl(pos_m, cont, rank=rank, cost=cost)
        results[name] = dict(metrics(pnl, pos_d), note=note)
        curves[name] = pnl
        positions[name] = pos_m

    # Benchmarks
    ecb, ecb_dfr = follow_the_ecb(F), follow_the_ecb_dfr(F)
    add(LONG_ONLY, pd.Series(1.0, index=F.index), note="benchmark")
    add(TREND_3M, np.sign(F["r_fut_mom3"]), note="benchmark")
    add(TREND_12M, np.sign(F["r_fut_mom12"]), note="benchmark")
    add(ECB_RULE, ecb, note="benchmark")
    add(ECB_RULE_DFR, ecb_dfr, note="v1 anchor")

    # Prior-sign composite (no fitting)
    comp, groups = prior_composite(F, core)
    add(COMPOSITE, np.sign(comp), note="no fitting")
    add(COMPOSITE_SCALED, comp.clip(-2, 2), note="no fitting")
    comp_user, _ = prior_composite(F, core, groups=("R", "M", "S"))
    add("Prior composite, user factors only (R+M+S)", np.sign(comp_user), note="no fitting; no inflation")
    for g in groups.columns:
        add(f"Prior group {g} only", np.sign(groups[g]), note="no fitting")
    for g in groups.columns:
        without, _ = prior_composite(F, core, groups=tuple(x for x in "RMIS" if x != g))
        add(f"Prior composite drop {g}", np.sign(without), note="ablation")
    rolling, _ = prior_composite(F, core, window=60)
    add("Prior composite, rolling 60M z-scores", np.sign(rolling), note="z-score window")
    add("Prior composite, FRONT contract", np.sign(comp), rank=0, note="contract choice")
    add("Prior composite, 3RD contract", np.sign(comp), rank=2, note="contract choice")
    add("Prior composite, 3M smoothed signal", np.sign(comp).rolling(3).mean(), note="holding period")
    add("Prior composite, cost 1bp/side", np.sign(comp), cost=0.01, note="cost sensitivity")
    add("Prior composite, cost 2bp/side", np.sign(comp), cost=0.02, note="cost sensitivity")

    # The anchored specifications: v1 as reported in September, the anchor fix alone, and the frozen v2
    score1, score5 = risk_score(groups), factor_score(F)
    add(SCORE5, np.sign(score5), note="no fitting")
    add(SPEC_V1, frozen_spec(ecb_dfr, score1), note="v1 spec")
    add(SPEC_V1_BOTH, frozen_spec(ecb, score1), note="anchor fix only")
    add(SPEC, frozen_spec(ecb, score5), note="frozen spec")

    # Fitted models, walk-forward
    ridge_pos, ridge_pred, ridge_coef = walk_forward(F, y, core, "ridge", alpha=10)
    add(RIDGE_10, ridge_pos, note="walk-forward, monthly refit")
    ridge_coef.to_csv(RESULTS / "ridge_coefs.csv")
    ridge_pred.to_csv(RESULTS / "ridge_pred.csv")
    add("Ridge all factors (a=10), scaled", walk_forward(F, y, core, "ridge", alpha=10, sizing="scaled")[0])
    for a in (1, 100, 1000):
        add(f"Ridge all factors (a={a}), sign", walk_forward(F, y, core, "ridge", alpha=a)[0], note="alpha sensitivity")
    add("Lasso all factors (a=0.01), sign", walk_forward(F, y, core, "lasso", alpha=0.01)[0])
    add(LOGIT, walk_forward(F, y, core, "logit", alpha=0.1)[0])
    add("Ridge user factors only (R+M+D+S)", walk_forward(F, y, user_set, "ridge", alpha=10)[0], note="no inflation")
    for g in "RMDIS":
        only = [c for c in core if c[0].upper() == g]
        add(f"Ridge group {g} only", walk_forward(F, y, only, "ridge", alpha=10)[0], note="single group")
        rest = [c for c in core if c[0].upper() != g]
        add(f"Ridge drop group {g}", walk_forward(F, y, rest, "ridge", alpha=10)[0], note="ablation")
    add("Ridge all + US rates + TIC holdings", walk_forward(F, y, extended, "ridge", alpha=10)[0], note="extension (starts 2009)")
    add("Ridge all, min_train 120 (OOS from 2012)",
        walk_forward(F, y, core, "ridge", alpha=10, min_train=120, oos_start="2012-01-31")[0], note="later OOS start")
    add(PLACEBO, walk_forward(F, y, core, "ridge", alpha=10, shuffle_seed=0)[0], note="should be ~0")
    add("Combo: prior sign + ridge sign (avg)", (np.sign(comp) + ridge_pos) / 2)
    add("Combo: prior sign + follow-the-ECB (avg)", (np.sign(comp) + ecb) / 2)
    add("Ridge all, FRONT contract", walk_forward(F, y0, core, "ridge", alpha=10)[0], rank=0, note="contract choice")

    table = pd.DataFrame(results).T
    keys = [LONG_ONLY, TREND_12M, ECB_RULE_DFR, ECB_RULE, SPEC_V1, SPEC, COMPOSITE, COMPOSITE_SCALED, "Prior composite, user factors only (R+M+S)",
            RIDGE_10, RIDGE_100, LOGIT, "Combo: prior sign + follow-the-ECB (avg)"]
    subperiods = subperiod_table(curves, keys)
    return table, subperiods, ridge_coef, groups, curves, positions


def main():
    F, y, y0 = load_features()
    cont = load_continuous()
    table, subperiods, coef, groups, curves, positions = run_variants(F, y, y0, cont)
    table.to_csv(RESULTS / "results_main.csv")
    pd.DataFrame(curves).to_csv(RESULTS / "daily_pnl_curves.csv")
    pd.DataFrame(positions).to_csv(RESULTS / "monthly_positions.csv")
    groups.to_csv(RESULTS / "prior_group_scores.csv")
    subperiods.to_csv(RESULTS / "subperiod_sharpe.csv")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 20)
    cols = ["sharpe", "ann_ret_bp", "ann_vol_bp", "maxdd_bp", "cagr_vt", "maxdd_vt", "hit", "months", "t_stat", "exposure", "note"]
    print(table[cols].round(2).to_string())
    print("\nSub-period Sharpe:\n", subperiods.round(2).to_string())
    print("\nMean ridge coefficient:\n", coef.mean().sort_values().round(4).to_string())


if __name__ == "__main__":
    main()
