"""Walk-forward backtest of macro-factor models on synthetic 3M Euribor futures (2nd quarterly contract)."""
import numpy as np, pandas as pd, os, sys, warnings, json
from sklearn.linear_model import Ridge, LogisticRegression, Lasso
warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
D = os.path.join(ROOT, "data"); OUT = os.path.join(ROOT, "results"); os.makedirs(OUT, exist_ok=True)
from features import PRIOR

COST = 0.005          # price points per unit traded per side (half a basis point ~ one tick)
OOS_START = "2008-01-31"; OOS_END = "2026-08-31"
MIN_TRAIN = 72
SUBS = {"2008-12 crisis": ("2008-01-01", "2012-12-31"), "2013-19 ZLB/QE": ("2013-01-01", "2019-12-31"),
        "2020-21 COVID": ("2020-01-01", "2021-12-31"), "2022-26 hikes+cuts": ("2022-01-01", OOS_END)}

def load():
    F = pd.read_csv(f"{D}/features_monthly.csv", index_col=0, parse_dates=True)
    y = F.pop("y_next"); y0 = F.pop("y0_next")
    cont = pd.read_csv(f"{D}/euribor_futures_continuous.csv", index_col=0, parse_dates=True)
    return F, y, y0, cont

def daily_pnl(pos_m, cont, rank=1, cost=COST):
    """pos_m: positions decided at month-end t, applied from the next trading day. Returns daily P&L (points) and daily positions."""
    chg = cont[f"chg{rank}"].fillna(0.0); exp = cont[f"exp{rank}"]; idx = chg.index
    pm = pos_m.dropna()
    pos_d = pd.merge_asof(pd.DataFrame({"date": idx}), pm.rename("pos").rename_axis("date").reset_index(), on="date", allow_exact_matches=False).set_index("date")["pos"].fillna(0.0)
    trade = pos_d.diff().abs().fillna(pos_d.abs())
    roll = (exp != exp.shift(1)) & (np.arange(len(exp)) > 0)
    pnl = pos_d * chg - trade * cost - roll.astype(float) * pos_d.abs() * 2 * cost
    return pnl, pos_d

def metrics(pnl, pos_d, start=OOS_START, end=OOS_END):
    pnl = pnl.loc[start:end]; pos_d = pos_d.loc[start:end]
    n = len(pnl)
    if n < 60 or pnl.std() == 0: return dict(ann_ret_bp=np.nan, ann_vol_bp=np.nan, sharpe=np.nan, maxdd_bp=np.nan, cagr_vt=np.nan, maxdd_vt=np.nan, hit=np.nan, months=0, t_stat=np.nan, exposure=np.nan)
    ann_ret = pnl.mean() * 252; ann_vol = pnl.std() * np.sqrt(252); sr = ann_ret / ann_vol
    cum = pnl.cumsum(); mdd = (cum - cum.cummax()).min()
    lev = 0.10 / (ann_vol / 100); r = lev * pnl / 100; eq = (1 + r).cumprod()
    cagr = eq.iloc[-1] ** (252 / n) - 1; mdd_vt = (eq / eq.cummax() - 1).min()
    mo = pnl.resample("ME").sum(); pm = pos_d.resample("ME").last().reindex(mo.index); mo = mo[pm.abs() > 0]
    return dict(ann_ret_bp=ann_ret * 100, ann_vol_bp=ann_vol * 100, sharpe=sr, maxdd_bp=mdd * 100, cagr_vt=cagr * 100, maxdd_vt=mdd_vt * 100,
                hit=(mo > 0).mean() * 100, months=len(mo), t_stat=sr * np.sqrt(n / 252), exposure=pos_d.abs().mean())

# ---------------- models ----------------
def prior_composite(F, cols, groups=("R", "M", "I", "S"), window=None):
    z = pd.DataFrame(index=F.index)
    for c in cols:
        if PRIOR.get(c, 0) == 0 or c[0].upper() not in groups: continue
        s = F[c]
        if window: m = s.rolling(window, min_periods=36).mean(); sd = s.rolling(window, min_periods=36).std()
        else: m = s.expanding(36).mean(); sd = s.expanding(36).std()
        z[c] = ((s - m) / sd).clip(-3, 3) * PRIOR[c]
    g = pd.DataFrame({k: z[[c for c in z.columns if c[0].upper() == k]].mean(axis=1) for k in groups if any(c[0].upper() == k for c in z.columns)})
    return g.mean(axis=1), g

def walk_forward(F, y, cols, model="ridge", alpha=10.0, min_train=MIN_TRAIN, oos_start=OOS_START, shuffle_seed=None, sizing="sign"):
    X = F[cols].copy(); idx = X.index
    preds = pd.Series(np.nan, index=idx); coefs = {}
    rng = np.random.default_rng(shuffle_seed) if shuffle_seed is not None else None
    for i, t in enumerate(idx):
        if t < pd.Timestamp(oos_start): continue
        tr = (idx <= t - pd.offsets.MonthEnd(1))                  # y_s known by t
        Xtr = X[tr]; ytr = y[tr]; ok = Xtr.notna().all(axis=1) & ytr.notna(); Xtr = Xtr[ok]; ytr = ytr[ok]
        if len(Xtr) < min_train or X.loc[t].isna().any(): continue
        if rng is not None: ytr = pd.Series(rng.permutation(ytr.values), index=ytr.index)
        mu = Xtr.mean(); sd = Xtr.std().replace(0, 1); Z = (Xtr - mu) / sd
        if model == "ridge": m = Ridge(alpha=alpha).fit(Z, ytr)
        elif model == "lasso": m = Lasso(alpha=alpha, max_iter=20000).fit(Z, ytr)
        elif model == "logit": m = LogisticRegression(C=alpha, max_iter=2000).fit(Z, (ytr > 0).astype(int))
        ptr = m.predict(Z) if model != "logit" else m.predict_proba(Z)[:, 1] * 2 - 1
        psd = np.std(ptr) if np.std(ptr) > 0 else 1.0
        coefs[t] = dict(zip(cols, m.coef_.ravel()))
        z = (X.loc[[t]] - mu) / sd
        p = m.predict(z)[0] if model != "logit" else m.predict_proba(z)[0, 1] * 2 - 1
        preds[t] = p / psd
    pos = np.sign(preds) if sizing == "sign" else preds.clip(-2, 2)
    return pos, preds, pd.DataFrame(coefs).T

def run_all():
    F, y, y0, cont = load()
    core = [c for c in F.columns if c[0] in "rmdis" and c != "m_loans_yoy" and not c.startswith("d_tic")]
    ext = core + [c for c in F.columns if c.startswith("u_") or c.startswith("d_tic")]
    user_set = [c for c in core if c[0] in "rmds"]
    print("core features:", len(core), "| first month with all core features:", F[core].dropna().index.min().date())
    results = {}; curves = {}; positions = {}
    def add(name, pos_m, rank=1, note="", cost=COST):
        pnl, pos_d = daily_pnl(pos_m, cont, rank=rank, cost=cost)
        results[name] = dict(metrics(pnl, pos_d), note=note); curves[name] = pnl; positions[name] = pos_m
        return pnl
    ones = pd.Series(1.0, index=F.index)
    # ---- benchmarks ----
    add("BM long-only 2nd contract", ones, note="benchmark")
    add("BM trend 3M (sign of 3M price change)", np.sign(F["r_fut_mom3"]), note="benchmark")
    add("BM trend 12M", np.sign(F["r_fut_mom12"]), note="benchmark")
    add("BM follow-the-ECB (-sign of DFR 3M change)", (-np.sign(F["r_dfr_chg3"])).replace(0, np.nan).ffill(), note="benchmark")
    # ---- prior-sign composite (no fitting) ----
    comp, g = prior_composite(F, core)
    add("Prior composite, sign (R+M+I+S)", np.sign(comp), note="no fitting")
    add("Prior composite, scaled (clip +/-2)", comp.clip(-2, 2), note="no fitting")
    comp_u, _ = prior_composite(F, core, groups=("R", "M", "S")); add("Prior composite, user factors only (R+M+S)", np.sign(comp_u), note="no fitting; no inflation")
    for k in g.columns: add(f"Prior group {k} only", np.sign(g[k]), note="no fitting")
    for k in g.columns:
        c2, _ = prior_composite(F, core, groups=tuple(x for x in "RMIS" if x != k)); add(f"Prior composite drop {k}", np.sign(c2), note="ablation")
    c60, _ = prior_composite(F, core, window=60); add("Prior composite, rolling 60M z-scores", np.sign(c60), note="z-score window")
    add("Prior composite, FRONT contract", np.sign(comp), rank=0, note="contract choice")
    add("Prior composite, 3RD contract", np.sign(comp), rank=2, note="contract choice")
    add("Prior composite, 3M smoothed signal", np.sign(comp).rolling(3).mean(), note="holding period")
    add("Prior composite, cost 1bp/side", np.sign(comp), cost=0.01, note="cost sensitivity")
    add("Prior composite, cost 2bp/side", np.sign(comp), cost=0.02, note="cost sensitivity")
    # ---- fitted models ----
    pos, pred, coef = walk_forward(F, y, core, "ridge", alpha=10); add("Ridge all factors (a=10), sign", pos, note="walk-forward, monthly refit")
    coef.to_csv(f"{OUT}/ridge_coefs.csv"); pred.to_csv(f"{OUT}/ridge_pred.csv")
    p, _, _ = walk_forward(F, y, core, "ridge", alpha=10, sizing="scaled"); add("Ridge all factors (a=10), scaled", p)
    for a in (1, 100, 1000):
        p, _, _ = walk_forward(F, y, core, "ridge", alpha=a); add(f"Ridge all factors (a={a}), sign", p, note="alpha sensitivity")
    p, _, _ = walk_forward(F, y, core, "lasso", alpha=0.01); add("Lasso all factors (a=0.01), sign", p)
    p, _, _ = walk_forward(F, y, core, "logit", alpha=0.1); add("Logit direction (C=0.1), sign", p)
    p, _, _ = walk_forward(F, y, user_set, "ridge", alpha=10); add("Ridge user factors only (R+M+D+S)", p, note="no inflation")
    for k in "RMDIS":
        cols = [c for c in core if c[0].upper() == k]
        p, _, _ = walk_forward(F, y, cols, "ridge", alpha=10); add(f"Ridge group {k} only", p, note="single group")
        p, _, _ = walk_forward(F, y, [c for c in core if c[0].upper() != k], "ridge", alpha=10); add(f"Ridge drop group {k}", p, note="ablation")
    p, _, _ = walk_forward(F, y, ext, "ridge", alpha=10); add("Ridge all + US rates + TIC holdings", p, note="extension (starts 2009)")
    p, _, _ = walk_forward(F, y, core, "ridge", alpha=10, min_train=120, oos_start="2012-01-31"); add("Ridge all, min_train 120 (OOS from 2012)", p, note="later OOS start")
    p, _, _ = walk_forward(F, y, core, "ridge", alpha=10, shuffle_seed=0); add("PLACEBO ridge on shuffled target", p, note="should be ~0")
    add("Combo: prior sign + ridge sign (avg)", (np.sign(comp) + pos) / 2)
    add("Combo: prior sign + follow-the-ECB (avg)", (np.sign(comp) + (-np.sign(F["r_dfr_chg3"])).replace(0, np.nan).ffill()) / 2)
    p0, _, _ = walk_forward(F, y0, core, "ridge", alpha=10); add("Ridge all, FRONT contract", p0, rank=0, note="contract choice")
    R = pd.DataFrame(results).T; R.to_csv(f"{OUT}/results_main.csv")
    pd.DataFrame(curves).to_csv(f"{OUT}/daily_pnl_curves.csv"); pd.DataFrame(positions).to_csv(f"{OUT}/monthly_positions.csv")
    g.to_csv(f"{OUT}/prior_group_scores.csv")
    # ---- sub-periods ----
    keys = ["BM long-only 2nd contract", "BM trend 12M", "BM follow-the-ECB (-sign of DFR 3M change)", "Prior composite, sign (R+M+I+S)", "Prior composite, scaled (clip +/-2)",
            "Prior composite, user factors only (R+M+S)", "Ridge all factors (a=10), sign", "Ridge all factors (a=100), sign", "Logit direction (C=0.1), sign", "Combo: prior sign + follow-the-ECB (avg)"]
    rows = []
    for k in keys:
        for sname, (s, e) in SUBS.items():
            mm = metrics(curves[k], curves[k].abs() * 0 + 1, start=s, end=e); rows.append(dict(variant=k, period=sname, sharpe=mm["sharpe"], ann_ret_bp=mm["ann_ret_bp"]))
        mm = metrics(curves[k], curves[k].abs() * 0 + 1, start="2002-06-30", end="2007-12-31"); rows.append(dict(variant=k, period="2002-07 (pre-OOS)", sharpe=mm["sharpe"], ann_ret_bp=mm["ann_ret_bp"]))
    S = pd.DataFrame(rows).pivot(index="variant", columns="period", values="sharpe").loc[keys, ["2002-07 (pre-OOS)"] + list(SUBS)]
    S.to_csv(f"{OUT}/subperiod_sharpe.csv")
    return R, S, coef, F, y, g

if __name__ == "__main__":
    R, S, coef, F, y, g = run_all()
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 20)
    print(R[["sharpe", "ann_ret_bp", "ann_vol_bp", "maxdd_bp", "cagr_vt", "maxdd_vt", "hit", "months", "t_stat", "exposure", "note"]].round(2).to_string())
    print("\nSub-period Sharpe:\n", S.round(2).to_string())
    print("\nMean ridge coefficient:\n", coef.mean().sort_values().round(4).to_string())
