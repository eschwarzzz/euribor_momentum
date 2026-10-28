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

# The frozen specification, v2 (28 October 2026, after the 18 October review, fixed before any test): ECB rate momentum
# on both policy rates as the anchor, overridden by a five-input risk-factor score; the account holds a fixed risk per euro.
SCORE_INPUTS = ("r_dfr_chg3", "i_hicp", "i_core", "i_unemp_chg6", "s_ciss")   # policy persistence, mandate, persistence, slack, stress
OVERRIDE_THRESHOLD = 0.5
SIZING_VOL_END = "2007-12-31"    # account size = 10% of equity at the average 60-day volatility up to here (1999-2007, 49 bp/yr)
# v1 (September 2026), kept for comparison: deposit-rate anchor, 23-series R+I+S group score, 10% volatility target
RISK_GROUPS = ("R", "I", "S")
ANCHOR_THRESHOLD_GRID = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.25, 1.5]
THRESHOLD_PICK_START = "2002-01-31"   # the walk-forward threshold is re-picked each December on data from here
N_TRIALS_TOTAL = 105             # looks at this sample: about 100 counted by the review, plus the v2 choices and their checks

# Variant names used as keys in results/results_main.csv and results/monthly_positions.csv
ECB_RULE = "BM follow-the-ECB (-sign of MRO+DFR 3M change)"
ECB_RULE_DFR = "BM follow-the-ECB, DFR only (v1 anchor)"
SPEC = "Frozen spec v2: both-rates anchor + 5-input override"
SPEC_V1 = "Spec v1: DFR anchor + 23-series R+I+S override"
SPEC_V1_BOTH = "Spec v1 score on the both-rates anchor"
SCORE5 = "Five-input score alone, sign"
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
