"""Append Eurex Three-Month EURIBOR futures (FEU3) daily settlements to data/eurex_feu3_history.csv.

Eurex's public statistics API only serves the trailing ~21 business days, so run this at least every
three weeks (cron, launchd, or a scheduled routine) to accumulate a real settlement history over time.
Idempotent: re-running only adds days that are not already stored.
"""
import requests, time, os, pandas as pd
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"); OUT = os.path.join(D, "eurex_feu3_history.csv")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36", "Accept": "application/json"}
API = "https://www.eurex.com/api/v1/overallstatistics/40828"       # productId 40828 = FEU3
old = pd.read_csv(OUT, parse_dates=["date", "expiry"]) if os.path.exists(OUT) else pd.DataFrame(columns=["date", "expiry", "settle", "last", "volume", "oi"])
have = set(old["date"].dt.strftime("%Y%m%d")) if len(old) else set()
hdr = requests.get(API, params={"busdate": pd.Timestamp.today().strftime("%Y%m%d"), "filtertype": "overview"}, headers=UA, timeout=40).json()["header"]
dates = sorted(pd.to_datetime(x[:10], format="%d-%m-%Y") for x in hdr["tradingDates"])
rows = []
for d in dates:
    if d.strftime("%Y%m%d") in have: continue
    j = requests.get(API, params={"busdate": d.strftime("%Y%m%d"), "filtertype": "overview"}, headers=UA, timeout=40).json()
    rows += [dict(date=d, expiry=pd.to_datetime(x["date"]), settle=x["dSettle"], last=x["last"], volume=x["volume"], oi=x["openInt"]) for x in j.get("dataRows", [])]
    time.sleep(0.4)
new = pd.concat([old, pd.DataFrame(rows)], ignore_index=True).drop_duplicates(["date", "expiry"]).sort_values(["date", "expiry"])
new.to_csv(OUT, index=False)
print(f"added {len(rows)} rows; history now {new['date'].nunique()} days, {new['date'].min().date()} -> {new['date'].max().date()}")
