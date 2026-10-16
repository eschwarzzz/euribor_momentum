"""Synthetic three-month Euribor futures (quarterly IMM contracts), daily prices.

No free source of ICE Euribor futures history exists, so the contract is priced from public curves.
For the contract expiring at IMM date T, t1 days ahead:

    F_t(T) = Euribor3M_t + [ f(t1, t1 + 91) - f(0, 91) ]

that is, spot 3M Euribor plus the risk-free forward premium read off a reference curve, with money-market
forwards from log-linear discount-factor interpolation. Price = 100 - F. At expiry the price is exactly
100 - 3M Euribor.

Reference curve, in order of preference for each day:

* ``ois``: the EONIA swap curve (Bundesbank, 2005-06 to 2014-06), when all of 1M/3M/6M/12M are present;
* ``gov``: the ECB AAA government zero curve (3M, 6M, 1Y; from 2004-09-06);
* ``dep``: the Euribor deposit curve itself (1W to 12M), only before the government curve starts.

Why not the deposit curve throughout: after 2008 the 6M and 12M deposit rates carry a larger credit and
liquidity premium than the 3M tenor, so a single-curve forward overstates the expected 3M rate and every
contract "converges" upward into expiry, an artificial drift of tens of bp a year (long-only Sharpe above 6
in 2013-19). Before September 2004 that tenor basis was 1-3 bp, so the deposit-curve fallback is harmless.
"""
import numpy as np
import pandas as pd

from .config import PROCESSED, RAW
from .data import load_euribor_daily

DEPOSIT_TENOR_DAYS = {"1w": 7, "1m": 30, "3m": 91, "6m": 182, "9m": 273, "12m": 365}
GOV_TENOR_DAYS = {"g3m": 91, "g6m": 182, "g1y": 365}
OIS_TENOR_DAYS = {"1w": 7, "1m": 30, "3m": 91, "6m": 182, "12m": 365}
CONTRACT_DAYS = 91
MAX_HORIZON_DAYS = 365          # the curves only reach one year, so only contracts settling inside it are priced
RANKS = (0, 1, 2)               # front, 2nd and 3rd quarterly contract


def imm_dates(start, end):
    """Third Wednesday of March, June, September and December between ``start`` and ``end`` plus ~13 months."""
    out = []
    for year in range(start.year, end.year + 2):
        for month in (3, 6, 9, 12):
            first = pd.Timestamp(year, month, 1)
            first_wednesday = first + pd.DateOffset(days=int((2 - first.dayofweek) % 7))
            out.append(first_wednesday + pd.DateOffset(days=14))
    return [d for d in out if start <= d <= end + pd.DateOffset(days=400)]


def money_market_forward(days, log_df, t1, t2):
    """Simple forward rate (percent, ACT/360) between day t1 and day t2 from a log-discount-factor curve."""
    l1 = np.interp(t1, days, log_df)
    l2 = np.interp(t2, days, log_df)
    return (np.exp(l1 - l2) - 1.0) * 360.0 / (t2 - t1) * 100.0


def _money_market_curve(row, tenor_days):
    """Log discount factors from simple money-market rates (deposit or OIS quotes)."""
    days, log_df = [0.0], [0.0]
    for tenor, n in tenor_days.items():
        rate = row.get(tenor, np.nan)
        if pd.notna(rate):
            days.append(float(n))
            log_df.append(-np.log1p(rate / 100.0 * n / 360.0))
    return np.array(days), np.array(log_df)


def deposit_curve(row):
    return _money_market_curve(row, DEPOSIT_TENOR_DAYS)


def ois_curve(row):
    return _money_market_curve(row, OIS_TENOR_DAYS)


def government_curve(row):
    """Log discount factors from the ECB annually compounded spot rates."""
    days, log_df = [0.0], [0.0]
    for tenor, n in GOV_TENOR_DAYS.items():
        rate = row.get(tenor, np.nan)
        if pd.notna(rate):
            days.append(float(n))
            log_df.append(-n / 365.0 * np.log1p(rate / 100.0))
    return np.array(days), np.array(log_df)


def build_contracts(euribor, gov, ois=None):
    """Price the three nearest quarterly contracts on every day in ``euribor``.

    Returns a long frame with columns date, rank, expiry, dte (days to expiry), price, method.
    """
    expiries = imm_dates(euribor.index.min(), euribor.index.max())
    records = []
    for day, row in euribor.iterrows():
        ois_row = ois.loc[day] if (ois is not None and day in ois.index) else None
        use_ois = ois_row is not None and ois_row[["1m", "3m", "6m", "12m"]].notna().all()
        gov_row = gov.loc[day] if day in gov.index else None
        use_gov = (not use_ois) and gov_row is not None and gov_row.notna().all()
        if use_ois:
            days, log_df = ois_curve(ois_row)
            method = "ois"
        elif use_gov:
            days, log_df = government_curve(gov_row)
            method = "gov"
        else:
            days, log_df = deposit_curve(row)
            method = "dep"
        spot_forward = money_market_forward(days, log_df, 0, CONTRACT_DAYS)
        spot_3m = row["3m"]
        for rank, expiry in enumerate([d for d in expiries if d >= day][:len(RANKS)]):
            t1 = (expiry - day).days
            t2 = t1 + CONTRACT_DAYS
            if t2 > MAX_HORIZON_DAYS:
                continue
            if t1 == 0:
                rate = spot_3m
            elif method == "dep":
                rate = money_market_forward(days, log_df, t1, t2)
            else:
                rate = spot_3m + money_market_forward(days, log_df, t1, t2) - spot_forward
            records.append((day, rank, expiry, t1, 100.0 - rate, method))
    return pd.DataFrame(records, columns=["date", "rank", "expiry", "dte", "price", "method"])


def continuous_series(contracts):
    """Constant-rank continuous series: price, same-contract daily change, days to expiry and expiry per rank.

    On the day the front contract expires, rank k becomes yesterday's rank k+1, so the change on that day is
    taken against yesterday's rank k+1 price (a roll with no price jump).
    """
    out = {}
    for rank in RANKS:
        s = contracts[contracts["rank"] == rank].set_index("date")
        same_contract = s["expiry"] == s["expiry"].shift(1)
        change = (s["price"] - s["price"].shift(1)).where(same_contract)
        if rank < max(RANKS):
            deferred = contracts[contracts["rank"] == rank + 1].set_index("date")
            for day in s.index[~same_contract & (np.arange(len(s)) > 0)]:
                previous = s.index[s.index.get_loc(day) - 1]
                if previous in deferred.index and deferred.loc[previous, "expiry"] == s.loc[day, "expiry"]:
                    change.loc[day] = s.loc[day, "price"] - deferred.loc[previous, "price"]
        out[f"px{rank}"] = s["price"]
        out[f"chg{rank}"] = change
        out[f"dte{rank}"] = s["dte"]
        out[f"exp{rank}"] = s["expiry"]
    return pd.DataFrame(out)


def _align_curve(curve, index):
    """Reindex a curve to the Euribor calendar, bridging isolated holidays with up to five days of carry."""
    return curve.reindex(curve.index.union(index)).sort_index().ffill(limit=5).reindex(index)


def load_government_curve(index):
    gov = pd.DataFrame({
        name: pd.read_csv(RAW / f"ecb_yc_aaa_{tenor}.csv", index_col=0, parse_dates=True)["value"]
        for name, tenor in [("g3m", "3m"), ("g6m", "6m"), ("g1y", "1y")]
    })
    return _align_curve(gov, index)


def load_ois_curve(index):
    path = RAW / "eonia_swap_daily.csv"
    if not path.exists():
        return None
    ois = pd.read_csv(path, index_col=0, parse_dates=True)
    return _align_curve(ois, index)


def diagnostics(contracts, cont, euribor):
    """Print the checks that caught the deposit-curve drift: convergence at expiry, drift by period, futures minus spot."""
    print(contracts.groupby(["rank", "method"]).agg(n=("price", "size"), first=("date", "min"), last=("date", "max")))
    print(cont[["px0", "px1", "px2"]].describe().T[["count", "mean", "std", "min", "max"]])
    at_expiry = contracts[(contracts["rank"] == 0) & (contracts["dte"] == 0)].merge(euribor[["3m"]], left_on="date", right_index=True)
    print("expiry convergence max err:", (at_expiry["price"] - (100 - at_expiry["3m"])).abs().max())
    for a, b in [("2000", "2004"), ("2005", "2007"), ("2008", "2012"), ("2013", "2019"), ("2020", "2021"), ("2022", "2026")]:
        c = cont.loc[a:b, "chg1"].dropna()
        print(f"{a}-{b}: long rank-1 drift {c.mean() * 252 * 100:6.1f} bp/yr, vol {c.std() * np.sqrt(252) * 100:6.1f} bp, "
              f"SR {c.mean() / c.std() * np.sqrt(252):5.2f}")
    second = contracts[contracts["rank"] == 1].merge(euribor[["3m"]], left_on="date", right_index=True)
    second["fut_minus_spot"] = (100 - second["price"]) - second["3m"]
    print("2nd contract implied rate minus spot 3M Euribor, yearly mean (pct):")
    print(second.groupby(second["date"].dt.year)["fut_minus_spot"].mean().round(3).to_string())


def main():
    euribor = load_euribor_daily()
    gov = load_government_curve(euribor.index)
    contracts = build_contracts(euribor, gov)
    contracts.to_csv(PROCESSED / "synthetic_euribor_futures.csv", index=False)
    cont = continuous_series(contracts)
    cont.to_csv(PROCESSED / "euribor_futures_continuous.csv")
    ois = load_ois_curve(euribor.index)
    if ois is not None:
        contracts_ois = build_contracts(euribor, gov, ois)
        contracts_ois.to_csv(PROCESSED / "synthetic_euribor_futures_ois.csv", index=False)
        continuous_series(contracts_ois).to_csv(PROCESSED / "euribor_futures_continuous_ois.csv")
        print("OIS-based instrument:")
        print(contracts_ois.groupby(["rank", "method"]).agg(n=("price", "size"), first=("date", "min"), last=("date", "max")))
    diagnostics(contracts, cont, euribor)


if __name__ == "__main__":
    main()
