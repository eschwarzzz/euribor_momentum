"""Monthly feature matrix and next-month target.

Every feature is stamped at a month-end t and uses only information published by t: publication lags are
applied per source (one month for most monthly macro series, two for unemployment and US Treasury holdings,
five for the quarterly BIS banking statistics, one week for the Eurosystem balance sheet). The target is next
month's change in the roll-adjusted price of the 2nd quarterly synthetic future, in points (+1 = rates
expected to fall by one percentage point).

Feature groups, by the first letter of the column name: r = rates and policy, m = money, d = debt holdings,
i = inflation, s = sentiment and political stress, u = US rates.
"""
import numpy as np
import pandas as pd

from .config import PROCESSED, RAW
from .data import load_continuous, load_euribor_daily, read_ecb_series, read_fred, read_monthly_csv

GROUPS = {"R": "Rates", "M": "Money", "D": "Debt holdings", "I": "Inflation", "S": "Sentiment/political", "U": "US rates"}

# Prior sign of each feature's effect on the futures PRICE (i.e. minus its effect on rates), fixed from theory
# before any backtest. Debt-holdings features have no theory-pinned sign (0): they enter the fitted models only.
PRIOR = {
    "r_dfr_chg3": -1, "r_dfr_chg6": -1, "r_slope": +1, "r_slope_chg3": -1, "r_12m_chg3": -1, "r_3m_minus_dfr": +1,
    "r_fut_mom3": +1, "r_fut_mom12": +1,
    "m_m1_yoy": -1, "m_m3_yoy": -1, "m_loans_yoy": -1, "m_m3_6m_ann": -1, "m_m3_accel": -1, "m_real_m1": -1,
    "m_ecb_bs_yoy": +1, "m_ecb_bs_chg3": +1,
    "i_hicp": -1, "i_core": -1, "i_hicp_chg3": -1, "i_core_chg3": -1, "i_unemp_chg6": +1,
    "s_epu_z": +1, "s_epu_chg3": +1, "s_epu_periph": +1, "s_epu_periph_chg3": +1, "s_periph_spread": +1,
    "s_periph_chg3": +1, "s_ciss": +1, "s_ciss_chg3": +1, "s_esi_z": -1, "s_esi_chg3": -1,
    "u_2y_chg3": -1, "u_ff_chg3": -1, "u_2y_minus_eu12m": 0,
    "d_nonea_share_chg12": 0, "d_nonea_yoy": 0, "d_ea_yoy": 0, "d_ea_minus_nonea": 0,
    "d_tic_core_yoy": 0, "d_tic_all_yoy": 0, "d_tic_share_chg12": 0,
    "d_bis_usd_share_chg12": 0, "d_bis_usd_yoy": 0, "d_bis_eur_yoy": 0,
}

EPU_COLUMNS = [("European_News_Index", "epu_eu"), ("Germany_News_Index", "epu_de"), ("France_News_Index", "epu_fr"),
               ("Italy_News_Index", "epu_it"), ("Spain_News_Index", "epu_es")]


def month_end_last(s):
    """Daily or weekly series -> its last value in each calendar month, stamped at month-end."""
    return s.resample("ME").last()


def zscore_expanding(s, min_periods=36):
    return (s - s.expanding(min_periods).mean()) / s.expanding(min_periods).std()


def log_yoy(s, periods=12, scale=100):
    """Log change over ``periods`` observations, in percent."""
    x = np.log(s)
    return (x - x.shift(periods)) * scale


def monthly_panel():
    """Assemble every input series on a month-end index, with publication lags applied where the source needs one."""
    cont = load_continuous()
    euribor = load_euribor_daily()
    M = pd.DataFrame(index=cont.resample("ME").last().index)

    # Daily market data as of month-end
    M["px1"] = month_end_last(cont["px1"])
    M["dte1"] = month_end_last(cont["dte1"])
    M["cum1"] = month_end_last(cont["chg1"].fillna(0).cumsum())    # roll-adjusted 2nd-contract index
    M["cum0"] = month_end_last(cont["chg0"].fillna(0).cumsum())
    M["eur3m"] = month_end_last(euribor["3m"])
    M["eur12m"] = month_end_last(euribor["12m"])
    M["eur1m"] = month_end_last(euribor["1m"])
    M["dfr"] = month_end_last(read_ecb_series("dfr")).ffill()
    M["mro"] = month_end_last(read_ecb_series("mro_fixed").combine_first(read_ecb_series("mro_minbid"))).ffill()
    M["ciss"] = month_end_last(read_ecb_series("ciss"))
    M["yc2y"] = month_end_last(read_ecb_series("yc_aaa_2y"))
    M["yc10y"] = month_end_last(read_ecb_series("yc_aaa_10y"))
    M["yc10y_all"] = month_end_last(read_ecb_series("yc_all_10y"))

    # Monthly ECB series (stocks and rates, reference month)
    for name in ["m1", "m2", "m3", "loans_private", "mfi_debt_hold_ea", "mfi_debt_hold_nonea", "mfi_ext_assets", "unemp",
                 "ltgy_de", "ltgy_it", "ltgy_es", "ltgy_fr"]:
        M[name] = read_ecb_series(name).reindex(M.index)

    # Eurostat inflation and sentiment
    hicp = read_monthly_csv("eurostat_hicp.csv")
    M["hicp"] = hicp["hicp"].reindex(M.index)
    M["hicp_core"] = hicp["hicp_core"].reindex(M.index)
    M["esi"] = read_monthly_csv("eurostat_esi.csv", "value").reindex(M.index)

    # Economic policy uncertainty (policyuncertainty.com), monthly news indices
    epu = pd.read_excel(RAW / "epu_europe.xlsx", sheet_name=0)
    epu = epu[pd.to_numeric(epu["Year"], errors="coerce").notna()].copy()
    epu.index = pd.PeriodIndex([f"{int(y)}-{int(m):02d}" for y, m in zip(epu["Year"], epu["Month"])], freq="M") \
        .to_timestamp(how="end").normalize()
    for source, name in EPU_COLUMNS:
        M[name] = pd.to_numeric(epu[source], errors="coerce").reindex(M.index)

    # Eurosystem balance sheet: weekly, published about four days after the Friday -> shift one week
    assets = read_ecb_series("eurosystem_assets_w")
    assets.index = assets.index + pd.Timedelta(days=7)
    M["ecb_assets"] = month_end_last(assets).ffill()

    # US Treasury holdings by euro-area countries (TIC): monthly, lag applied at feature stage
    tic = pd.read_csv(RAW / "tic_ea_holdings.csv", index_col=0, parse_dates=True)
    for c in ["tic_ea_all", "tic_ea_core", "tic_grand_total"]:
        M[c] = tic[c].reindex(M.index)

    # BIS: euro-area banks' cross-border claims by currency, quarterly with a ~5-month publication lag
    bis_path = RAW / "bis_lbs_ea.csv"
    if bis_path.exists():
        bis = pd.read_csv(bis_path)
        bis.index = pd.PeriodIndex(bis["date"].str.replace("-Q", "Q"), freq="Q").to_timestamp(how="end").normalize()
        bis.index = bis.index + pd.offsets.MonthEnd(5)
        for c in ["bis_xb_claims_usd", "bis_xb_claims_eur"]:
            M[c] = bis[c].reindex(M.index).ffill()

    # US rates (FRED, daily)
    M["us2y"] = month_end_last(read_fred("DGS2"))
    M["usff"] = month_end_last(read_fred("DFF"))
    return M, cont


def feature_matrix(M):
    """Features known at each month-end, from the assembled panel."""
    F = pd.DataFrame(index=M.index)
    lag = lambda s, k: s.shift(k)       # noqa: E731  (a monthly series published k months after its reference month)

    # Rates (R): all daily, no lag
    F["r_dfr_chg3"] = M["dfr"] - M["dfr"].shift(3)
    F["r_dfr_chg6"] = M["dfr"] - M["dfr"].shift(6)
    F["r_slope"] = M["eur12m"] - M["eur3m"]
    F["r_slope_chg3"] = F["r_slope"] - F["r_slope"].shift(3)
    F["r_12m_chg3"] = M["eur12m"] - M["eur12m"].shift(3)
    F["r_3m_minus_dfr"] = M["eur3m"] - M["dfr"]
    F["r_fut_mom3"] = M["cum1"] - M["cum1"].shift(3)
    F["r_fut_mom12"] = M["cum1"] - M["cum1"].shift(12)

    # Money (M): monthly stocks with a one-month publication lag
    for source, name in [("m1", "m_m1"), ("m3", "m_m3"), ("loans_private", "m_loans")]:
        F[name + "_yoy"] = log_yoy(lag(M[source], 1))
    F["m_m3_6m_ann"] = log_yoy(lag(M["m3"], 1), periods=6, scale=200)
    F["m_m3_accel"] = F["m_m3_yoy"] - F["m_m3_yoy"].shift(6)
    F["m_real_m1"] = F["m_m1_yoy"] - lag(M["hicp"], 1)
    F["m_ecb_bs_yoy"] = log_yoy(M["ecb_assets"])
    F["m_ecb_bs_chg3"] = log_yoy(M["ecb_assets"], periods=3)

    # Debt holdings (D): MFI holdings by issuer residence, US Treasuries (TIC, two-month lag), BIS cross-border claims
    ea = lag(M["mfi_debt_hold_ea"], 1)
    non_ea = lag(M["mfi_debt_hold_nonea"], 1)
    share = non_ea / (ea + non_ea) * 100
    F["d_nonea_share_chg12"] = share - share.shift(12)
    F["d_nonea_yoy"] = log_yoy(non_ea)
    F["d_ea_yoy"] = log_yoy(ea)
    F["d_ea_minus_nonea"] = F["d_ea_yoy"] - F["d_nonea_yoy"]
    tic_core, tic_all, tic_total = (lag(M[c], 2) for c in ["tic_ea_core", "tic_ea_all", "tic_grand_total"])
    F["d_tic_core_yoy"] = log_yoy(tic_core)
    F["d_tic_all_yoy"] = log_yoy(tic_all)
    tic_share = tic_all / tic_total * 100
    F["d_tic_share_chg12"] = tic_share - tic_share.shift(12)
    if "bis_xb_claims_usd" in M:
        usd_share = M["bis_xb_claims_usd"] / (M["bis_xb_claims_usd"] + M["bis_xb_claims_eur"]) * 100
        F["d_bis_usd_share_chg12"] = usd_share - usd_share.shift(12)
        F["d_bis_usd_yoy"] = log_yoy(M["bis_xb_claims_usd"])
        F["d_bis_eur_yoy"] = log_yoy(M["bis_xb_claims_eur"])

    # Inflation (I): HICP one month, unemployment two months
    F["i_hicp"] = lag(M["hicp"], 1)
    F["i_core"] = lag(M["hicp_core"], 1)
    F["i_hicp_chg3"] = F["i_hicp"] - F["i_hicp"].shift(3)
    F["i_core_chg3"] = F["i_core"] - F["i_core"].shift(3)
    F["i_unemp_chg6"] = lag(M["unemp"], 2) - lag(M["unemp"], 2).shift(6)

    # Sentiment and political stress (S)
    log_epu = np.log(lag(M["epu_eu"], 1))
    F["s_epu_z"] = zscore_expanding(log_epu)
    F["s_epu_chg3"] = (log_epu - log_epu.shift(3)) * 100
    F["s_epu_periph"] = (np.log(lag(M["epu_it"], 1)) + np.log(lag(M["epu_es"], 1))
                         - np.log(lag(M["epu_de"], 1)) - np.log(lag(M["epu_fr"], 1))) / 2 * 100
    F["s_epu_periph_chg3"] = F["s_epu_periph"] - F["s_epu_periph"].shift(3)
    F["s_periph_spread"] = (M["ltgy_it"] + M["ltgy_es"]) / 2 - M["ltgy_de"]
    F["s_periph_chg3"] = F["s_periph_spread"] - F["s_periph_spread"].shift(3)
    F["s_ciss"] = M["ciss"]
    F["s_ciss_chg3"] = M["ciss"] - M["ciss"].shift(3)
    esi = lag(M["esi"], 1)
    F["s_esi_z"] = zscore_expanding(esi)
    F["s_esi_chg3"] = esi - esi.shift(3)

    # US rates (U): extension, daily
    F["u_2y_chg3"] = M["us2y"] - M["us2y"].shift(3)
    F["u_ff_chg3"] = M["usff"] - M["usff"].shift(3)
    F["u_2y_minus_eu12m"] = M["us2y"] - M["eur12m"]
    return F


def build():
    """Return the monthly panel M, features F, targets y (2nd contract) and y0 (front), and the daily continuous series."""
    M, cont = monthly_panel()
    F = feature_matrix(M)
    y = (M["cum1"].shift(-1) - M["cum1"]).rename("y_next")
    y0 = (M["cum0"].shift(-1) - M["cum0"]).rename("y0_next")
    return M, F, y, y0, cont


def main():
    M, F, y, y0, cont = build()
    print(F.shape)
    print("first month with a value, by feature:")
    print(F.notna().idxmax().sort_values().to_string())
    print(F.tail(2).T)
    F.join(y).join(y0).to_csv(PROCESSED / "features_monthly.csv")


if __name__ == "__main__":
    main()
