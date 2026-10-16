"""Compare the government-curve synthetic with the OIS-based synthetic over 2005-07 to 2014-06, and re-score key variants on both."""
import pandas as pd

from euribor.backtest import daily_pnl, metrics
from euribor.config import COMPOSITE, COMPOSITE_SCALED, ECB_RULE, LOGIT, LONG_ONLY, RESULTS, RIDGE_10
from euribor.data import load_continuous, load_euribor_daily, load_positions

WINDOW = slice("2005-07-01", "2014-06-25")


def main():
    pd.set_option("display.width", 200)
    gov, ois = load_continuous(), load_continuous(ois=True)
    euribor = load_euribor_daily()["3m"]
    level = pd.DataFrame({"gov": gov.loc[WINDOW, "px1"], "ois": ois.loc[WINDOW, "px1"]})
    d = (level["ois"] - level["gov"]) * 100
    print("2nd contract, level difference OIS minus govt (bp): mean %.1f  sd %.1f  min %.1f  max %.1f" % (d.mean(), d.std(), d.min(), d.max()))
    print("by year:", d.groupby(d.index.year).mean().round(1).to_dict())
    for name, freq in [("daily", "D"), ("weekly", "W-FRI"), ("monthly", "ME")]:
        a = gov.loc[WINDOW, "chg1"].fillna(0).resample(freq).sum() * 100
        b = ois.loc[WINDOW, "chg1"].fillna(0).resample(freq).sum() * 100
        a, b = a[a != 0], b[a != 0]
        print(f"{name:8s} changes: corr {a.corr(b):.2f} | sd govt {a.std():.1f} bp, sd ois {b.std():.1f} bp | tracking error {(a - b).std():.1f} bp | "
              f"cumulative govt {a.sum():+.0f} vs ois {b.sum():+.0f} bp")
    for label, c in [("govt", gov), ("ois", ois)]:
        m = (100 - c.loc[WINDOW, "px1"]) - euribor.reindex(c.loc[WINDOW].index)
        print(f"{label}: 2nd-contract implied rate minus spot 3M Euribor, yearly mean (bp):", (m.groupby(m.index.year).mean() * 100).round(0).to_dict())
    # same positions, two instruments (signals are price-independent except the two momentum features)
    P = load_positions()
    keys = [LONG_ONLY, ECB_RULE, COMPOSITE, COMPOSITE_SCALED, RIDGE_10, LOGIT]
    rows = []
    for k in keys:
        for label, c in [("govt-curve", gov), ("OIS-based", ois)]:
            pnl, pos = daily_pnl(P[k], c)
            m = metrics(pnl, pos, start="2008-01-01", end="2014-06-25")
            rows.append(dict(variant=k, instrument=label, sharpe=m["sharpe"], ann_pnl_bp=m["ann_ret_bp"], maxdd_bp=m["maxdd_bp"], hit=m["hit"]))
    T = pd.DataFrame(rows).pivot(index="variant", columns="instrument", values=["sharpe", "ann_pnl_bp", "maxdd_bp"]).loc[keys]
    print("\n2008-01 to 2014-06, same positions, two instruments:")
    print(T.round(2).to_string())
    T.to_csv(RESULTS / "instrument_comparison_2008_2014.csv")
    pa, _ = daily_pnl(P[COMPOSITE], gov)
    pb, _ = daily_pnl(P[COMPOSITE], ois)
    ma = pa.loc["2008":"2014-06"].resample("ME").sum() * 100
    mb = pb.loc["2008":"2014-06"].resample("ME").sum() * 100
    print(f"\ncomposite monthly P&L: corr between instruments {ma.corr(mb):.2f}, mean abs difference {(ma - mb).abs().mean():.1f} bp/month, "
          f"sd of monthly P&L {ma.std():.1f} bp")


if __name__ == "__main__":
    main()
