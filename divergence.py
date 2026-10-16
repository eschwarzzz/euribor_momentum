"""Where do the strategy paths diverge from the follow-the-ECB rule, and did it pay?"""
import numpy as np, pandas as pd, os, sys, itertools, warnings
from sklearn.linear_model import Ridge, LogisticRegression
warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT); D = f"{ROOT}/data"; R = f"{ROOT}/results"
from backtest import OOS_START, OOS_END
W = slice(OOS_START, OOS_END)
P = pd.read_csv(f"{R}/monthly_positions.csv", index_col=0, parse_dates=True)
F = pd.read_csv(f"{D}/features_monthly.csv", index_col=0, parse_dates=True); y = F.pop("y_next"); F.pop("y0_next")
G = pd.read_csv(f"{R}/prior_group_scores.csv", index_col=0, parse_dates=True)
core = [c for c in F.columns if c[0] in "rmdis" and c != "m_loans_yoy" and not c.startswith("d_tic")]
ecb = P["BM follow-the-ECB (-sign of DFR 3M change)"]
paths = {}
for k in ["Prior composite, sign (R+M+I+S)", "Prior composite, scaled (clip +/-2)", "Prior composite, user factors only (R+M+S)", "Prior composite drop R", "Prior composite drop M", "Prior composite drop I", "Prior composite drop S",
          "Prior composite, rolling 60M z-scores", "Prior composite, 3M smoothed signal", "Ridge all factors (a=1), sign", "Ridge all factors (a=10), sign", "Ridge all factors (a=100), sign", "Ridge all factors (a=1000), sign",
          "Lasso all factors (a=0.01), sign", "Logit direction (C=0.1), sign", "Ridge user factors only (R+M+D+S)"]:
    paths[k] = np.sign(P[k])
paths["Nested ridge"] = np.sign(pd.read_csv(f"{R}/nested_positions.csv", index_col=0, parse_dates=True)["pos"])
# CPCV paths (same construction as montecarlo.py)
X = F[core]; ok = X.notna().all(axis=1) & y.notna(); X = X[ok]; yv = y[ok]; idx = X.index; n = len(idx)
groups = np.array_split(np.arange(n), 10); combos = list(itertools.combinations(range(10), 2))
def fit_predict(model, alpha, tr, te):
    mu = X.iloc[tr].mean(); sd = X.iloc[tr].std().replace(0, 1); Z = (X.iloc[tr] - mu) / sd; Zt = (X.iloc[te] - mu) / sd
    if model == "ridge": return Ridge(alpha=alpha).fit(Z, yv.iloc[tr]).predict(Zt)
    return LogisticRegression(C=alpha, max_iter=2000).fit(Z, (yv.iloc[tr] > 0).astype(int)).predict_proba(Zt)[:, 1] * 2 - 1
for model, alpha, lab in [("ridge", 10, "CPCV ridge10"), ("ridge", 100, "CPCV ridge100"), ("logit", 0.1, "CPCV logit")]:
    preds = {}
    for ci, combo in enumerate(combos):
        te = np.concatenate([groups[g] for g in combo]); te_set = set(te); purge = set()
        for g in combo: lo, hi = groups[g][0], groups[g][-1]; purge |= set(range(max(0, lo - 1), lo)) | set(range(hi + 1, min(n, hi + 3)))
        tr = np.array([i for i in range(n) if i not in te_set and i not in purge]); ps = pd.Series(fit_predict(model, alpha, tr, te), index=idx[te])
        for g in combo: preds[(ci, g)] = ps.loc[idx[groups[g]]]
    for g in range(10):
        cids = [ci for ci, combo in enumerate(combos) if g in combo]
        for j, ci in enumerate(cids): paths.setdefault(f"{lab} path{j}", []).append(preds[(ci, g)])
    for j in range(9): paths[f"{lab} path{j}"] = np.sign(pd.concat(paths[f"{lab} path{j}"]).sort_index())
PT = pd.DataFrame(paths).loc[W].reindex(ecb.loc[W].index); E = ecb.loc[W]; Y = (y.loc[W] * 100)
print(f"{PT.shape[1]} paths x {len(PT)} months")
dis = PT.apply(lambda s: (s != E) & s.notna() & (s != 0))                     # disagreement with the ECB rule
rel = PT.apply(lambda s: (s - E) * Y)                                           # relative P&L vs ECB rule, bp (no cost)
Dint = dis.mean(axis=1); RP = rel.mean(axis=1)
# ---- 1. divergence intensity by year and regime ----
yr = pd.DataFrame({"share_paths_disagreeing": Dint.groupby(Dint.index.year).mean(), "avg_rel_pnl_bp_per_month": RP.groupby(RP.index.year).mean(), "composite_rel_pnl_bp_year": rel["Prior composite, sign (R+M+I+S)"].groupby(rel.index.year).sum()})
print("\n[1] By year: share of paths disagreeing with follow-the-ECB, average relative P&L per month across paths, composite's relative P&L for the year:"); print(yr.round(2).to_string())
# ---- 2. top months by divergence intensity and by |relative P&L| ----
top = pd.DataFrame({"share_disagree": Dint, "avg_rel_pnl_bp": RP, "ecb_pos": E, "comp_pos": PT["Prior composite, sign (R+M+I+S)"], "next_month_chg_bp": Y}).join(G.round(2))
print("\n[2] Twelve months where most paths diverge from the ECB rule (positions decided at month-end, P&L is the following month):"); print(top.sort_values("share_disagree", ascending=False).head(12).round(2).to_string())
print("\n    Ten months where divergence cost the most / paid the most (average across paths):"); print(pd.concat([top.sort_values("avg_rel_pnl_bp").head(5), top.sort_values("avg_rel_pnl_bp", ascending=False).head(5)]).round(1).to_string())
# ---- 3. episodes: runs of >= 3 consecutive months with majority disagreement ----
runs = []; cur = []
for t, v in Dint.items():
    if v > 0.5: cur.append(t)
    else:
        if len(cur) >= 3: runs.append(cur)
        cur = []
if len(cur) >= 3: runs.append(cur)
print("\n[3] Divergence episodes (3+ consecutive months with a majority of paths against the ECB rule):")
for r in runs:
    seg = rel.loc[r]; print(f"   {r[0].strftime('%Y-%m')} to {r[-1].strftime('%Y-%m')} ({len(r)} mo): ECB pos {E.loc[r].mean():+.1f}, avg rel P&L across paths {seg.mean(axis=1).sum():+.0f} bp, composite rel P&L {seg['Prior composite, sign (R+M+I+S)'].sum():+.0f} bp, group scores R {G.loc[r,'R'].mean():+.2f} M {G.loc[r,'M'].mean():+.2f} I {G.loc[r,'I'].mean():+.2f} S {G.loc[r,'S'].mean():+.2f}")
# ---- 4. composite attribution: which group drove each disagreement, and did it pay ----
comp = PT["Prior composite, sign (R+M+I+S)"]; dm = (comp != E) & comp.notna()
Gw = G.loc[W].reindex(comp.index)
rows = []
for t in comp.index[dm]:
    sc = Gw.loc[t]; side = comp.loc[t]; drivers = sc[np.sign(sc) == side]
    driver = drivers.abs().idxmax() if len(drivers) else "none"
    rows.append(dict(date=t, driver=driver, driver_score=sc[driver] if driver != "none" else np.nan, n_groups_with_composite=int((np.sign(sc) == side).sum()), rel_pnl_bp=rel.loc[t, "Prior composite, sign (R+M+I+S)"], ecb_pos=E.loc[t]))
A = pd.DataFrame(rows).set_index("date")
print(f"\n[4] Composite disagrees with the ECB rule in {len(A)} of {dm.notna().sum()} months. Attribution to the group that pushed hardest against the ECB rule:")
print(A.groupby("driver").agg(months=("rel_pnl_bp", "size"), rel_pnl_sum_bp=("rel_pnl_bp", "sum"), rel_pnl_mean_bp=("rel_pnl_bp", "mean"), hit_rate=("rel_pnl_bp", lambda s: (s > 0).mean())).round(2).to_string())
print("\n    by how many groups sided with the composite against the ECB rule:"); print(A.groupby("n_groups_with_composite").agg(months=("rel_pnl_bp", "size"), rel_pnl_sum_bp=("rel_pnl_bp", "sum"), hit_rate=("rel_pnl_bp", lambda s: (s > 0).mean())).round(2).to_string())
print("\n    by ECB rule position at the time (i.e. was the composite fading a cutting cycle or a hiking cycle):"); print(A.groupby("ecb_pos").agg(months=("rel_pnl_bp", "size"), rel_pnl_sum_bp=("rel_pnl_bp", "sum"), hit_rate=("rel_pnl_bp", lambda s: (s > 0).mean())).round(2).to_string())
# ---- 5. each group's standalone agreement with the ECB rule and relative value ----
print("\n[5] Group-level: correlation of each group's score with the ECB rule position, and the group's relative P&L vs the rule when it disagrees:")
for g in "RMIS":
    s = np.sign(Gw[g]); d = (s != E) & (s != 0); r = ((s - E) * Y)[d]
    print(f"   {g}: corr with ECB position {np.corrcoef(Gw[g].fillna(0), E)[0,1]:+.2f} | disagrees {d.mean():.0%} of months | relative P&L when it disagrees {r.sum():+.0f} bp, hit {(r > 0).mean():.0%}")
A.to_csv(f"{R}/divergence_attribution.csv"); top.to_csv(f"{R}/divergence_monthly.csv"); yr.to_csv(f"{R}/divergence_by_year.csv")
