"""Credit-demand block: capex momentum by industry, investment by asset and Bank Lending Survey loan demand.

Tested alone, against follow-the-ECB, and as a replacement for the money block inside the composite and the
anchored override. Rejected: it fails the same way money supply does (real-economy weakness reads as "cuts"
while inflation forbids them).
"""
import warnings

import numpy as np
import pandas as pd

from euribor.backtest import daily_pnl, metrics
from euribor.config import ECB_RULE, OOS_END, OOS_START, PROCESSED, RAW, RESULTS, SUBPERIODS, TREND_12M
from euribor.data import load_continuous, load_features, load_group_scores, load_positions
from euribor.signals import override

warnings.filterwarnings("ignore")
INDUSTRIES = ["C26", "C27", "C28", "C29", "C30", "C33"]       # capital-goods producing industries, Eurostat STS
BLOCKS = {"capex by industry (STS)": ["c_ind_mom12", "c_ind_mom3", "c_ind_breadth", "c_ind_mom12_z", "c_cag_mom12", "c_cag_rel_ip", "c_constr_mom12"],
          "investment by asset (GFCF)": ["c_gfcf_bus_yoy", "c_gfcf_bus_2q", "c_gfcf_eq_yoy", "c_gfcf_eq_accel"],
          "loan demand (BLS)": ["c_bls_demand", "c_bls_fix", "c_bls_ltl", "c_bls_demand_chg"]}


def zscore(s, min_periods=36):
    return ((s - s.expanding(min_periods).mean()) / s.expanding(min_periods).std()).clip(-3, 3)


def build_features(idx):
    """Credit-demand features on the monthly index, each shifted to its availability date and carried forward."""
    def quarterly(s, lag_months):
        s = s.copy()
        s.index = pd.PeriodIndex(s.index, freq="Q").to_timestamp(how="end").normalize() + pd.offsets.MonthEnd(lag_months)
        return s.reindex(idx, method="ffill")

    def monthly(s, lag_months):
        s = s.copy()
        s.index = pd.PeriodIndex(s.index, freq="M").to_timestamp(how="end").normalize() + pd.offsets.MonthEnd(lag_months)
        return s.reindex(idx, method="ffill")

    C = pd.DataFrame(index=idx)
    # quarterly fixed investment by asset (Eurostat, ~65-day lag -> 3 months)
    gfcf = pd.read_csv(RAW / "eurostat_gfcf_q.csv", index_col=0)
    business = np.log(gfcf["N11G"] - gfcf["N111G"])
    equipment = np.log(gfcf["N11MG"] + gfcf["N117G"])
    C["c_gfcf_bus_yoy"] = quarterly((business - business.shift(4)) * 100, 3)
    C["c_gfcf_bus_2q"] = quarterly((business - business.shift(2)) * 200, 3)
    C["c_gfcf_eq_yoy"] = quarterly((equipment - equipment.shift(4)) * 100, 3)
    C["c_gfcf_eq_accel"] = C["c_gfcf_eq_yoy"] - C["c_gfcf_eq_yoy"].shift(6)
    # monthly capital-goods output by producing industry and construction (Eurostat STS, ~45-day lag -> 2 months)
    sts = pd.read_csv(RAW / "eurostat_sts_capex_m.csv", index_col=0)
    mom12 = pd.DataFrame({i: monthly((np.log(sts[i]) - np.log(sts[i]).shift(12)) * 100, 2) for i in INDUSTRIES})
    mom3 = pd.DataFrame({i: monthly((np.log(sts[i]) - np.log(sts[i]).shift(3)) * 400, 2) for i in INDUSTRIES})
    C["c_ind_mom12"] = mom12.mean(axis=1)
    C["c_ind_mom3"] = mom3.mean(axis=1)
    C["c_ind_breadth"] = (mom12 > 0).mean(axis=1) * 100 - 50
    C["c_ind_mom12_z"] = mom12.apply(zscore).mean(axis=1)              # z-score each industry first, then aggregate
    C["c_cag_mom12"] = monthly((np.log(sts["MIG_CAG"]) - np.log(sts["MIG_CAG"]).shift(12)) * 100, 2)
    C["c_cag_rel_ip"] = C["c_cag_mom12"] - monthly((np.log(sts["B-D"]) - np.log(sts["B-D"]).shift(12)) * 100, 2)
    C["c_constr_mom12"] = monthly((np.log(sts["F"]) - np.log(sts["F"]).shift(12)) * 100, 2)
    # Bank Lending Survey: enterprise loan demand (quarter end + 1 month)
    bls = pd.read_csv(RAW / "ecb_bls_demand_q.csv", index_col=0)
    C["c_bls_demand"] = quarterly(bls["O"], 1)
    C["c_bls_fix"] = quarterly(bls["FIX"], 1)
    C["c_bls_ltl"] = quarterly(bls["LTL"], 1)
    C["c_bls_demand_chg"] = C["c_bls_demand"] - C["c_bls_demand"].shift(12)
    return C


def main():
    pd.set_option("display.width", 260)
    F, y, _ = load_features()
    idx = F.index
    cont = load_continuous()
    P, G = load_positions(), load_group_scores()
    ecb = P[ECB_RULE]
    C = build_features(idx)
    C.to_csv(PROCESSED / "features_credit_demand.csv")
    print("credit-demand features first valid month:")
    print(C.apply(lambda s: s.first_valid_index()).astype(str).to_string())
    # group score: every feature carries prior sign -1 (more capex or credit demand -> higher rates -> lower futures price)
    Z = C.apply(zscore) * -1
    scores = {k: Z[v].mean(axis=1) for k, v in BLOCKS.items()}
    c_score = pd.DataFrame(scores).mean(axis=1)
    G2 = G.copy()
    G2["C"] = c_score
    comp_ris, comp_risc = G[["R", "I", "S"]].mean(axis=1), G2[["R", "I", "S", "C"]].mean(axis=1)
    candidates = {"Follow-the-ECB (policy momentum)": ecb, "BM trend 12M (price momentum)": P[TREND_12M],
                  "Credit-demand block alone": np.sign(c_score),
                  "  capex by industry alone": np.sign(scores["capex by industry (STS)"]),
                  "  investment by asset alone": np.sign(scores["investment by asset (GFCF)"]),
                  "  BLS loan demand alone": np.sign(scores["loan demand (BLS)"]),
                  "Composite R+I+S (ex money)": np.sign(comp_ris), "Composite R+I+S+C": np.sign(comp_risc),
                  "ECB anchor, R+I+S override >0.5 (current winner)": override(ecb, comp_ris, 0.5),
                  "ECB anchor, R+I+S+C override >0.5": override(ecb, comp_risc, 0.5),
                  "ECB anchor, C-only override >0.75": override(ecb, c_score, 0.75)}
    y_bp = y * 100
    rows = []
    for name, pos in candidates.items():
        pos = pos.reindex(idx)
        pnl, pos_d = daily_pnl(pos, cont)
        m = metrics(pnl, pos_d)
        w, e = pos.loc[OOS_START:OOS_END], ecb.loc[OOS_START:OOS_END]
        disagree = (w != e) & w.notna() & (w != 0)
        relative = ((w - e) * y_bp.loc[OOS_START:OOS_END])[disagree]
        subs = {s[:7]: metrics(pnl, pos_d, start=a, end=b)["sharpe"] for s, (a, b) in SUBPERIODS.items()}
        rows.append(dict(variant=name, sharpe=m["sharpe"], ann_pnl_bp=m["ann_ret_bp"], maxdd_bp=m["maxdd_bp"], hit=m["hit"],
                         corr_with_ecb=np.corrcoef(w.fillna(0), e)[0, 1], months_vs_ecb=int(disagree.sum()), rel_pnl_vs_ecb_bp=relative.sum(), **subs))
    T = pd.DataFrame(rows).set_index("variant")
    print("\n2008-01 to 2026-08:")
    print(T.round(2).to_string())
    T.to_csv(RESULTS / "credit_demand_results.csv")
    print(f"\nnew trials here: {len(candidates) - 3} (ECB rule, 12M trend and the R+I+S override were already counted)")
    print("\ncorrelation of the C score with the other group scores (2008+):")
    print(G2.loc["2008":].corr().round(2)["C"].to_string())
    pc = np.sign(c_score).reindex(idx).loc[OOS_START:OOS_END]
    e = ecb.loc[OOS_START:OOS_END]
    rel = ((pc - e) * y_bp.loc[OOS_START:OOS_END]).where(pc != e, 0)
    print("\nC block: relative P&L vs the ECB rule by year (bp), positive = C's disagreement paid:")
    print(rel.groupby(rel.index.year).sum().round(0).to_string())


if __name__ == "__main__":
    main()
