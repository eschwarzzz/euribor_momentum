"""Position rules: ECB rate momentum, the prior-sign macro composite, and the anchored override that is the frozen spec."""
import numpy as np
import pandas as pd

from .config import ANCHOR_THRESHOLD_GRID, OVERRIDE_THRESHOLD, RISK_GROUPS, SCORE_INPUTS, THRESHOLD_PICK_START
from .features import PRIOR


def follow_the_ecb(F):
    """Long if the policy rates were cut in the last three months, short if raised, else keep the previous position.

    Reads the sum of the MRO and deposit-rate changes, so a corridor change that moves only one of them (9 October
    2008 put the DFR back to its July level the day after a 50 bp cut) does not hide the cut.
    """
    return (-np.sign(F["r_mro_chg3"] + F["r_dfr_chg3"])).replace(0, np.nan).ffill()


def follow_the_ecb_dfr(F):
    """The v1 anchor: the same rule on the deposit facility rate alone."""
    return (-np.sign(F["r_dfr_chg3"])).replace(0, np.nan).ffill()


def signed_zscores(F, cols, window=None):
    """Clipped z-scores times their theory sign, for the columns that have one.

    Z-scores use an expanding window (at least 36 months) unless ``window`` gives a rolling length.
    """
    z = pd.DataFrame(index=F.index)
    for c in cols:
        if PRIOR.get(c, 0) == 0:
            continue
        s = F[c]
        if window:
            mean, sd = s.rolling(window, min_periods=36).mean(), s.rolling(window, min_periods=36).std()
        else:
            mean, sd = s.expanding(36).mean(), s.expanding(36).std()
        z[c] = ((s - mean) / sd).clip(-3, 3) * PRIOR[c]
    return z


def factor_score(F, cols=SCORE_INPUTS):
    """The v2 risk-factor score: flat mean of the inputs' signed z-scores, so each input weighs the same."""
    return signed_zscores(F, cols).mean(axis=1, skipna=False)


def prior_composite(F, cols, groups=("R", "M", "I", "S"), window=None):
    """Mean of clipped z-scores times their theory sign, averaged within each group and then across groups.

    Returns the composite score and the frame of group scores.
    """
    z = signed_zscores(F, [c for c in cols if c[0].upper() in groups], window)
    group_scores = pd.DataFrame({
        g: z[[c for c in z.columns if c[0].upper() == g]].mean(axis=1)
        for g in groups if any(c[0].upper() == g for c in z.columns)
    })
    return group_scores.mean(axis=1), group_scores


def risk_score(group_scores, groups=RISK_GROUPS):
    """The v1 risk-factor score: mean of the rates, inflation and sentiment group scores."""
    return group_scores[list(groups)].mean(axis=1)


def override(anchor, score, tau=OVERRIDE_THRESHOLD):
    """Hold the anchor position unless |score| > tau, in which case take sign(score)."""
    return pd.Series(np.where(score.abs() > tau, np.sign(score), anchor), index=anchor.index)


def frozen_spec(anchor, score):
    return override(anchor, score, OVERRIDE_THRESHOLD)


def pick_threshold(unit_pnl, taus, start, end, metrics):
    """Threshold with the highest one-contract Sharpe over [start, end]; ties go to the largest threshold."""
    sharpe = pd.Series({t: metrics(*unit_pnl[t], start=start, end=end)["sharpe"] for t in taus})
    best = sharpe.max()
    return max(t for t, v in sharpe.items() if abs(v - best) < 1e-9)


def walk_forward_threshold(anchor, score, cont, years, taus=ANCHOR_THRESHOLD_GRID, before=None,
                           pick_start=THRESHOLD_PICK_START, cost=None):
    """Re-pick the override threshold every December on all data from ``pick_start`` to that date, apply it next year.

    ``before`` fills the years ahead of the first walk-forward year (None leaves them NaN, i.e. flat).
    Returns the position series and the dict year -> threshold.
    """
    from .backtest import daily_pnl, metrics  # local import: backtest depends on this module's rules

    kwargs = {} if cost is None else {"cost": cost}
    unit_pnl = {t: daily_pnl(override(anchor, score, t), cont, **kwargs) for t in taus}
    positions = anchor.copy() if before is not None else pd.Series(np.nan, index=anchor.index)
    tau_path = {}
    for year in years:
        tau_path[year] = pick_threshold(unit_pnl, taus, pick_start, f"{year - 1}-12-31", metrics)
        in_year = anchor.index.year == year
        positions[in_year] = override(anchor, score, tau_path[year])[in_year]
    return positions, tau_path
