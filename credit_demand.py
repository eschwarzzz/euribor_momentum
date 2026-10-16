"""Credit-demand block: capex momentum by industry + investment by asset + Bank Lending Survey loan demand.
Tested alone, against follow-the-ECB, and as the replacement for the money block inside the composite and the anchored override."""
import numpy as np, pandas as pd, os, sys, warnings
warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT); D = f"{ROOT}/data"; R = f"{ROOT}/results"
from backtest import daily_pnl, metrics, OOS_START, OOS_END, SUBS
F = pd.read_csv(f"{D}/features_monthly.csv", index_col=0, parse_dates=True); y = F.pop("y_next"); F.pop("y0_next"); idx = F.index
cont = pd.read_csv(f"{D}/euribor_futures_continuous.csv", index_col=0, parse_dates=True)
P = pd.read_csv(f"{R}/monthly_positions.csv", index_col=0, parse_dates=True); G = pd.read_csv(f"{R}/prior_group_scores.csv", index_col=0, parse_dates=True)
ecb = P["BM follow-the-ECB (-sign of DFR 3M change)"]
def z(s, minp=36): m = s.expanding(minp).mean(); sd = s.expanding(minp).std(); return ((s - m) / sd).clip(-3, 3)
def qtr_to_me(s, lag_months):   # quarterly period index -> availability month-end (quarter end + lag), then monthly ffill
    s = s.copy(); s.index = pd.PeriodIndex(s.index, freq="Q").to_timestamp(how="end").normalize() + pd.offsets.MonthEnd(lag_months); return s.reindex(idx, method="ffill")
def mon_to_me(s, lag_months):
    s = s.copy(); s.index = pd.PeriodIndex(s.index, freq="M").to_timestamp(how="end").normalize() + pd.offsets.MonthEnd(lag_months); return s.reindex(idx, method="ffill")
# ---- 1. quarterly fixed investment by asset (Eurostat, ~65-day lag -> 3 months) ----
Gq = pd.read_csv(f"{D}/eurostat_gfcf_q.csv", index_col=0)
bus = np.log(Gq["N11G"] - Gq["N111G"]); eqip = np.log(Gq["N11MG"] + Gq["N117G"])
C = pd.DataFrame(index=idx)
C["c_gfcf_bus_yoy"] = qtr_to_me((bus - bus.shift(4)) * 100, 3); C["c_gfcf_bus_2q"] = qtr_to_me((bus - bus.shift(2)) * 200, 3)
C["c_gfcf_eq_yoy"] = qtr_to_me((eqip - eqip.shift(4)) * 100, 3); C["c_gfcf_eq_accel"] = C["c_gfcf_eq_yoy"] - C["c_gfcf_eq_yoy"].shift(6)
# ---- 2. monthly capital-goods output by producing industry + construction (Eurostat STS, ~45-day lag -> 2 months) ----
S = pd.read_csv(f"{D}/eurostat_sts_capex_m.csv", index_col=0); inds = ["C26", "C27", "C28", "C29", "C30", "C33"]
mom12 = pd.DataFrame({i: mon_to_me((np.log(S[i]) - np.log(S[i]).shift(12)) * 100, 2) for i in inds}); mom3 = pd.DataFrame({i: mon_to_me((np.log(S[i]) - np.log(S[i]).shift(3)) * 400, 2) for i in inds})
C["c_ind_mom12"] = mom12.mean(axis=1); C["c_ind_mom3"] = mom3.mean(axis=1); C["c_ind_breadth"] = (mom12 > 0).mean(axis=1) * 100 - 50
C["c_ind_mom12_z"] = mom12.apply(z).mean(axis=1)              # z-score each industry first, then aggregate (the 'momentum by industry' construction)
C["c_cag_mom12"] = mon_to_me((np.log(S["MIG_CAG"]) - np.log(S["MIG_CAG"]).shift(12)) * 100, 2)
C["c_cag_rel_ip"] = C["c_cag_mom12"] - mon_to_me((np.log(S["B-D"]) - np.log(S["B-D"]).shift(12)) * 100, 2)   # capital goods relative to all industry
C["c_constr_mom12"] = mon_to_me((np.log(S["F"]) - np.log(S["F"]).shift(12)) * 100, 2)
# ---- 3. Bank Lending Survey: enterprise loan demand (quarter end + 1 month) ----
B = pd.read_csv(f"{D}/ecb_bls_demand_q.csv", index_col=0)
C["c_bls_demand"] = qtr_to_me(B["O"], 1); C["c_bls_fix"] = qtr_to_me(B["FIX"], 1); C["c_bls_ltl"] = qtr_to_me(B["LTL"], 1)
C["c_bls_demand_chg"] = C["c_bls_demand"] - C["c_bls_demand"].shift(12)
C.to_csv(f"{D}/features_credit_demand.csv")
print("credit-demand features first valid month:"); print(C.apply(lambda s: s.first_valid_index()).astype(str).to_string())
# ---- group score: all features carry prior sign -1 (more capex / more credit demand -> higher rates -> lower futures price) ----
Z = C.apply(z) * -1
sub = {"capex by industry (STS)": ["c_ind_mom12", "c_ind_mom3", "c_ind_breadth", "c_ind_mom12_z", "c_cag_mom12", "c_cag_rel_ip", "c_constr_mom12"],
       "investment by asset (GFCF)": ["c_gfcf_bus_yoy", "c_gfcf_bus_2q", "c_gfcf_eq_yoy", "c_gfcf_eq_accel"], "loan demand (BLS)": ["c_bls_demand", "c_bls_fix", "c_bls_ltl", "c_bls_demand_chg"]}
scores = {k: Z[v].mean(axis=1) for k, v in sub.items()}; Cscore = pd.DataFrame(scores).mean(axis=1)
G2 = G.copy(); G2["C"] = Cscore
comp_RIS = G[["R", "I", "S"]].mean(axis=1); comp_RISC = G2[["R", "I", "S", "C"]].mean(axis=1)
def override(anchor, score, tau): return pd.Series(np.where(score.abs() > tau, np.sign(score), anchor), index=anchor.index)
cands = {"Follow-the-ECB (policy momentum)": ecb, "BM trend 12M (price momentum)": P["BM trend 12M"],
         "Credit-demand block alone": np.sign(Cscore), "  capex by industry alone": np.sign(scores["capex by industry (STS)"]), "  investment by asset alone": np.sign(scores["investment by asset (GFCF)"]), "  BLS loan demand alone": np.sign(scores["loan demand (BLS)"]),
         "Composite R+I+S (ex money)": np.sign(comp_RIS), "Composite R+I+S+C": np.sign(comp_RISC),
         "ECB anchor, R+I+S override >0.5 (current winner)": override(ecb, comp_RIS, 0.5), "ECB anchor, R+I+S+C override >0.5": override(ecb, comp_RISC, 0.5), "ECB anchor, C-only override >0.75": override(ecb, Cscore, 0.75)}
Y = y * 100; rows = []
for k, pos in cands.items():
    pos = pos.reindex(idx); pnl, pd_ = daily_pnl(pos, cont); m = metrics(pnl, pd_)
    w = pos.loc[OOS_START:OOS_END]; e = ecb.loc[OOS_START:OOS_END]; dis = (w != e) & w.notna() & (w != 0); relp = ((w - e) * Y.loc[OOS_START:OOS_END])[dis]
    subs = {s[:7]: metrics(pnl, pd_, start=a, end=b)["sharpe"] for s, (a, b) in SUBS.items()}
    rows.append(dict(variant=k, sharpe=m["sharpe"], ann_pnl_bp=m["ann_ret_bp"], maxdd_bp=m["maxdd_bp"], hit=m["hit"], corr_with_ecb=np.corrcoef(w.fillna(0), e)[0, 1], months_vs_ecb=int(dis.sum()), rel_pnl_vs_ecb_bp=relp.sum(), **subs))
T = pd.DataFrame(rows).set_index("variant"); pd.set_option("display.width", 260); print("\n2008-01 to 2026-08:"); print(T.round(2).to_string()); T.to_csv(f"{R}/credit_demand_results.csv")
print(f"\nnew trials here: {len(cands) - 3} (ECB rule, 12M trend and the R+I+S override were already counted)")
print("\ncorrelation of the C score with the other group scores (2008+):"); print(G2.loc["2008":].corr().round(2)["C"].to_string())
# year-by-year relative P&L of the C block vs the ECB rule
pc = np.sign(Cscore).reindex(idx).loc[OOS_START:OOS_END]; e = ecb.loc[OOS_START:OOS_END]; rel = ((pc - e) * Y.loc[OOS_START:OOS_END]).where(pc != e, 0)
print("\nC block: relative P&L vs the ECB rule by year (bp), positive = C's disagreement paid:"); print(rel.groupby(rel.index.year).sum().round(0).to_string())
