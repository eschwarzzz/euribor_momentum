"""Readers for the files in data/raw, data/processed and results.

Every module goes through these so that file names and parsing conventions live in one place.
"""
import numpy as np
import pandas as pd

from .config import PROCESSED, RAW, RESULTS


def read_ecb_series(name):
    """One ECB Data Portal series saved by ``fetch_ecb`` as data/raw/ecb_<name>.csv (date,value).

    Monthly periods (YYYY-MM) are stamped at month-end, ISO weeks (YYYY-Www) at the Friday of that week.
    """
    df = pd.read_csv(RAW / f"ecb_{name}.csv")
    values = pd.to_numeric(df["value"], errors="coerce")
    period = df["date"].astype(str)
    if period.str.len().max() == 7:
        values.index = pd.PeriodIndex(period, freq="M").to_timestamp(how="end").normalize()
    elif "W" in period.iloc[0]:
        values.index = pd.to_datetime(period + "-5", format="%G-W%V-%u")
    else:
        values.index = pd.to_datetime(period)
    return values.dropna().sort_index()


def load_cash_rate():
    """Overnight euro rate in percent: EONIA until €STR starts on 1 October 2019, €STR from then on."""
    eonia, estr = read_ecb_series("eonia"), read_ecb_series("estr")
    return pd.concat([eonia.loc[:estr.index[0] - pd.Timedelta(days=1)], estr])


def read_monthly_csv(name, column=None):
    """Eurostat-style monthly file (date column YYYY-MM) stamped at month-end."""
    df = pd.read_csv(RAW / name)
    df.index = pd.PeriodIndex(df["date"], freq="M").to_timestamp(how="end").normalize()
    if column is None:
        return df
    return pd.to_numeric(df[column], errors="coerce")


def read_fred(series_id):
    df = pd.read_csv(RAW / f"fred_{series_id}.csv")
    df.columns = ["date", "value"]
    values = pd.to_numeric(df["value"], errors="coerce")
    values.index = pd.to_datetime(df["date"])
    return values.dropna()


def load_euribor_daily():
    """Bundesbank daily Euribor fixings, columns 1w, 1m, 3m, 6m, 9m, 12m (percent)."""
    return pd.read_csv(RAW / "euribor_daily.csv", index_col=0, parse_dates=True)


def load_continuous(ois=False):
    """Continuous synthetic futures: px/chg/dte/exp for ranks 0 (front), 1 (2nd) and 2 (3rd).

    ``ois=True`` returns the series that uses the EONIA-swap construction where it exists (2005-06 to 2014-06).
    """
    name = "euribor_futures_continuous_ois.csv" if ois else "euribor_futures_continuous.csv"
    return pd.read_csv(PROCESSED / name, index_col=0, parse_dates=True)


def load_features():
    """Monthly feature matrix F and the two targets: y (2nd contract) and y0 (front contract), next-month price change."""
    F = pd.read_csv(PROCESSED / "features_monthly.csv", index_col=0, parse_dates=True)
    y = F.pop("y_next")
    y0 = F.pop("y0_next")
    return F, y, y0


def load_positions():
    """Month-end positions of every backtest variant (results/monthly_positions.csv)."""
    return pd.read_csv(RESULTS / "monthly_positions.csv", index_col=0, parse_dates=True)


def load_group_scores():
    """Prior-sign group scores R, M, I, S (results/prior_group_scores.csv)."""
    return pd.read_csv(RESULTS / "prior_group_scores.csv", index_col=0, parse_dates=True)


def load_pnl_curves():
    """Daily one-contract P&L of every variant (results/daily_pnl_curves.csv)."""
    return pd.read_csv(RESULTS / "daily_pnl_curves.csv", index_col=0, parse_dates=True)


def load_results_table():
    return pd.read_csv(RESULTS / "results_main.csv", index_col=0)


def core_feature_columns(F):
    """The feature set the main models use: groups R, M, D, I, S without private loans, the TIC (US Treasury) block and
    the MRO change, which feeds the anchor only."""
    return [c for c in F.columns if c[0] in "rmdis" and c not in ("m_loans_yoy", "r_mro_chg3") and not c.startswith("d_tic")]


def sharpe_monthly(x):
    """Annualised Sharpe ratio of a monthly series; NaN when the series is constant."""
    if x.std() == 0:
        return np.nan
    return x.mean() / x.std() * np.sqrt(12)


def sharpe_daily(x):
    return x.mean() / x.std() * np.sqrt(252)
