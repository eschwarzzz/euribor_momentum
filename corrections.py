"""Candidate corrections implied by the divergence map. All are post hoc trials and are counted as such."""
import numpy as np, pandas as pd, os, sys, warnings
warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT); D = f"{ROOT}/data"; R = f"{ROOT}/results"
from backtest import daily_pnl, metrics, OOS_START, OOS_END, SUBS
from features import PRIOR
F = pd.read_csv(f"{D}/features_monthly.csv", index_col=0, parse_dates=True); y = F.pop("y_next"); F.pop("y0_next")
cont = pd.read_csv(f"{D}/euribor_futures_continuous.csv", index_col=0, parse_dates=True)
P = pd.read_csv(f"{R}/monthly_positions.csv", index_col=0, parse_dates=True); G = pd.read_csv(f"{R}/prior_group_scores.csv", index_col=0, parse_dates=True)
ecb = P["BM follow-the-ECB (-sign of DFR 3M change)"]; comp = G[["R", "M", "I", "S"]].mean(axis=1); comp_xM = G[["R", "I", "S"]].mean(axis=1)
def override(anchor, score, tau):            # anchor position unless |score| > tau, then sign(score)
    return pd.Series(np.where(score.abs() > tau, np.sign(score), anchor), index=anchor.index)
cands = {"Follow-the-ECB (anchor)": ecb, "Composite (base)": np.sign(comp), "Composite without M": np.sign(comp_xM)}
for tau in (0.25, 0.5, 0.75): cands[f"ECB anchor, composite override |score|>{tau}"] = override(ecb, comp, tau)
for tau in (0.25, 0.5, 0.75): cands[f"ECB anchor, composite-ex-M override |score|>{tau}"] = override(ecb, comp_xM, tau)
for tau in (0.75, 1.0): cands[f"ECB anchor, stress override S>{tau} -> long"] = pd.Series(np.where(G["S"] > tau, 1.0, ecb), index=ecb.index)
cands["ECB anchor, stress S>1 long, inflation I<-1 short"] = pd.Series(np.where(G["S"] > 1.0, 1.0, np.where(G["I"] < -1.0, -1.0, ecb)), index=ecb.index)
rows = []; Y = y * 100
for k, pos in cands.items():
    pos = pos.reindex(F.index); pnl, pd_ = daily_pnl(pos, cont); m = metrics(pnl, pd_)
    w = pos.loc[OOS_START:OOS_END]; e = ecb.loc[OOS_START:OOS_END]; dis = (w != e) & w.notna(); relp = ((w - e) * Y.loc[OOS_START:OOS_END])[dis]
    subs = {s: metrics(pnl, pd_, start=a, end=b)["sharpe"] for s, (a, b) in SUBS.items()}
    rows.append(dict(variant=k, sharpe=m["sharpe"], ann_pnl_bp=m["ann_ret_bp"], maxdd_bp=m["maxdd_bp"], hit=m["hit"], months_vs_ecb=int(dis.sum()), rel_pnl_vs_ecb_bp=relp.sum(), **{s[:7]: v for s, v in subs.items()}))
T = pd.DataFrame(rows).set_index("variant"); pd.set_option("display.width", 250); print(T.round(2).to_string()); T.to_csv(f"{R}/corrections.csv")
print(f"\nadditional trials in this file: {len(cands) - 2}")
