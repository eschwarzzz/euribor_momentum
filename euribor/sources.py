"""Download the public source series into data/raw. Everything is free and needs no API key.

Sources and what they feed:

* ECB Data Portal (``fetch_ecb``): policy rates, Euribor monthly averages, EONIA/€STR, M1-M3, loans, MFI debt holdings,
  HICP (ECB copy, ends 2025-12), unemployment, AAA and all-issuer yield curves, Eurosystem balance sheet, CISS,
  long-term government yields.
* Bundesbank (``fetch_bundesbank``): daily Euribor 1W-12M since December 1998 (the ECB portal dropped the daily
  series) and the daily EONIA swap curve 2005-06 to 2014-06 used for the OIS-based instrument.
* Eurostat (``fetch_eurostat``): HICP headline and core on the ECOICOP v2 classification (the only series that
  continues past 2025), and the economic sentiment indicator.
* policyuncertainty.com (``fetch_epu``): the European news-based policy uncertainty workbook.
* FRED (``fetch_fred``): US 2-year yield, fed funds, 3-month bill, 2s10s.
* BIS locational banking statistics (``fetch_bis``): euro-area banks' cross-border claims by currency, summed over
  the thirteen reporting euro-area countries.
* US Treasury TIC (``fetch_tic``): the "Major Foreign Holders" history and current table are downloaded;
  ``data/raw/tic_ea_holdings.csv`` (euro-area holdings, 7- and 4-country sums) was assembled from them by hand in
  September 2026 and is committed, because the Treasury's country coverage changes between the two tables.
* Eurex (``collect_eurex``): FEU3 daily settlements; the public API serves only the trailing ~21 business days, so
  the collector appends to a history file and should run every two to three weeks.

The credit-demand research inputs (``eurostat_gfcf_q.csv``, ``eurostat_sts_capex_m.csv``, ``ecb_bls_demand_q.csv``)
were one-off Eurostat and ECB downloads for a rejected feature block and are committed as processed tables.
"""
import io
import time

import pandas as pd
import requests

from .config import RAW

TIMEOUT = 120
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}


def get(url, tries=3, **kwargs):
    """requests.get with a timeout and a few retries; the public endpoints occasionally stall."""
    kwargs.setdefault("timeout", TIMEOUT)
    for attempt in range(tries):
        try:
            r = requests.get(url, **kwargs)
            r.raise_for_status()
            return r
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt == tries - 1:
                raise
            print(f"  retry {attempt + 1} after {type(e).__name__}: {url[:80]}")
            time.sleep(5 * (attempt + 1))

# ---------------------------------------------------------------- ECB Data Portal
ECB_BASE = "https://data-api.ecb.europa.eu/service/data/"
ECB_SERIES = {
    # policy rates (daily)
    "dfr": "FM/D.U2.EUR.4F.KR.DFR.LEV",
    "mro_fixed": "FM/D.U2.EUR.4F.KR.MRR_FR.LEV",
    "mro_minbid": "FM/D.U2.EUR.4F.KR.MRR_MBR.LEV",
    # Euribor monthly averages
    "euribor1m_m": "FM/M.U2.EUR.RT.MM.EURIBOR1MD_.HSTA",
    "euribor3m_m": "FM/M.U2.EUR.RT.MM.EURIBOR3MD_.HSTA",
    "euribor6m_m": "FM/M.U2.EUR.RT.MM.EURIBOR6MD_.HSTA",
    "euribor1y_m": "FM/M.U2.EUR.RT.MM.EURIBOR1YD_.HSTA",
    # overnight
    "eonia": "EON/D.EONIA_TO.RATE",
    "estr": "EST/B.EU000A2X2A25.WT",
    # money and credit (monthly, seasonally adjusted stocks)
    "m1": "BSI/M.U2.Y.V.M10.X.1.U2.2300.Z01.E",
    "m2": "BSI/M.U2.Y.V.M20.X.1.U2.2300.Z01.E",
    "m3": "BSI/M.U2.Y.V.M30.X.1.U2.2300.Z01.E",
    "loans_private": "BSI/M.U2.Y.U.A20T.A.1.U2.2250.Z01.E",
    # MFI holdings of debt securities by issuer residence (not seasonally adjusted stocks)
    "mfi_debt_hold_ea": "BSI/M.U2.N.A.A30.A.1.U2.0000.Z01.E",
    "mfi_debt_hold_nonea": "BSI/M.U2.N.A.A30.A.1.U4.0000.Z01.E",
    "mfi_ext_assets": "BSI/M.U2.N.A.AXG.A.1.U4.0000.Z01.E",
    # prices and labour (the ECB HICP keys stop at 2025-12; Eurostat continues them)
    "hicp": "ICP/M.U2.N.000000.4.ANR",
    "hicp_core": "ICP/M.U2.N.XEF000.4.ANR",
    "unemp": "LFSI/M.I9.S.UNEHRT.TOTAL0.15_74.T",
    # yield curves (daily, from 2004-09)
    "yc_aaa_3m": "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_3M",
    "yc_aaa_6m": "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_6M",
    "yc_aaa_1y": "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_1Y",
    "yc_aaa_2y": "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_2Y",
    "yc_aaa_10y": "YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y",
    "yc_all_2y": "YC/B.U2.EUR.4F.G_N_C.SV_C_YM.SR_2Y",
    "yc_all_10y": "YC/B.U2.EUR.4F.G_N_C.SV_C_YM.SR_10Y",
    # long-term government yields, monthly (periphery spread before the yield curve starts)
    "ltgy_de": "IRS/M.DE.L.L40.CI.0000.EUR.N.Z",
    "ltgy_it": "IRS/M.IT.L.L40.CI.0000.EUR.N.Z",
    "ltgy_es": "IRS/M.ES.L.L40.CI.0000.EUR.N.Z",
    "ltgy_fr": "IRS/M.FR.L.L40.CI.0000.EUR.N.Z",
    # systemic stress and the Eurosystem balance sheet
    "ciss": "CISS/D.U2.Z0Z.4F.EC.SS_CIN.IDX",
    "eurosystem_assets_w": "ILM/W.U2.C.T000000.Z5.Z01",
}


def fetch_ecb(out=RAW, names=None):
    for name, key in ECB_SERIES.items():
        if names and name not in names:
            continue
        try:
            r = get(ECB_BASE + key, params={"format": "csvdata", "startPeriod": "1998-01-01"}, headers={"Accept": "text/csv"})
            df = pd.read_csv(io.StringIO(r.text))[["TIME_PERIOD", "OBS_VALUE"]].rename(columns={"TIME_PERIOD": "date", "OBS_VALUE": "value"})
            df.to_csv(out / f"ecb_{name}.csv", index=False)
            print(f"ecb {name:20s} {len(df):6d} rows  {df.date.iloc[0]} -> {df.date.iloc[-1]}")
        except Exception as e:                                   # noqa: BLE001  (one failed series should not stop the rest)
            print(f"ecb {name:20s} FAILED {e}")
        time.sleep(0.3)


# ---------------------------------------------------------------- Bundesbank
BUNDESBANK_BASE = "https://api.statistiken.bundesbank.de/rest/data/BBIG1/"
EURIBOR_TENORS = {"1w": "W01", "1m": "M01", "3m": "M03", "6m": "M06", "9m": "M09", "12m": "M12"}
EONIA_SWAP_TENORS = {"1w": "W01", "1m": "M01", "3m": "M03", "6m": "M06", "12m": "M12"}


def _bundesbank_series(key):
    """A BBIG1 series as a Series; the CSV carries several metadata rows before the dated observations."""
    r = get(BUNDESBANK_BASE + key, params={"format": "csv", "lang": "en"})
    rows = [line.split(",") for line in r.text.lstrip("﻿").splitlines()]
    data = [(row[0].strip('"'), row[1]) for row in rows if len(row) >= 2 and len(row[0].strip('"')) == 10 and row[0].strip('"')[4] == "-"]
    s = pd.Series({pd.Timestamp(d): pd.to_numeric(v, errors="coerce") for d, v in data}).dropna().sort_index()
    return s, r.text


def fetch_bundesbank(out=RAW):
    euribor = {}
    for tenor, code in EURIBOR_TENORS.items():
        s, raw = _bundesbank_series(f"D.D0.EUR.MMKT.EURIBOR.{code}.BID._Z")
        (out / f"buba_euribor_{code}.csv").write_text(raw)
        euribor[tenor] = s
        print(f"bundesbank euribor {tenor:3s} {len(s):5d} days  {s.index[0].date()} -> {s.index[-1].date()}")
        time.sleep(0.3)
    daily = pd.DataFrame(euribor).rename_axis("date")
    daily.to_csv(out / "euribor_daily.csv")
    swaps = {}
    for tenor, code in EONIA_SWAP_TENORS.items():
        s, _ = _bundesbank_series(f"D.D0.EUR.MMKT.EOSWAP.{code}._Z._Z")
        swaps[tenor] = s
        time.sleep(0.3)
    ois = pd.DataFrame(swaps).rename_axis("date")
    ois.to_csv(out / "eonia_swap_daily.csv")
    print(f"bundesbank eonia swaps {len(ois)} days  {ois.index[0].date()} -> {ois.index[-1].date()}")


# ---------------------------------------------------------------- Eurostat
EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"


def _eurostat_jsonstat(dataset, **filters):
    """One Eurostat dataset slice as a long frame (one column per dimension plus ``value``)."""
    r = get(EUROSTAT_BASE + dataset, params={**filters, "format": "JSON", "lang": "EN"})
    j = r.json()
    dims = j["id"]
    sizes = j["size"]
    labels = [list(j["dimension"][d]["category"]["index"]) for d in dims]
    rows = []
    for flat, value in j["value"].items():
        i, coords = int(flat), []
        for n in reversed(sizes):
            coords.append(i % n)
            i //= n
        coords.reverse()
        rows.append({d: labels[k][c] for k, (d, c) in enumerate(zip(dims, coords))} | {"value": value})
    return pd.DataFrame(rows)


def fetch_eurostat(out=RAW):
    hicp = _eurostat_jsonstat("prc_hicp_minr", geo="EA", unit="RCH_A", coicop18=["TOTAL", "TOT_X_NRG_FOOD"])
    wide = hicp.pivot(index="time", columns="coicop18", values="value").rename(columns={"TOTAL": "hicp", "TOT_X_NRG_FOOD": "hicp_core"})
    wide = wide[["hicp", "hicp_core"]].rename_axis("date").sort_index()
    wide.to_csv(out / "eurostat_hicp.csv")
    print(f"eurostat hicp {len(wide)} months  {wide.index[0]} -> {wide.index[-1]}")
    esi = _eurostat_jsonstat("ei_bssi_m_r2", geo="EA21", indic="BS-ESI-I", s_adj="SA")
    esi = esi.set_index("time")["value"].rename_axis("date").sort_index()
    esi.to_csv(out / "eurostat_esi.csv")
    print(f"eurostat esi  {len(esi)} months  {esi.index[0]} -> {esi.index[-1]}")


# ---------------------------------------------------------------- policy uncertainty, FRED
EPU_URL = "https://www.policyuncertainty.com/media/Europe_Policy_Uncertainty_Data.xlsx"
FRED_SERIES = ["DGS2", "DFF", "DGS3MO", "T10Y2Y"]


def fetch_epu(out=RAW):
    r = get(EPU_URL, headers=HEADERS)
    (out / "epu_europe.xlsx").write_bytes(r.content)
    print(f"epu workbook {len(r.content) / 1e3:.0f} kB")


def fetch_fred(out=RAW):
    for sid in FRED_SERIES:
        r = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}")
        (out / f"fred_{sid}.csv").write_text(r.text)
        print(f"fred {sid:7s} {r.text.count(chr(10))} rows")


# ---------------------------------------------------------------- BIS locational banking statistics
BIS_BASE = "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_LBS_D_PUB/1.0/"
BIS_EA_COUNTRIES = ["DE", "FR", "IT", "ES", "NL", "BE", "LU", "AT", "FI", "PT", "GR", "IE", "CY"]   # no euro-area aggregate exists


def _bis_rows(key, **extra):
    r = get(BIS_BASE + key, params={"format": "csv"})
    df = pd.read_csv(io.StringIO(r.text))
    for k, v in extra.items():
        df[k] = v
    return df


def process_bis(usd_raw, to1_raw):
    """Quarterly euro-area bank cross-border claims: USD-denominated, all currencies, foreign currencies, euro (all minus foreign)."""
    usd = usd_raw[usd_raw["cur"] == "USD"].groupby("TIME_PERIOD")["OBS_VALUE"].sum(min_count=1)
    all_cur = to1_raw[to1_raw["L_CURR_TYPE"] == "A"].groupby("TIME_PERIOD")["OBS_VALUE"].sum(min_count=1)
    foreign = to1_raw[to1_raw["L_CURR_TYPE"] == "F"].groupby("TIME_PERIOD")["OBS_VALUE"].sum(min_count=1)
    out = pd.DataFrame({"bis_xb_claims_usd": usd, "bis_xb_claims_all": all_cur, "bis_xb_claims_fx": foreign})
    out["bis_xb_claims_eur"] = out["bis_xb_claims_all"] - out["bis_xb_claims_fx"]
    return out.rename_axis("date")


def fetch_bis(out=RAW):
    usd = pd.concat([_bis_rows(f"Q.S.C.A.{cur}.F.5J.A.{cty}.A.5J.N", cur=cur, cty=cty) for cur in ("USD", "EUR") for cty in BIS_EA_COUNTRIES])
    to1 = pd.concat([_bis_rows(f"Q.S.C.A.TO1.{ctype}.5J.A.{cty}.A.5J.N", cty=cty) for ctype in ("A", "F", "U", "D") for cty in BIS_EA_COUNTRIES])
    usd.to_csv(out / "bis_lbs_ea_raw.csv", index=False)
    to1.to_csv(out / "bis_lbs_ea_to1_raw.csv", index=False)
    table = process_bis(usd, to1)
    table.to_csv(out / "bis_lbs_ea.csv")
    print(f"bis lbs {len(table)} quarters  {table.index[0]} -> {table.index[-1]}")


# ---------------------------------------------------------------- US Treasury TIC
TIC_HISTORY = "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/mfhhis01.txt"
TIC_CURRENT = "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.txt"


def fetch_tic(out=RAW):
    """Download the two Major Foreign Holders tables. ``tic_ea_holdings.csv`` is assembled from them by hand (see module docstring)."""
    for url, name in [(TIC_HISTORY, "tic_mfhhis01.txt"), (TIC_CURRENT, "tic_slt_table5.txt")]:
        r = get(url, headers=HEADERS)
        (out / name).write_bytes(r.content)
        print(f"tic {name} {len(r.content) / 1e3:.0f} kB")


# ---------------------------------------------------------------- Eurex FEU3 settlements
EUREX_API = "https://www.eurex.com/api/v1/overallstatistics/40828"        # productId 40828 = three-month Euribor future (FEU3)


def collect_eurex(out=RAW):
    """Append the trailing ~21 business days of FEU3 settlements to eurex_feu3_history.csv. Idempotent."""
    path = out / "eurex_feu3_history.csv"
    columns = ["date", "expiry", "settle", "last", "volume", "oi"]
    old = pd.read_csv(path, parse_dates=["date", "expiry"]) if path.exists() else pd.DataFrame(columns=columns)
    have = set(old["date"].dt.strftime("%Y%m%d")) if len(old) else set()
    headers = {**HEADERS, "Accept": "application/json"}
    header = get(EUREX_API, params={"busdate": pd.Timestamp.today().strftime("%Y%m%d"), "filtertype": "overview"}, headers=headers, timeout=40).json()["header"]
    dates = sorted(pd.to_datetime(x[:10], format="%d-%m-%Y") for x in header["tradingDates"])
    rows = []
    for day in dates:
        if day.strftime("%Y%m%d") in have:
            continue
        j = get(EUREX_API, params={"busdate": day.strftime("%Y%m%d"), "filtertype": "overview"}, headers=headers, timeout=40).json()
        rows += [dict(date=day, expiry=pd.to_datetime(x["date"]), settle=x["dSettle"], last=x["last"], volume=x["volume"], oi=x["openInt"])
                 for x in j.get("dataRows", [])]
        time.sleep(0.4)
    fresh = pd.DataFrame(rows, columns=columns)
    new = (pd.concat([old, fresh], ignore_index=True) if len(old) else fresh).drop_duplicates(["date", "expiry"]).sort_values(["date", "expiry"])
    new.to_csv(path, index=False)
    print(f"eurex: added {len(rows)} rows; history now {new['date'].nunique()} days, {new['date'].min().date()} -> {new['date'].max().date()}")


FETCHERS = {"ecb": fetch_ecb, "bundesbank": fetch_bundesbank, "eurostat": fetch_eurostat, "epu": fetch_epu, "fred": fetch_fred, "bis": fetch_bis,
            "tic": fetch_tic, "eurex": collect_eurex}


def main(sources=None, out=RAW):
    out.mkdir(parents=True, exist_ok=True)
    for name, fetch in FETCHERS.items():
        if sources and name not in sources:
            continue
        print(f"=== {name}")
        fetch(out)


if __name__ == "__main__":
    main()
