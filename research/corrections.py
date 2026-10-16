"""Candidate corrections implied by the divergence map. All are post hoc trials and are counted as such."""
import warnings

import numpy as np
import pandas as pd

from euribor.backtest import daily_pnl, metrics
from euribor.config import ECB_RULE, OOS_END, OOS_START, RESULTS, SUBPERIODS
from euribor.data import load_continuous, load_features, load_group_scores, load_positions
from euribor.signals import override

warnings.filterwarnings("ignore")


def main():
    pd.set_option("display.width", 250)
    F, y, _ = load_features()
    cont = load_continuous()
    P, G = load_positions(), load_group_scores()
    ecb = P[ECB_RULE]
    comp, comp_ex_money = G[["R", "M", "I", "S"]].mean(axis=1), G[["R", "I", "S"]].mean(axis=1)
    candidates = {"Follow-the-ECB (anchor)": ecb, "Composite (base)": np.sign(comp), "Composite without M": np.sign(comp_ex_money)}
    for tau in (0.25, 0.5, 0.75):
        candidates[f"ECB anchor, composite override |score|>{tau}"] = override(ecb, comp, tau)
    for tau in (0.25, 0.5, 0.75):
        candidates[f"ECB anchor, composite-ex-M override |score|>{tau}"] = override(ecb, comp_ex_money, tau)
    for tau in (0.75, 1.0):
        candidates[f"ECB anchor, stress override S>{tau} -> long"] = pd.Series(np.where(G["S"] > tau, 1.0, ecb), index=ecb.index)
    candidates["ECB anchor, stress S>1 long, inflation I<-1 short"] = pd.Series(np.where(G["S"] > 1.0, 1.0, np.where(G["I"] < -1.0, -1.0, ecb)), index=ecb.index)
    y_bp = y * 100
    rows = []
    for name, pos in candidates.items():
        pos = pos.reindex(F.index)
        pnl, pos_d = daily_pnl(pos, cont)
        m = metrics(pnl, pos_d)
        w, e = pos.loc[OOS_START:OOS_END], ecb.loc[OOS_START:OOS_END]
        disagree = (w != e) & w.notna()
        relative = ((w - e) * y_bp.loc[OOS_START:OOS_END])[disagree]
        subs = {s[:7]: metrics(pnl, pos_d, start=a, end=b)["sharpe"] for s, (a, b) in SUBPERIODS.items()}
        rows.append(dict(variant=name, sharpe=m["sharpe"], ann_pnl_bp=m["ann_ret_bp"], maxdd_bp=m["maxdd_bp"], hit=m["hit"],
                         months_vs_ecb=int(disagree.sum()), rel_pnl_vs_ecb_bp=relative.sum(), **subs))
    T = pd.DataFrame(rows).set_index("variant")
    print(T.round(2).to_string())
    T.to_csv(RESULTS / "corrections.csv")
    print(f"\nadditional trials in this file: {len(candidates) - 2}")


if __name__ == "__main__":
    main()
