"""Synthetic 3M Euribor futures (quarterly IMM contracts) — daily prices.

Futures rate for the contract expiring at IMM date T (time-to-expiry t1 days):
    F_t(T) = Euribor3M_t + [ f_gov(t1, t1+91) - f_gov(0, 91) ]
i.e. spot 3M Euribor plus the risk-free forward premium read off the ECB AAA government
zero curve (3M/6M/1Y spot rates, log-linear discount-factor interpolation, money-market
convention). Price = 100 - F. At expiry the price is exactly 100 - 3M Euribor.

Why not bootstrap the forward from the Euribor deposit curve (1M/3M/6M/12M)? The 6M and 12M
deposit rates carry a larger credit/liquidity premium than the 3M tenor, so a single-curve
forward overstates the expected 3M rate and every contract "converges" upward into expiry:
an artificial drift of tens of bp a year (long-only Sharpe > 6 in 2013-19). Before the ECB
yield curve starts (2004-09-06) that tenor basis was 1-3bp, so the deposit-curve forward is
used there as a fallback.
"""
import numpy as np, pandas as pd, os
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DEP_TENOR_DAYS = {"1w": 7, "1m": 30, "3m": 91, "6m": 182, "9m": 273, "12m": 365}
GOV_TENOR_DAYS = {"g3m": 91, "g6m": 182, "g1y": 365}

def imm_dates(start, end):
    out = []
    for y in range(start.year, end.year + 2):
        for m in (3, 6, 9, 12):
            d = pd.Timestamp(y, m, 1); wed = d + pd.DateOffset(days=int((2 - d.dayofweek) % 7)); out.append(wed + pd.DateOffset(days=14))
    return [d for d in out if start <= d <= end + pd.DateOffset(days=400)]

def fwd_mm(days, ldf, t1, t2):
    """Money-market forward (%, ACT/360) from a log-DF curve, log-linear interpolation."""
    l1 = np.interp(t1, days, ldf); l2 = np.interp(t2, days, ldf)
    return (np.exp(l1 - l2) - 1.0) * 360.0 / (t2 - t1) * 100.0

def dep_curve(row):
    days = [0.0]; ldf = [0.0]
    for t, n in DEP_TENOR_DAYS.items():
        r = row.get(t, np.nan)
        if pd.notna(r): days.append(float(n)); ldf.append(-np.log1p(r / 100.0 * n / 360.0))
    return np.array(days), np.array(ldf)

def gov_curve(row):
    days = [0.0]; ldf = [0.0]
    for t, n in GOV_TENOR_DAYS.items():
        r = row.get(t, np.nan)
        if pd.notna(r): days.append(float(n)); ldf.append(-n / 365.0 * np.log1p(r / 100.0))   # annually compounded spot -> log DF
    return np.array(days), np.array(ldf)

OIS_TENOR_DAYS = {"1w": 7, "1m": 30, "3m": 91, "6m": 182, "12m": 365}
def ois_curve(row):
    days = [0.0]; ldf = [0.0]
    for t, n in OIS_TENOR_DAYS.items():
        r = row.get(t, np.nan)
        if pd.notna(r): days.append(float(n)); ldf.append(-np.log1p(r / 100.0 * n / 360.0))
    return np.array(days), np.array(ldf)

def build(eur, gov, ois=None):
    """Priority per day: OIS-based (EONIA swap forward + Euribor-OIS basis) if `ois` given and complete,
    else government-curve based, else deposit-curve fallback."""
    imm = imm_dates(eur.index.min(), eur.index.max()); recs = []
    for dt, row in eur.iterrows():
        o = ois.loc[dt] if (ois is not None and dt in ois.index) else None
        use_ois = o is not None and o[["1m", "3m", "6m", "12m"]].notna().all()
        g = gov.loc[dt] if dt in gov.index else None
        use_gov = (not use_ois) and g is not None and g.notna().all()
        if use_ois: od, ol = ois_curve(o); s_o = fwd_mm(od, ol, 0, 91)
        elif use_gov: gd, gl = gov_curve(g); s_g = fwd_mm(gd, gl, 0, 91)
        else: dd, dl = dep_curve(row)
        for k, ex in enumerate([d for d in imm if d >= dt][:3]):
            t1 = (ex - dt).days; t2 = t1 + 91
            if t2 > 365: continue
            if t1 == 0: f = row["3m"]
            elif use_ois: f = row["3m"] + fwd_mm(od, ol, t1, t2) - s_o
            elif use_gov: f = row["3m"] + fwd_mm(gd, gl, t1, t2) - s_g
            else: f = fwd_mm(dd, dl, t1, t2)
            recs.append((dt, k, ex, t1, 100.0 - f, "ois" if use_ois else ("gov" if use_gov else "dep")))
    return pd.DataFrame(recs, columns=["date", "rank", "expiry", "dte", "price", "method"])

def continuous(fut):
    out = {}
    for k in (0, 1, 2):
        s = fut[fut["rank"] == k].set_index("date")
        same = s["expiry"] == s["expiry"].shift(1)
        chg = (s["price"] - s["price"].shift(1)).where(same)
        if k < 2:
            nxt = fut[fut["rank"] == k + 1].set_index("date")
            for d in s.index[~same & (np.arange(len(s)) > 0)]:
                dprev = s.index[s.index.get_loc(d) - 1]
                if dprev in nxt.index and nxt.loc[dprev, "expiry"] == s.loc[d, "expiry"]:
                    chg.loc[d] = s.loc[d, "price"] - nxt.loc[dprev, "price"]
        out[f"px{k}"] = s["price"]; out[f"chg{k}"] = chg; out[f"dte{k}"] = s["dte"]; out[f"exp{k}"] = s["expiry"]
    return pd.DataFrame(out)

if __name__ == "__main__":
    eur = pd.read_csv(f"{D}/euribor_daily.csv", index_col=0, parse_dates=True)
    gov = pd.DataFrame({n: pd.read_csv(f"{D}/ecb_yc_aaa_{t}.csv", index_col=0, parse_dates=True)["value"] for n, t in [("g3m", "3m"), ("g6m", "6m"), ("g1y", "1y")]})
    gov = gov.reindex(gov.index.union(eur.index)).sort_index().ffill(limit=5).reindex(eur.index)   # bridge isolated ECB holidays
    fut = build(eur, gov); fut.to_csv(f"{D}/synthetic_euribor_futures.csv", index=False)
    cont = continuous(fut); cont.to_csv(f"{D}/euribor_futures_continuous.csv")
    if os.path.exists(f"{D}/eonia_swap_daily.csv"):      # second instrument: OIS-based where the EONIA swap curve exists (2005-06 to 2014-06)
        ois = pd.read_csv(f"{D}/eonia_swap_daily.csv", index_col=0, parse_dates=True)
        ois = ois.reindex(ois.index.union(eur.index)).sort_index().ffill(limit=5).reindex(eur.index)
        fut_o = build(eur, gov, ois); fut_o.to_csv(f"{D}/synthetic_euribor_futures_ois.csv", index=False)
        continuous(fut_o).to_csv(f"{D}/euribor_futures_continuous_ois.csv")
        print("OIS-based instrument:"); print(fut_o.groupby(["rank", "method"]).agg(n=("price", "size"), first=("date", "min"), last=("date", "max")))
    print(fut.groupby(["rank", "method"]).agg(n=("price", "size"), first=("date", "min"), last=("date", "max")))
    print(cont[["px0", "px1", "px2"]].describe().T[["count", "mean", "std", "min", "max"]])
    ex = fut[(fut["rank"] == 0) & (fut["dte"] == 0)].merge(eur[["3m"]], left_on="date", right_index=True)
    print("expiry convergence max err:", (ex["price"] - (100 - ex["3m"])).abs().max())
    # drift diagnostics: annualised mean daily change (bp) and Sharpe of long-only rank-1 by period
    for a, b in [("2000", "2004"), ("2005", "2007"), ("2008", "2012"), ("2013", "2019"), ("2020", "2021"), ("2022", "2026")]:
        c = cont.loc[a:b, "chg1"].dropna(); print(f"{a}-{b}: long rank-1 drift {c.mean()*252*100:6.1f} bp/yr, vol {c.std()*np.sqrt(252)*100:6.1f} bp, SR {c.mean()/c.std()*np.sqrt(252):5.2f}")
    # implied futures rate minus spot (should be a few bp on average, not tens)
    m = fut[fut["rank"] == 1].merge(eur[["3m"]], left_on="date", right_index=True); m["fut_minus_spot"] = (100 - m["price"]) - m["3m"]
    print(m.groupby(m["date"].dt.year)["fut_minus_spot"].mean().round(3).to_string())
