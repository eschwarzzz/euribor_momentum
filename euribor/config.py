"""Paths, contract conventions and evaluation windows shared by every module."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
LOGS = RESULTS / "logs"

# Contract conventions: three-month Euribor future, price = 100 - rate
POINT_VALUE_EUR = 2_500.0        # EUR per full price point (EUR 25 per basis point)
TICK_COST = 0.005                # price points per side in the one-contract backtests (half a bp, about one tick)
ACCOUNT_COST_BP = 0.3            # bp per side in the account backtest: half a one-tick spread plus fees on ICE
INITIAL_MARGIN_EUR = 237.0       # initial margin per contract, broker quote September 2026

# Evaluation windows
OOS_START = "2008-01-31"         # first month-end whose next-month P&L counts (one-contract backtests)
OOS_END = "2026-08-31"
ACCOUNT_START = "2008-01-01"     # the account opens on 1 January 2008
ACCOUNT_START_5Y = "2021-09-01"  # the fresh last-five-years account
MIN_TRAIN_MONTHS = 72
SUBPERIODS = {
    "2008-12 crisis": ("2008-01-01", "2012-12-31"),
    "2013-19 ZLB/QE": ("2013-01-01", "2019-12-31"),
    "2020-21 COVID": ("2020-01-01", "2021-12-31"),
    "2022-26 hikes+cuts": ("2022-01-01", OOS_END),
}

# The frozen specification: ECB rate momentum as the anchor, overridden by the R+I+S risk-factor score
RISK_GROUPS = ("R", "I", "S")
OVERRIDE_THRESHOLD = 0.5
ANCHOR_THRESHOLD_GRID = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.25, 1.5]
THRESHOLD_PICK_START = "2002-01-31"   # the walk-forward threshold is re-picked each December on data from here

# Variant names used as keys in results/results_main.csv and results/monthly_positions.csv
ECB_RULE = "BM follow-the-ECB (-sign of DFR 3M change)"
LONG_ONLY = "BM long-only 2nd contract"
TREND_12M = "BM trend 12M"
TREND_3M = "BM trend 3M (sign of 3M price change)"
COMPOSITE = "Prior composite, sign (R+M+I+S)"
COMPOSITE_SCALED = "Prior composite, scaled (clip +/-2)"
RIDGE_10 = "Ridge all factors (a=10), sign"
RIDGE_100 = "Ridge all factors (a=100), sign"
LOGIT = "Logit direction (C=0.1), sign"
PLACEBO = "PLACEBO ridge on shuffled target"


def ensure_dirs():
    for d in (RAW, PROCESSED, RESULTS, FIGURES, LOGS):
        d.mkdir(parents=True, exist_ok=True)
