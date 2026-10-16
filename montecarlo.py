"""Monte Carlo and cross-validation checks on the Euribor macro strategy.
1. Block bootstrap of monthly P&L -> distribution of realised Sharpe (sampling uncertainty).
2. Circular-shift and block-permutation nulls -> p-value of the observed Sharpe under 'no timing skill'.
3. Deflated Sharpe ratio (Bailey & Lopez de Prado) for the number of variants tried.
4. Combinatorial purged cross-validation (CPCV) of the fitted models -> Sharpe across backtest paths.
5. Nested walk-forward: ridge alpha chosen each month on an inner validation window only.
"""
import numpy as np, pandas as pd, os, sys, itertools, json, warnings
from scipy.stats import norm, skew, kurtosis
from sklearn.linear_model import Ridge, LogisticRegression
warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT); D = f"{ROOT}/data"; R = f"{ROOT}/results"
from backtest import daily_pnl, metrics, OOS_START, OOS_END, COST
rng = np.random.default_rng(42)
W = slice(OOS_START, OOS_END)

def sharpe_m(x): return np.nan if x.std() == 0 else x.mean() / x.std() * np.sqrt(12)

# ---------- inputs ----------
C = pd.read_csv(f"{R}/daily_pnl_curves.csv", index_col=0, parse_dates=True)
P = pd.read_csv(f"{R}/monthly_positions.csv", index_col=0, parse_dates=True)
F = pd.read_csv(f"{D}/features_monthly.csv", index_col=0, parse_dates=True); y = F.pop("y_next"); F.pop("y0_next")
core = [c for c in F.columns if c[0] in "rmdis" and c != "m_loans_yoy" and not c.startswith("d_tic")]
keys = {"Long-only": "BM long-only 2nd contract", "Follow-the-ECB": "BM follow-the-ECB (-sign of DFR 3M change)", "Composite ±1": "Prior composite, sign (R+M+I+S)",
        "Composite scaled": "Prior composite, scaled (clip +/-2)", "Ridge a=10": "Ridge all factors (a=10), sign", "Ridge a=100": "Ridge all factors (a=100), sign", "Logit": "Logit direction (C=0.1), sign"}
M = C[list(keys.values())].loc[W].resample("ME").sum() * 100; M.columns = list(keys)          # monthly P&L in bp
T = len(M); print(f"monthly P&L matrix: {T} months, observed monthly-based Sharpe:", M.apply(sharpe_m).round(2).to_dict())

# ---------- 1. block bootstrap ----------
def block_boot(x, n=10000, L=12):
    x = x.values; T = len(x); nb = int(np.ceil(T / L)); out = np.empty(n)
    for i in range(n):
        starts = rng.integers(0, T, nb); idx = (starts[:, None] + np.arange(L)[None, :]).ravel() % T
        s = x[idx[:T]]; out[i] = s.mean() / s.std() * np.sqrt(12)
    return out
boot = {k: block_boot(M[k]) for k in M.columns}
B = pd.DataFrame({k: dict(mean=v.mean(), p05=np.percentile(v, 5), p50=np.percentile(v, 50), p95=np.percentile(v, 95), prob_gt0=(v > 0).mean()) for k, v in boot.items()}).T
diff = boot["Composite ±1"] - boot["Long-only"]; B.loc["Composite ±1", "prob_beats_longonly"] = (diff > 0).mean()
diff2 = boot["Composite ±1"] - boot["Follow-the-ECB"]; B.loc["Composite ±1", "prob_beats_ecb"] = (diff2 > 0).mean()
print("\n[1] Block bootstrap (12-month blocks, 10,000 draws) of realised Sharpe:"); print(B.round(2).to_string())

# ---------- 2. nulls: circular shift of positions, block permutation of positions ----------
yy = (y.loc[W] * 100)                     # next-month change of the 2nd contract, bp
def pnl_from_pos(pos, yv):
    pos = pos.reindex(yv.index).fillna(0); cost = pos.diff().abs().fillna(pos.abs()) * COST * 100 + pos.abs() * 2 * COST * 100 / 3
    return pos * yv - cost
nulls = {}
for k in ["Composite ±1", "Follow-the-ECB", "Ridge a=10", "Logit"]:
    pos = P[keys[k]].loc[W].reindex(yy.index).fillna(0).values; T = len(pos)
    obs = sharpe_m(pnl_from_pos(pd.Series(pos, index=yy.index), yy))
    shifts = np.array([sharpe_m(pnl_from_pos(pd.Series(np.roll(pos, s), index=yy.index), yy)) for s in range(6, T - 6)])
    perm = []
    nb = int(np.ceil(T / 12))
    for i in range(3000):
        order = rng.permutation(nb); idx = np.concatenate([np.arange(b * 12, min((b + 1) * 12, T)) for b in order])
        perm.append(sharpe_m(pnl_from_pos(pd.Series(pos[idx], index=yy.index), yy)))
    perm = np.array(perm)
    nulls[k] = dict(observed=obs, shift_mean=shifts.mean(), shift_sd=shifts.std(), p_shift=(shifts >= obs).mean(), perm_mean=perm.mean(), perm_sd=perm.std(), p_perm=(perm >= obs).mean(), n_shift=len(shifts))
N = pd.DataFrame(nulls).T; print("\n[2] No-skill nulls (positions shifted / block-permuted against the same returns), p = share of null Sharpes >= observed:"); print(N.round(3).to_string())
json.dump({k: {kk: float(vv) for kk, vv in v.items()} for k, v in nulls.items()}, open(f"{R}/mc_nulls.json", "w"), indent=1)

# ---------- 3. deflated Sharpe ratio ----------
Res = pd.read_csv(f"{R}/results_main.csv", index_col=0)
Mall = C.loc[W].resample("ME").sum() * 100
trial_sr = Mall.apply(lambda s: s.mean() / s.std()).dropna()          # monthly (non-annualised) Sharpe of every variant tried
Nt = len(trial_sr); V = trial_sr.var(); g = 0.5772156649
sr0 = np.sqrt(V) * ((1 - g) * norm.ppf(1 - 1 / Nt) + g * norm.ppf(1 - 1 / (Nt * np.e)))
def dsr(x):
    sr = x.mean() / x.std(); T = len(x); g3 = skew(x); g4 = kurtosis(x, fisher=False)
    return norm.cdf((sr - sr0) * np.sqrt(T - 1) / np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2)), sr * np.sqrt(12), sr0 * np.sqrt(12)
DS = {k: dsr(M[k]) for k in ["Composite ±1", "Composite scaled", "Follow-the-ECB", "Ridge a=10", "Ridge a=100", "Logit"]}
best = Mall.apply(sharpe_m).idxmax(); DS[f"best of all ({best})"] = dsr(Mall[best])
print(f"\n[3] Deflated Sharpe: {Nt} trials, expected max Sharpe under the null = {sr0*np.sqrt(12):.2f} (annualised)")
for k, (p, sr, s0) in DS.items(): print(f"   {k:32s} Sharpe {sr:+.2f}  P(true Sharpe > 0 after deflation) = {p:.2f}")

# ---------- 4. CPCV for fitted models ----------
X = F[core]; ok = X.notna().all(axis=1) & y.notna(); X = X[ok]; yv = y[ok]; idx = X.index; n = len(idx)
groups = np.array_split(np.arange(n), 10); NG = 10; k_test = 2
combos = list(itertools.combinations(range(NG), k_test))
def fit_predict(model, alpha, tr, te):
    mu = X.iloc[tr].mean(); sd = X.iloc[tr].std().replace(0, 1); Z = (X.iloc[tr] - mu) / sd; Zt = (X.iloc[te] - mu) / sd
    if model == "ridge": m = Ridge(alpha=alpha).fit(Z, yv.iloc[tr]); return m.predict(Zt)
    m = LogisticRegression(C=alpha, max_iter=2000).fit(Z, (yv.iloc[tr] > 0).astype(int)); return m.predict_proba(Zt)[:, 1] * 2 - 1
cp_rows = []; path_tables = {}
for model, alpha, lab in [("ridge", 10, "Ridge a=10"), ("ridge", 100, "Ridge a=100"), ("logit", 0.1, "Logit")]:
    preds = {}                                          # (combo_id, group) -> Series of preds
    for ci, combo in enumerate(combos):
        te = np.concatenate([groups[g] for g in combo]); te_set = set(te)
        purge = set(); 
        for g in combo:
            lo, hi = groups[g][0], groups[g][-1]; purge |= set(range(max(0, lo - 1), lo)) | set(range(hi + 1, min(n, hi + 3)))   # purge 1 before (overlapping target), embargo 2 after
        tr = np.array([i for i in range(n) if i not in te_set and i not in purge])
        p = fit_predict(model, alpha, tr, te); ps = pd.Series(p, index=idx[te])
        for g in combo: preds[(ci, g)] = ps.loc[idx[groups[g]]]
        pos = np.sign(ps); pnl = pnl_from_pos(pos, yv.loc[ps.index] * 100); cp_rows.append(dict(model=lab, combo=ci, test_groups=str(combo), sharpe=sharpe_m(pnl), months=len(pnl)))
    # assemble paths: for each group, the j-th combo containing it feeds path j
    paths = {}
    for g in range(NG):
        cids = [ci for ci, combo in enumerate(combos) if g in combo]
        for j, ci in enumerate(cids): paths.setdefault(j, []).append(preds[(ci, g)])
    ps_rows = []
    for j, parts in paths.items():
        ps = pd.concat(parts).sort_index(); pos = np.sign(ps); pnl = pnl_from_pos(pos, yv.loc[ps.index] * 100)
        ps_rows.append(dict(model=lab, path=j, sharpe_full=sharpe_m(pnl), sharpe_2008on=sharpe_m(pnl.loc["2008-01-31":]), sharpe_pre2008=sharpe_m(pnl.loc[:"2007-12-31"])))
    path_tables[lab] = pd.DataFrame(ps_rows)
CP = pd.DataFrame(cp_rows); PT = pd.concat(path_tables.values())
print(f"\n[4] CPCV: {NG} groups of ~{n//NG} months over {idx[0].date()} to {idx[-1].date()}, {len(combos)} train/test combinations, {len(path_tables['Ridge a=10'])} full backtest paths, purge 1 month + embargo 2 months")
print("   per-combination test Sharpe (each ~2 groups):"); print(CP.groupby("model")["sharpe"].describe()[["mean", "std", "min", "25%", "50%", "75%", "max"]].round(2).to_string())
print("   per-path Sharpe (full path, and 2008+ part):"); print(PT.groupby("model")[["sharpe_full", "sharpe_2008on", "sharpe_pre2008"]].agg(["mean", "min", "max"]).round(2).to_string())
CP.to_csv(f"{R}/cpcv_combos.csv", index=False); PT.to_csv(f"{R}/cpcv_paths.csv", index=False)

# ---------- 5. nested walk-forward (alpha chosen on inner validation) ----------
alphas = [1, 10, 100, 1000]; preds = pd.Series(np.nan, index=F.index); chosen = {}
for t in F.index:
    if t < pd.Timestamp(OOS_START): continue
    tr_mask = (F.index <= t - pd.offsets.MonthEnd(1)); Xtr = F.loc[tr_mask, core]; ytr = y[tr_mask]; okk = Xtr.notna().all(axis=1) & ytr.notna(); Xtr = Xtr[okk]; ytr = ytr[okk]
    if len(Xtr) < 72 or F.loc[t, core].isna().any(): continue
    inner_tr = Xtr.index <= t - pd.offsets.MonthEnd(37); inner_va = ~inner_tr
    best_a, best_s = None, -np.inf
    for a in alphas:
        mu = Xtr[inner_tr].mean(); sd = Xtr[inner_tr].std().replace(0, 1)
        m = Ridge(alpha=a).fit((Xtr[inner_tr] - mu) / sd, ytr[inner_tr]); pv = m.predict((Xtr[inner_va] - mu) / sd)
        s = sharpe_m(pnl_from_pos(pd.Series(np.sign(pv), index=ytr[inner_va].index), ytr[inner_va] * 100))
        if s > best_s + 1e-9 or (abs(s - best_s) <= 1e-9 and best_a is not None and a > best_a): best_a, best_s = a, s
    mu = Xtr.mean(); sd = Xtr.std().replace(0, 1); m = Ridge(alpha=best_a).fit((Xtr - mu) / sd, ytr)
    preds[t] = m.predict(((F.loc[[t], core] - mu) / sd))[0]; chosen[t] = best_a
pos_nested = np.sign(preds)
cont = pd.read_csv(f"{D}/euribor_futures_continuous.csv", index_col=0, parse_dates=True)
pnl_d, pos_d = daily_pnl(pos_nested, cont); mm = metrics(pnl_d, pos_d)
print(f"\n[5] Nested walk-forward ridge (alpha chosen each month on the prior 36 months only): Sharpe {mm['sharpe']:+.2f}, ann P&L {mm['ann_ret_bp']:+.0f} bp, max DD {mm['maxdd_bp']:.0f} bp, months {mm['months']}")
print("   alpha chosen, share of months:", pd.Series(chosen).value_counts(normalize=True).round(2).to_dict())
pd.Series(chosen).to_csv(f"{R}/nested_alpha_choices.csv"); pd.DataFrame({"pos": pos_nested}).to_csv(f"{R}/nested_positions.csv")
pd.DataFrame({k: v for k, v in boot.items()}).to_csv(f"{R}/mc_bootstrap_sharpe.csv", index=False)
