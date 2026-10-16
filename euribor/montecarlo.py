"""Monte Carlo and cross-validation checks on the one-contract backtests.

1. Block bootstrap of monthly P&L -> sampling distribution of the realised Sharpe.
2. Circular-shift and block-permutation nulls -> p-value of the observed Sharpe under "no timing skill".
3. Deflated Sharpe ratio (Bailey and Lopez de Prado) for the number of variants tried.
4. Combinatorial purged cross-validation (CPCV) of the fitted models -> Sharpe across backtest paths.
5. Nested walk-forward: ridge alpha chosen each month on an inner validation window only.
"""
import itertools
import json
import warnings

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew
from sklearn.linear_model import LogisticRegression, Ridge

from .backtest import daily_pnl, metrics
from .config import (COMPOSITE, COMPOSITE_SCALED, ECB_RULE, LOGIT, LONG_ONLY, OOS_END, OOS_START, RESULTS, RIDGE_10,
                     RIDGE_100, TICK_COST)
from .data import core_feature_columns, load_continuous, load_features, load_pnl_curves, load_positions, sharpe_monthly

warnings.filterwarnings("ignore")
EULER_GAMMA = 0.5772156649


def block_bootstrap_sharpe(x, rng, n=10000, block=12):
    """Annualised Sharpe of ``n`` circular block-bootstrap resamples of a monthly series."""
    values = x.values
    T = len(values)
    n_blocks = int(np.ceil(T / block))
    out = np.empty(n)
    for i in range(n):
        starts = rng.integers(0, T, n_blocks)
        idx = (starts[:, None] + np.arange(block)[None, :]).ravel() % T
        sample = values[idx[:T]]
        out[i] = sample.mean() / sample.std() * np.sqrt(12)
    return out


def monthly_pnl(pos, y_bp, cost=TICK_COST):
    """Monthly P&L in bp from month-end positions and next-month price changes, with trading and roll costs."""
    pos = pos.reindex(y_bp.index).fillna(0)
    costs = pos.diff().abs().fillna(pos.abs()) * cost * 100 + pos.abs() * 2 * cost * 100 / 3
    return pos * y_bp - costs


def no_skill_nulls(pos, y_bp, rng, n_perm=3000, block=12):
    """Sharpe of the position path shifted in time (every shift of 6..T-6) and block-permuted, against the same returns."""
    values = pos.reindex(y_bp.index).fillna(0).values
    T = len(values)
    observed = sharpe_monthly(monthly_pnl(pd.Series(values, index=y_bp.index), y_bp))
    shifts = np.array([sharpe_monthly(monthly_pnl(pd.Series(np.roll(values, s), index=y_bp.index), y_bp)) for s in range(6, T - 6)])
    n_blocks = int(np.ceil(T / block))
    perm = np.empty(n_perm)
    for i in range(n_perm):
        order = rng.permutation(n_blocks)
        idx = np.concatenate([np.arange(b * block, min((b + 1) * block, T)) for b in order])
        perm[i] = sharpe_monthly(monthly_pnl(pd.Series(values[idx], index=y_bp.index), y_bp))
    return dict(observed=observed, shift_mean=shifts.mean(), shift_sd=shifts.std(), p_shift=(shifts >= observed).mean(),
                perm_mean=perm.mean(), perm_sd=perm.std(), p_perm=(perm >= observed).mean(), n_shift=len(shifts)), perm


def expected_max_sharpe(trial_sharpes, n_trials=None):
    """Expected maximum (monthly, non-annualised) Sharpe of ``n_trials`` zero-skill trials with the observed dispersion.

    ``trial_sharpes`` are the monthly Sharpe ratios of the variants on file; ``n_trials`` defaults to their count.
    """
    n = len(trial_sharpes) if n_trials is None else n_trials
    v = trial_sharpes.var()
    return np.sqrt(v) * ((1 - EULER_GAMMA) * norm.ppf(1 - 1 / n) + EULER_GAMMA * norm.ppf(1 - 1 / (n * np.e)))


def deflated_sharpe(x, sr0):
    """Probability that the true Sharpe exceeds zero after deflating by the expected best-of-N Sharpe ``sr0``."""
    sr = x.mean() / x.std()
    T = len(x)
    g3, g4 = skew(x), kurtosis(x, fisher=False)
    return norm.cdf((sr - sr0) * np.sqrt(T - 1) / np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2))


def fit_predict(X, yv, model, alpha, train, test):
    """Standardise on the training rows, fit, predict the test rows. Logit predictions are mapped to [-1, 1]."""
    mu, sd = X.iloc[train].mean(), X.iloc[train].std().replace(0, 1)
    Z, Zt = (X.iloc[train] - mu) / sd, (X.iloc[test] - mu) / sd
    if model == "ridge":
        return Ridge(alpha=alpha).fit(Z, yv.iloc[train]).predict(Zt)
    return LogisticRegression(C=alpha, max_iter=2000).fit(Z, (yv.iloc[train] > 0).astype(int)).predict_proba(Zt)[:, 1] * 2 - 1


def cpcv_predictions(X, yv, model, alpha, n_groups=10, k_test=2, purge=1, embargo=2):
    """Combinatorial purged cross-validation predictions.

    The sample is cut into ``n_groups`` contiguous blocks; every combination of ``k_test`` blocks is a test set,
    with ``purge`` months removed before each test block (overlapping target) and ``embargo`` after. Returns the
    list of (combination, prediction Series) and the list of full-sample prediction paths assembled from them.
    """
    idx = X.index
    n = len(idx)
    groups = np.array_split(np.arange(n), n_groups)
    combos = list(itertools.combinations(range(n_groups), k_test))
    by_combo, by_group = [], {}
    for ci, combo in enumerate(combos):
        test = np.concatenate([groups[g] for g in combo])
        excluded = set(test)
        for g in combo:
            lo, hi = groups[g][0], groups[g][-1]
            excluded |= set(range(max(0, lo - purge), lo)) | set(range(hi + 1, min(n, hi + 1 + embargo)))
        train = np.array([i for i in range(n) if i not in excluded])
        preds = pd.Series(fit_predict(X, yv, model, alpha, train, test), index=idx[test])
        by_combo.append((combo, preds))
        for g in combo:
            by_group[(ci, g)] = preds.loc[idx[groups[g]]]
    paths = {}
    for g in range(n_groups):
        for j, ci in enumerate(ci for ci, combo in enumerate(combos) if g in combo):
            paths.setdefault(j, []).append(by_group[(ci, g)])
    paths = [pd.concat(parts).sort_index() for _, parts in sorted(paths.items())]
    return by_combo, paths


def nested_walk_forward(F, y, cols, alphas=(1, 10, 100, 1000), min_train=72, inner_validation=36):
    """Ridge with alpha chosen each month on the last ``inner_validation`` months of the training window only."""
    preds = pd.Series(np.nan, index=F.index)
    chosen = {}
    for t in F.index:
        if t < pd.Timestamp(OOS_START):
            continue
        train = F.index <= t - pd.offsets.MonthEnd(1)
        Xtr, ytr = F.loc[train, cols], y[train]
        ok = Xtr.notna().all(axis=1) & ytr.notna()
        Xtr, ytr = Xtr[ok], ytr[ok]
        if len(Xtr) < min_train or F.loc[t, cols].isna().any():
            continue
        inner_train = Xtr.index <= t - pd.offsets.MonthEnd(inner_validation + 1)
        inner_valid = ~inner_train
        best_alpha, best_sharpe = None, -np.inf
        for a in alphas:
            mu, sd = Xtr[inner_train].mean(), Xtr[inner_train].std().replace(0, 1)
            m = Ridge(alpha=a).fit((Xtr[inner_train] - mu) / sd, ytr[inner_train])
            pv = m.predict((Xtr[inner_valid] - mu) / sd)
            s = sharpe_monthly(monthly_pnl(pd.Series(np.sign(pv), index=ytr[inner_valid].index), ytr[inner_valid] * 100))
            if s > best_sharpe + 1e-9 or (abs(s - best_sharpe) <= 1e-9 and best_alpha is not None and a > best_alpha):
                best_alpha, best_sharpe = a, s
        mu, sd = Xtr.mean(), Xtr.std().replace(0, 1)
        m = Ridge(alpha=best_alpha).fit((Xtr - mu) / sd, ytr)
        preds[t] = m.predict((F.loc[[t], cols] - mu) / sd)[0]
        chosen[t] = best_alpha
    return np.sign(preds), pd.Series(chosen)


KEYS = {"Long-only": LONG_ONLY, "Follow-the-ECB": ECB_RULE, "Composite ±1": COMPOSITE, "Composite scaled": COMPOSITE_SCALED,
        "Ridge a=10": RIDGE_10, "Ridge a=100": RIDGE_100, "Logit": LOGIT}
CPCV_MODELS = [("ridge", 10, "Ridge a=10"), ("ridge", 100, "Ridge a=100"), ("logit", 0.1, "Logit")]


def main():
    rng = np.random.default_rng(42)
    window = slice(OOS_START, OOS_END)
    curves = load_pnl_curves()
    positions = load_positions()
    F, y, _ = load_features()
    core = core_feature_columns(F)
    M = curves[list(KEYS.values())].loc[window].resample("ME").sum() * 100      # monthly P&L in bp
    M.columns = list(KEYS)
    print(f"monthly P&L matrix: {len(M)} months, observed monthly-based Sharpe:", M.apply(sharpe_monthly).round(2).to_dict())

    # 1. block bootstrap
    boot = {k: block_bootstrap_sharpe(M[k], rng) for k in M.columns}
    B = pd.DataFrame({k: dict(mean=v.mean(), p05=np.percentile(v, 5), p50=np.percentile(v, 50), p95=np.percentile(v, 95),
                              prob_gt0=(v > 0).mean()) for k, v in boot.items()}).T
    B.loc["Composite ±1", "prob_beats_longonly"] = (boot["Composite ±1"] - boot["Long-only"] > 0).mean()
    B.loc["Composite ±1", "prob_beats_ecb"] = (boot["Composite ±1"] - boot["Follow-the-ECB"] > 0).mean()
    print("\n[1] Block bootstrap (12-month blocks, 10,000 draws) of realised Sharpe:")
    print(B.round(2).to_string())
    pd.DataFrame(boot).to_csv(RESULTS / "mc_bootstrap_sharpe.csv", index=False)

    # 2. no-skill nulls
    y_bp = y.loc[window] * 100
    nulls = {}
    for k in ["Composite ±1", "Follow-the-ECB", "Ridge a=10", "Logit"]:
        nulls[k], _ = no_skill_nulls(positions[KEYS[k]].loc[window], y_bp, rng)
    N = pd.DataFrame(nulls).T
    print("\n[2] No-skill nulls (positions shifted / block-permuted against the same returns), p = share of null Sharpes >= observed:")
    print(N.round(3).to_string())
    json.dump({k: {kk: float(vv) for kk, vv in v.items()} for k, v in nulls.items()}, open(RESULTS / "mc_nulls.json", "w"), indent=1)

    # 3. deflated Sharpe over every variant tried
    M_all = curves.loc[window].resample("ME").sum() * 100
    trial_sr = M_all.apply(lambda s: s.mean() / s.std()).dropna()
    sr0 = expected_max_sharpe(trial_sr)
    print(f"\n[3] Deflated Sharpe: {len(trial_sr)} trials, expected max Sharpe under the null = {sr0 * np.sqrt(12):.2f} (annualised)")
    for k in ["Composite ±1", "Composite scaled", "Follow-the-ECB", "Ridge a=10", "Ridge a=100", "Logit"]:
        print(f"   {k:32s} Sharpe {sharpe_monthly(M[k]):+.2f}  P(true Sharpe > 0 after deflation) = {deflated_sharpe(M[k], sr0):.2f}")
    best = M_all.apply(sharpe_monthly).idxmax()
    print(f"   {'best of all (' + best + ')':32s} Sharpe {sharpe_monthly(M_all[best]):+.2f}  "
          f"P(true Sharpe > 0 after deflation) = {deflated_sharpe(M_all[best], sr0):.2f}")

    # 4. CPCV for the fitted models
    X = F[core]
    ok = X.notna().all(axis=1) & y.notna()
    X, yv = X[ok], y[ok]
    combo_rows, path_rows = [], []
    for model, alpha, label in CPCV_MODELS:
        by_combo, paths = cpcv_predictions(X, yv, model, alpha)
        for ci, (combo, preds) in enumerate(by_combo):
            pnl = monthly_pnl(np.sign(preds), yv.loc[preds.index] * 100)
            combo_rows.append(dict(model=label, combo=ci, test_groups=str(combo), sharpe=sharpe_monthly(pnl), months=len(pnl)))
        for j, preds in enumerate(paths):
            pnl = monthly_pnl(np.sign(preds), yv.loc[preds.index] * 100)
            path_rows.append(dict(model=label, path=j, sharpe_full=sharpe_monthly(pnl), sharpe_2008on=sharpe_monthly(pnl.loc["2008-01-31":]),
                                  sharpe_pre2008=sharpe_monthly(pnl.loc[:"2007-12-31"])))
    CP, PT = pd.DataFrame(combo_rows), pd.DataFrame(path_rows)
    n_paths = len(PT[PT["model"] == "Ridge a=10"])
    print(f"\n[4] CPCV: 10 groups of ~{len(X) // 10} months over {X.index[0].date()} to {X.index[-1].date()}, "
          f"{len(by_combo)} train/test combinations, {n_paths} full backtest paths, purge 1 month + embargo 2 months")
    print("   per-combination test Sharpe (each ~2 groups):")
    print(CP.groupby("model")["sharpe"].describe()[["mean", "std", "min", "25%", "50%", "75%", "max"]].round(2).to_string())
    print("   per-path Sharpe (full path, and 2008+ part):")
    print(PT.groupby("model")[["sharpe_full", "sharpe_2008on", "sharpe_pre2008"]].agg(["mean", "min", "max"]).round(2).to_string())
    CP.to_csv(RESULTS / "cpcv_combos.csv", index=False)
    PT.to_csv(RESULTS / "cpcv_paths.csv", index=False)

    # 5. nested walk-forward
    pos_nested, chosen = nested_walk_forward(F, y, core)
    pnl_d, pos_d = daily_pnl(pos_nested, load_continuous())
    mm = metrics(pnl_d, pos_d)
    print(f"\n[5] Nested walk-forward ridge (alpha chosen each month on the prior 36 months only): Sharpe {mm['sharpe']:+.2f}, "
          f"ann P&L {mm['ann_ret_bp']:+.0f} bp, max DD {mm['maxdd_bp']:.0f} bp, months {mm['months']}")
    print("   alpha chosen, share of months:", chosen.value_counts(normalize=True).round(2).to_dict())
    chosen.to_csv(RESULTS / "nested_alpha_choices.csv")
    pd.DataFrame({"pos": pos_nested}).to_csv(RESULTS / "nested_positions.csv")


if __name__ == "__main__":
    main()
