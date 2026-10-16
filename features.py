"""Monthly feature matrix + daily P&L inputs for the Euribor macro strategy.

Every feature is timestamped at a month-end t and uses only information published by t
(publication lags applied per source). Target = next month's price change of the 2nd
quarterly synthetic Euribor future (points; +1 = rates expected to fall by 1%).
"""
import numpy as np, pandas as pd, os
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def ecb(name):
    df = pd.read_csv(f"{D}/ecb_{name}.csv"); s = pd.to_numeric(df["value"], errors="coerce")
    idx = df["date"].astype(str)
    if idx.str.len().max() == 7:      # YYYY-MM -> month end
        s.index = pd.PeriodIndex(idx, freq="M").to_timestamp(how="end").normalize()
    elif "W" in idx.iloc[0]:          # YYYY-Www -> Friday of ISO week
        s.index = pd.to_datetime(idx + "-5", format="%G-W%V-%u")
    else:
        s.index = pd.to_datetime(idx)
    return s.dropna().sort_index()

def month_end_last(s):      # daily/weekly series -> value as of each month-end
    return s.resample("ME").last()

def lag_monthly(s, k):      # monthly series indexed at month-end of reference month -> shift availability by k months
    return s.shift(k)

def zscore_expanding(s, min_periods=36):
    m = s.expanding(min_periods).mean(); sd = s.expanding(min_periods).std()
    return (s - m) / sd

def build():
    # ---------- daily market data ----------
    cont = pd.read_csv(f"{D}/euribor_futures_continuous.csv", index_col=0, parse_dates=True)
    eur = pd.read_csv(f"{D}/euribor_daily.csv", index_col=0, parse_dates=True)
    cum1 = cont["chg1"].fillna(0).cumsum()          # roll-adjusted 2nd-contract index
    cum0 = cont["chg0"].fillna(0).cumsum()
    dfr = ecb("dfr"); mro = ecb("mro_fixed").combine_first(ecb("mro_minbid"))
    ciss = ecb("ciss")
    yc2 = ecb("yc_aaa_2y"); yc10 = ecb("yc_aaa_10y"); yc10c = ecb("yc_all_10y")
    M = pd.DataFrame(index=cont.resample("ME").last().index)
    m = month_end_last
    M["px1"] = m(cont["px1"]); M["dte1"] = m(cont["dte1"])
    M["cum1"] = m(cum1); M["cum0"] = m(cum0)
    M["eur3m"] = m(eur["3m"]); M["eur12m"] = m(eur["12m"]); M["eur1m"] = m(eur["1m"])
    M["dfr"] = m(dfr).ffill(); M["mro"] = m(mro).ffill()
    M["ciss"] = m(ciss); M["yc2y"] = m(yc2); M["yc10y"] = m(yc10); M["yc10y_all"] = m(yc10c)
    # ---------- monthly macro (ECB / Eurostat) ----------
    for k in ["m1", "m2", "m3", "loans_private", "mfi_debt_hold_ea", "mfi_debt_hold_nonea", "mfi_ext_assets", "unemp"]:
        M[k] = ecb(k).reindex(M.index)
    for k in ["ltgy_de", "ltgy_it", "ltgy_es", "ltgy_fr"]:
        M[k] = ecb(k).reindex(M.index)
    h = pd.read_csv(f"{D}/eurostat_hicp.csv"); h.index = pd.PeriodIndex(h["date"], freq="M").to_timestamp(how="end").normalize()
    M["hicp"] = h["hicp"].reindex(M.index); M["hicp_core"] = h["hicp_core"].reindex(M.index)
    e = pd.read_csv(f"{D}/eurostat_esi.csv"); e.index = pd.PeriodIndex(e["date"], freq="M").to_timestamp(how="end").normalize()
    M["esi"] = pd.to_numeric(e["value"], errors="coerce").reindex(M.index)
    # EPU (policyuncertainty.com)
    x = pd.read_excel(f"{D}/epu_europe.xlsx", sheet_name="European News-Index" if False else 0)
    x = x[pd.to_numeric(x["Year"], errors="coerce").notna()].copy()
    x.index = pd.PeriodIndex([f"{int(y)}-{int(mm):02d}" for y, mm in zip(x["Year"], x["Month"])], freq="M").to_timestamp(how="end").normalize()
    for c, n in [("European_News_Index", "epu_eu"), ("Germany_News_Index", "epu_de"), ("France_News_Index", "epu_fr"), ("Italy_News_Index", "epu_it"), ("Spain_News_Index", "epu_es")]:
        M[n] = pd.to_numeric(x[c], errors="coerce").reindex(M.index)
    # Eurosystem balance sheet (weekly) as of t (published ~4 days after the Friday -> shift one week)
    ilm = ecb("eurosystem_assets_w"); ilm.index = ilm.index + pd.Timedelta(days=7)
    M["ecb_assets"] = m(ilm).ffill()
    # TIC: EA holdings of US Treasuries (monthly, ~6-week publication lag -> 2-month lag)
    tic = pd.read_csv(f"{D}/tic_ea_holdings.csv", index_col=0, parse_dates=True)
    for c in ["tic_ea_all", "tic_ea_core", "tic_grand_total"]:
        M[c] = tic[c].reindex(M.index)
    # BIS: EA banks' cross-border claims by currency (quarterly, ~5-month publication lag)
    if os.path.exists(f"{D}/bis_lbs_ea.csv"):
        b = pd.read_csv(f"{D}/bis_lbs_ea.csv"); b.index = pd.PeriodIndex(b["date"].str.replace("-Q", "Q"), freq="Q").to_timestamp(how="end").normalize()
        b.index = b.index + pd.offsets.MonthEnd(5)      # availability date
        for c in ["bis_xb_claims_usd", "bis_xb_claims_eur"]:
            M[c] = b[c].reindex(M.index).ffill()
    # US rates (FRED, daily)
    for fid, n in [("DGS2", "us2y"), ("DFF", "usff")]:
        f = pd.read_csv(f"{D}/fred_{fid}.csv"); f.columns = ["date", "value"]; f["value"] = pd.to_numeric(f["value"], errors="coerce")
        s = f.set_index(pd.to_datetime(f["date"]))["value"].dropna(); M[n] = m(s)

    # ---------- features (known at t) ----------
    F = pd.DataFrame(index=M.index)
    L = lag_monthly
    # Rates (R)
    F["r_dfr_chg3"] = M["dfr"] - M["dfr"].shift(3)
    F["r_dfr_chg6"] = M["dfr"] - M["dfr"].shift(6)
    F["r_slope"] = M["eur12m"] - M["eur3m"]
    F["r_slope_chg3"] = F["r_slope"] - F["r_slope"].shift(3)
    F["r_12m_chg3"] = M["eur12m"] - M["eur12m"].shift(3)
    F["r_3m_minus_dfr"] = M["eur3m"] - M["dfr"]
    F["r_fut_mom3"] = M["cum1"] - M["cum1"].shift(3)
    F["r_fut_mom12"] = M["cum1"] - M["cum1"].shift(12)
    # Money (M) -- monthly stocks, 1-month publication lag
    for k, n in [("m1", "m_m1"), ("m3", "m_m3"), ("loans_private", "m_loans")]:
        s = np.log(L(M[k], 1))
        F[n + "_yoy"] = (s - s.shift(12)) * 100
    s = np.log(L(M["m3"], 1)); F["m_m3_6m_ann"] = (s - s.shift(6)) * 200
    F["m_m3_accel"] = F["m_m3_yoy"] - F["m_m3_yoy"].shift(6)
    F["m_real_m1"] = F["m_m1_yoy"] - L(M["hicp"], 1)
    s = np.log(M["ecb_assets"]); F["m_ecb_bs_yoy"] = (s - s.shift(12)) * 100
    F["m_ecb_bs_chg3"] = (s - s.shift(3)) * 100
    # Debt holdings (D)
    ea = L(M["mfi_debt_hold_ea"], 1); nea = L(M["mfi_debt_hold_nonea"], 1)
    share = nea / (ea + nea) * 100
    F["d_nonea_share_chg12"] = share - share.shift(12)
    F["d_nonea_yoy"] = (np.log(nea) - np.log(nea).shift(12)) * 100
    F["d_ea_yoy"] = (np.log(ea) - np.log(ea).shift(12)) * 100
    F["d_ea_minus_nonea"] = F["d_ea_yoy"] - F["d_nonea_yoy"]
    tc = L(M["tic_ea_core"], 2); ta = L(M["tic_ea_all"], 2); tg = L(M["tic_grand_total"], 2)
    F["d_tic_core_yoy"] = (np.log(tc) - np.log(tc).shift(12)) * 100
    F["d_tic_all_yoy"] = (np.log(ta) - np.log(ta).shift(12)) * 100
    tsh = ta / tg * 100; F["d_tic_share_chg12"] = tsh - tsh.shift(12)
    if "bis_xb_claims_usd" in M:
        ush = M["bis_xb_claims_usd"] / (M["bis_xb_claims_usd"] + M["bis_xb_claims_eur"]) * 100
        F["d_bis_usd_share_chg12"] = ush - ush.shift(12)
        F["d_bis_usd_yoy"] = (np.log(M["bis_xb_claims_usd"]) - np.log(M["bis_xb_claims_usd"]).shift(12)) * 100
        F["d_bis_eur_yoy"] = (np.log(M["bis_xb_claims_eur"]) - np.log(M["bis_xb_claims_eur"]).shift(12)) * 100
    # Inflation (I) -- extension beyond the user's list
    F["i_hicp"] = L(M["hicp"], 1); F["i_core"] = L(M["hicp_core"], 1)
    F["i_hicp_chg3"] = F["i_hicp"] - F["i_hicp"].shift(3)
    F["i_core_chg3"] = F["i_core"] - F["i_core"].shift(3)
    F["i_unemp_chg6"] = L(M["unemp"], 2) - L(M["unemp"], 2).shift(6)
    # Sentiment / political (S)
    le = np.log(L(M["epu_eu"], 1))
    F["s_epu_z"] = zscore_expanding(le); F["s_epu_chg3"] = (le - le.shift(3)) * 100
    F["s_epu_periph"] = (np.log(L(M["epu_it"], 1)) + np.log(L(M["epu_es"], 1)) - np.log(L(M["epu_de"], 1)) - np.log(L(M["epu_fr"], 1))) / 2 * 100
    F["s_epu_periph_chg3"] = F["s_epu_periph"] - F["s_epu_periph"].shift(3)
    F["s_periph_spread"] = (M["ltgy_it"] + M["ltgy_es"]) / 2 - M["ltgy_de"]
    F["s_periph_chg3"] = F["s_periph_spread"] - F["s_periph_spread"].shift(3)
    F["s_ciss"] = M["ciss"]; F["s_ciss_chg3"] = M["ciss"] - M["ciss"].shift(3)
    F["s_esi_z"] = zscore_expanding(L(M["esi"], 1)); F["s_esi_chg3"] = L(M["esi"], 1) - L(M["esi"], 1).shift(3)
    # US rates (U) -- extension
    F["u_2y_chg3"] = M["us2y"] - M["us2y"].shift(3)
    F["u_ff_chg3"] = M["usff"] - M["usff"].shift(3)
    F["u_2y_minus_eu12m"] = M["us2y"] - M["eur12m"]

    # ---------- target: next-month change of 2nd-contract price (points) ----------
    y = (M["cum1"].shift(-1) - M["cum1"]).rename("y_next")
    y0 = (M["cum0"].shift(-1) - M["cum0"]).rename("y0_next")
    return M, F, y, y0, cont

GROUPS = {"R": "Rates", "M": "Money", "D": "Debt holdings", "I": "Inflation", "S": "Sentiment/political", "U": "US rates"}
# Prior signs for the un-fitted composite (sign of expected effect on the futures PRICE, i.e. -rates)
PRIOR = {
    "r_dfr_chg3": -1, "r_dfr_chg6": -1, "r_slope": +1, "r_slope_chg3": -1, "r_12m_chg3": -1, "r_3m_minus_dfr": +1, "r_fut_mom3": +1, "r_fut_mom12": +1,
    "m_m1_yoy": -1, "m_m3_yoy": -1, "m_loans_yoy": -1, "m_m3_6m_ann": -1, "m_m3_accel": -1, "m_real_m1": -1, "m_ecb_bs_yoy": +1, "m_ecb_bs_chg3": +1,
    "i_hicp": -1, "i_core": -1, "i_hicp_chg3": -1, "i_core_chg3": -1, "i_unemp_chg6": +1,
    "s_epu_z": +1, "s_epu_chg3": +1, "s_epu_periph": +1, "s_epu_periph_chg3": +1, "s_periph_spread": +1, "s_periph_chg3": +1, "s_ciss": +1, "s_ciss_chg3": +1, "s_esi_z": -1, "s_esi_chg3": -1,
    "u_2y_chg3": -1, "u_ff_chg3": -1, "u_2y_minus_eu12m": 0,
    # debt-holdings signs are not pinned down by theory -> excluded from the prior composite (0), learned by the fitted models
    "d_nonea_share_chg12": 0, "d_nonea_yoy": 0, "d_ea_yoy": 0, "d_ea_minus_nonea": 0, "d_tic_core_yoy": 0, "d_tic_all_yoy": 0, "d_tic_share_chg12": 0,
    "d_bis_usd_share_chg12": 0, "d_bis_usd_yoy": 0, "d_bis_eur_yoy": 0,
}

if __name__ == "__main__":
    M, F, y, y0, cont = build()
    print(F.shape); print(F.notna().idxmax().sort_values().to_string())
    print(F.tail(2).T)
    F.join(y).join(y0).to_csv(os.path.join(D, "features_monthly.csv"))
