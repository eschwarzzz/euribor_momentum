"""Compare the government-curve synthetic with the OIS-based synthetic over 2005-07 to 2014-06, and re-score key variants."""
import pandas as pd, numpy as np, os, sys
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT); D = f"{ROOT}/data"; R = f"{ROOT}/results"
from backtest import daily_pnl, metrics
gov = pd.read_csv(f"{D}/euribor_futures_continuous.csv", index_col=0, parse_dates=True)
ois = pd.read_csv(f"{D}/euribor_futures_continuous_ois.csv", index_col=0, parse_dates=True)
eur = pd.read_csv(f"{D}/euribor_daily.csv", index_col=0, parse_dates=True)["3m"]
w = slice("2005-07-01", "2014-06-25")
lvl = pd.DataFrame({"gov": gov.loc[w, "px1"], "ois": ois.loc[w, "px1"]}); d = (lvl["ois"] - lvl["gov"]) * 100
print("2nd contract, level difference OIS minus govt (bp): mean %.1f  sd %.1f  min %.1f  max %.1f" % (d.mean(), d.std(), d.min(), d.max()))
print("by year:", d.groupby(d.index.year).mean().round(1).to_dict())
for name, freq in [("daily", "D"), ("weekly", "W-FRI"), ("monthly", "ME")]:
    a = gov.loc[w, "chg1"].fillna(0).resample(freq).sum() * 100; b = ois.loc[w, "chg1"].fillna(0).resample(freq).sum() * 100
    a, b = a[a != 0], b[a != 0]
    print(f"{name:8s} changes: corr {a.corr(b):.2f} | sd govt {a.std():.1f} bp, sd ois {b.std():.1f} bp | tracking error {(a-b).std():.1f} bp | cumulative govt {a.sum():+.0f} vs ois {b.sum():+.0f} bp")
# implied futures-minus-spot by year under each construction
for lab, c in [("govt", gov), ("ois", ois)]:
    m = (100 - c.loc[w, "px1"]) - eur.reindex(c.loc[w].index); print(f"{lab}: 2nd-contract implied rate minus spot 3M Euribor, yearly mean (bp):", (m.groupby(m.index.year).mean() * 100).round(0).to_dict())
# re-score key variants on both instruments, 2008-01 to 2014-06 (positions unchanged: signals are price-independent except two momentum features)
P = pd.read_csv(f"{R}/monthly_positions.csv", index_col=0, parse_dates=True)
keys = ["BM long-only 2nd contract", "BM follow-the-ECB (-sign of DFR 3M change)", "Prior composite, sign (R+M+I+S)", "Prior composite, scaled (clip +/-2)", "Ridge all factors (a=10), sign", "Logit direction (C=0.1), sign"]
rows = []
for k in keys:
    for lab, c in [("govt-curve", gov), ("OIS-based", ois)]:
        pnl, pos = daily_pnl(P[k], c); m = metrics(pnl, pos, start="2008-01-01", end="2014-06-25")
        rows.append(dict(variant=k, instrument=lab, sharpe=m["sharpe"], ann_pnl_bp=m["ann_ret_bp"], maxdd_bp=m["maxdd_bp"], hit=m["hit"]))
T = pd.DataFrame(rows).pivot(index="variant", columns="instrument", values=["sharpe", "ann_pnl_bp", "maxdd_bp"]).loc[keys]
pd.set_option("display.width", 200); print("\n2008-01 to 2014-06, same positions, two instruments:"); print(T.round(2).to_string())
T.to_csv(f"{R}/instrument_comparison_2008_2014.csv")
# monthly P&L correlation between instruments for the composite
pa, _ = daily_pnl(P["Prior composite, sign (R+M+I+S)"], gov); pb, _ = daily_pnl(P["Prior composite, sign (R+M+I+S)"], ois)
ma = pa.loc["2008":"2014-06"].resample("ME").sum() * 100; mb = pb.loc["2008":"2014-06"].resample("ME").sum() * 100
print(f"\ncomposite monthly P&L: corr between instruments {ma.corr(mb):.2f}, mean abs difference {(ma-mb).abs().mean():.1f} bp/month, sd of monthly P&L {ma.std():.1f} bp")
