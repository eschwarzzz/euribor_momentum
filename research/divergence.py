"""Where do the strategy paths diverge from the follow-the-ECB rule, and did it pay?

44 paths: the prior-sign composites, the fitted models, the nested ridge and 27 CPCV paths. For each month the
share of paths against the rule and their relative P&L; episodes of sustained divergence; attribution of the
composite's disagreements to the group that pushed hardest.
"""
import warnings

import numpy as np
import pandas as pd

from euribor.config import COMPOSITE, COMPOSITE_SCALED, ECB_RULE, LOGIT, OOS_END, OOS_START, RESULTS, RIDGE_10, RIDGE_100
from euribor.data import core_feature_columns, load_features, load_group_scores, load_positions
from euribor.montecarlo import CPCV_MODELS, cpcv_predictions

warnings.filterwarnings("ignore")
PATH_KEYS = [COMPOSITE, COMPOSITE_SCALED, "Prior composite, user factors only (R+M+S)", "Prior composite drop R", "Prior composite drop M",
             "Prior composite drop I", "Prior composite drop S", "Prior composite, rolling 60M z-scores", "Prior composite, 3M smoothed signal",
             "Ridge all factors (a=1), sign", RIDGE_10, RIDGE_100, "Ridge all factors (a=1000), sign", "Lasso all factors (a=0.01), sign", LOGIT,
             "Ridge user factors only (R+M+D+S)"]


def main():
    window = slice(OOS_START, OOS_END)
    P, G = load_positions(), load_group_scores()
    F, y, _ = load_features()
    core = core_feature_columns(F)
    ecb = P[ECB_RULE]
    paths = {k: np.sign(P[k]) for k in PATH_KEYS}
    paths["Nested ridge"] = np.sign(pd.read_csv(RESULTS / "nested_positions.csv", index_col=0, parse_dates=True)["pos"])
    X = F[core]
    ok = X.notna().all(axis=1) & y.notna()
    X, yv = X[ok], y[ok]
    for model, alpha, label in CPCV_MODELS:
        _, cpcv_paths = cpcv_predictions(X, yv, model, alpha)
        for j, preds in enumerate(cpcv_paths):
            paths[f"CPCV {label.lower().replace(' a=', '')} path{j}"] = np.sign(preds)
    PT = pd.DataFrame(paths).loc[window].reindex(ecb.loc[window].index)
    E, Y = ecb.loc[window], y.loc[window] * 100
    print(f"{PT.shape[1]} paths x {len(PT)} months")
    disagree = PT.apply(lambda s: (s != E) & s.notna() & (s != 0))
    relative = PT.apply(lambda s: (s - E) * Y)                        # relative P&L vs the rule, bp, before costs
    intensity, rel_mean = disagree.mean(axis=1), relative.mean(axis=1)

    # 1. by year
    by_year = pd.DataFrame({"share_paths_disagreeing": intensity.groupby(intensity.index.year).mean(),
                            "avg_rel_pnl_bp_per_month": rel_mean.groupby(rel_mean.index.year).mean(),
                            "composite_rel_pnl_bp_year": relative[COMPOSITE].groupby(relative.index.year).sum()})
    print("\n[1] By year: share of paths disagreeing with follow-the-ECB, average relative P&L per month across paths, composite's relative P&L for the year:")
    print(by_year.round(2).to_string())
    # 2. months
    top = pd.DataFrame({"share_disagree": intensity, "avg_rel_pnl_bp": rel_mean, "ecb_pos": E, "comp_pos": PT[COMPOSITE], "next_month_chg_bp": Y}).join(G.round(2))
    print("\n[2] Twelve months where most paths diverge from the ECB rule (positions decided at month-end, P&L is the following month):")
    print(top.sort_values("share_disagree", ascending=False).head(12).round(2).to_string())
    print("\n    Ten months where divergence cost the most / paid the most (average across paths):")
    print(pd.concat([top.sort_values("avg_rel_pnl_bp").head(5), top.sort_values("avg_rel_pnl_bp", ascending=False).head(5)]).round(1).to_string())
    # 3. episodes of three or more months with a majority against the rule
    episodes, current = [], []
    for t, v in intensity.items():
        if v > 0.5:
            current.append(t)
        else:
            if len(current) >= 3:
                episodes.append(current)
            current = []
    if len(current) >= 3:
        episodes.append(current)
    print("\n[3] Divergence episodes (3+ consecutive months with a majority of paths against the ECB rule):")
    for run in episodes:
        seg = relative.loc[run]
        print(f"   {run[0].strftime('%Y-%m')} to {run[-1].strftime('%Y-%m')} ({len(run)} mo): ECB pos {E.loc[run].mean():+.1f}, "
              f"avg rel P&L across paths {seg.mean(axis=1).sum():+.0f} bp, composite rel P&L {seg[COMPOSITE].sum():+.0f} bp, "
              f"group scores R {G.loc[run, 'R'].mean():+.2f} M {G.loc[run, 'M'].mean():+.2f} I {G.loc[run, 'I'].mean():+.2f} S {G.loc[run, 'S'].mean():+.2f}")
    # 4. composite attribution
    comp = PT[COMPOSITE]
    differs = (comp != E) & comp.notna()
    Gw = G.loc[window].reindex(comp.index)
    rows = []
    for t in comp.index[differs]:
        sc, side = Gw.loc[t], comp.loc[t]
        drivers = sc[np.sign(sc) == side]
        driver = drivers.abs().idxmax() if len(drivers) else "none"
        rows.append(dict(date=t, driver=driver, driver_score=sc[driver] if driver != "none" else np.nan,
                         n_groups_with_composite=int((np.sign(sc) == side).sum()), rel_pnl_bp=relative.loc[t, COMPOSITE], ecb_pos=E.loc[t]))
    A = pd.DataFrame(rows).set_index("date")
    hit = lambda s: (s > 0).mean()      # noqa: E731
    print(f"\n[4] Composite disagrees with the ECB rule in {len(A)} of {differs.notna().sum()} months. Attribution to the group that pushed hardest against the ECB rule:")
    print(A.groupby("driver").agg(months=("rel_pnl_bp", "size"), rel_pnl_sum_bp=("rel_pnl_bp", "sum"), rel_pnl_mean_bp=("rel_pnl_bp", "mean"),
                                  hit_rate=("rel_pnl_bp", hit)).round(2).to_string())
    print("\n    by how many groups sided with the composite against the ECB rule:")
    print(A.groupby("n_groups_with_composite").agg(months=("rel_pnl_bp", "size"), rel_pnl_sum_bp=("rel_pnl_bp", "sum"), hit_rate=("rel_pnl_bp", hit)).round(2).to_string())
    print("\n    by ECB rule position at the time (i.e. was the composite fading a cutting cycle or a hiking cycle):")
    print(A.groupby("ecb_pos").agg(months=("rel_pnl_bp", "size"), rel_pnl_sum_bp=("rel_pnl_bp", "sum"), hit_rate=("rel_pnl_bp", hit)).round(2).to_string())
    # 5. each group's standalone agreement with the rule
    print("\n[5] Group-level: correlation of each group's score with the ECB rule position, and the group's relative P&L vs the rule when it disagrees:")
    for g in "RMIS":
        s = np.sign(Gw[g])
        d = (s != E) & (s != 0)
        r = ((s - E) * Y)[d]
        print(f"   {g}: corr with ECB position {np.corrcoef(Gw[g].fillna(0), E)[0, 1]:+.2f} | disagrees {d.mean():.0%} of months | "
              f"relative P&L when it disagrees {r.sum():+.0f} bp, hit {(r > 0).mean():.0%}")
    A.to_csv(RESULTS / "divergence_attribution.csv")
    top.to_csv(RESULTS / "divergence_monthly.csv")
    by_year.to_csv(RESULTS / "divergence_by_year.csv")


if __name__ == "__main__":
    main()
