"""Fetch ECB Data Portal series to data/ecb_<name>.csv (date,value)."""
import io, sys, time, requests, pandas as pd
BASE = "https://data-api.ecb.europa.eu/service/data/"
SERIES = {
    # policy rates (daily)
    "dfr":        "FM/D.U2.EUR.4F.KR.DFR.LEV",
    "mro_fixed":  "FM/D.U2.EUR.4F.KR.MRR_FR.LEV",
    "mro_minbid": "FM/D.U2.EUR.4F.KR.MRR_MBR.LEV",
    # Euribor monthly averages
    "euribor1m_m": "FM/M.U2.EUR.RT.MM.EURIBOR1MD_.HSTA",
    "euribor3m_m": "FM/M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA",
    "euribor6m_m": "FM/M.U2.EUR.RT.MM.EURIBOR6MD_.HSTA",
    "euribor1y_m": "FM/M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA",
    # overnight
    "eonia": "EON/D.EONIA_TO.RATE",
    "estr":  "EST/B.EU000A2X2A25.WT",
    # money & credit (monthly, SA stocks)
    "m1": "BSI/M.U2.Y.V.M10.X.1.U2.2300.Z01.E",
    "m2": "BSI/M.U2.Y.V.M20.X.1.U2.2300.Z01.E",
    "m3": "BSI/M.U2.Y.V.M30.X.1.U2.2300.Z01.E",
    "loans_private": "BSI/M.U2.Y.U.A20T.A.1.U2.2250.Z01.E",
    # MFI holdings of debt securities by issuer residence (NSA stocks)
    "mfi_debt_hold_ea":   "BSI/M.U2.N.A.A30.A.1.U2.0000.Z01.E",
    "mfi_debt_hold_nonea":"BSI/M.U2.N.A.A30.A.1.U4.0000.Z01.E",
    "mfi_ext_assets":     "BSI/M.U2.N.A.AXG.A.1.U4.0000.Z01.E",
    # prices / labour
    "hicp":      "ICP/M.U2.N.000000.4.ANR",
    "hicp_core": "ICP/M.U2.N.XEF000.4.ANR",
    "unemp":     "LFSI/M.I9.S.UNEHRT.TOTAL0.15_74.T",
    # yield curves (daily, from 2004-09)
    "yc_aaa_3m":  "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M",
    "yc_aaa_6m":  "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_6M",
    "yc_aaa_1y":  "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y",
    "yc_aaa_2y":  "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y",
    "yc_aaa_10y": "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",
    "yc_all_2y":  "YC/B.U2.EUR.4F.G_N_C.SV_C_YM.SR_2Y",
    "yc_all_10y": "YC/B.U2.EUR.4F.G_N_C.SV_C_YM.SR_10Y",
    # long-term govt yields monthly (for periphery spread pre-2004)
    "ltgy_de": "IRS/M.DE.L.L40.CI.0000.EUR.N.Z",
    "ltgy_it": "IRS/M.IT.L.L40.CI.0000.EUR.N.Z",
    "ltgy_es": "IRS/M.ES.L.L40.CI.0000.EUR.N.Z",
    "ltgy_fr": "IRS/M.FR.L.L40.CI.0000.EUR.N.Z",
}
def fetch(key):
    r = requests.get(BASE + key, params={"format": "csvdata", "startPeriod": "1998-01-01"},
                     headers={"Accept": "text/csv"}, timeout=120)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    return df[["TIME_PERIOD", "OBS_VALUE"]].rename(columns={"TIME_PERIOD": "date", "OBS_VALUE": "value"})
for name, key in SERIES.items():
    try:
        df = fetch(key); df.to_csv(f"data/ecb_{name}.csv", index=False)
        print(f"{name:20s} {len(df):6d} rows  {df.date.iloc[0]} -> {df.date.iloc[-1]}")
    except Exception as e:
        print(f"{name:20s} FAILED {e}")
    time.sleep(0.3)
