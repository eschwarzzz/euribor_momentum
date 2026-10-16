"""Override threshold: train/test split, reverse split and walk-forward selection, plus signal statistics.

The threshold 0.5 of the frozen specification was chosen on this grid; this script shows it is chosen on either
half of the sample and what a walk-forward choice would have earned.
"""
import warnings

import numpy as np
import pandas as pd

from euribor.backtest import daily_pnl, metrics
from euribor.config import ANCHOR_THRESHOLD_GRID, ECB_RULE, RESULTS, SUBPERIODS
from euribor.data import load_continuous, load_features, load_group_scores, load_positions
from euribor.signals import override, risk_score, walk_forward_threshold

warnings.filterwarnings("ignore")
TAUS = [0.0] + ANCHOR_THRESHOLD_GRID + [99.0]          # 0 = composite only, 99 = rule only (never override)
TRAIN, TEST, FULL = ("2002-01-31", "2013-12-31"), ("2014-01-01", "2026-08-31"), ("2008-01-31", "2026-08-31")


def main():
    pd.set_option("display.width", 200)
    F, _, _ = load_features()
    cont = load_continuous()
    ecb = load_positions()[ECB_RULE]
    score = risk_score(load_group_scores())
    cache = {t: daily_pnl(override(ecb, score, t), cont) for t in TAUS}

    def sharpe(t, a, b):
        return metrics(*cache[t], start=a, end=b)["sharpe"]

    def fired(t, a, b):
        return int(((score.abs() > t) & (np.sign(score) != ecb)).loc[a:b].sum())

    labels = [("composite only" if t == 0 else "rule only" if t == 99 else t) for t in TAUS]
    grid = pd.DataFrame({"train 2002-13": [sharpe(t, *TRAIN) for t in TAUS], "test 2014-26": [sharpe(t, *TEST) for t in TAUS],
                         "2008-26 (report window)": [sharpe(t, *FULL) for t in TAUS], "override months (test)": [fired(t, *TEST) for t in TAUS]},
                        index=labels)
    print("[A] Sharpe by threshold (rows 'composite only' = tau 0, 'rule only' = never override):")
    print(grid.round(2).to_string())

    def pick(a, b):
        s = pd.Series({t: sharpe(t, a, b) for t in ANCHOR_THRESHOLD_GRID})
        return max(t for t, v in s.items() if abs(v - s.max()) < 1e-9)

    t_fwd, t_rev = pick(*TRAIN), pick(*TEST)
    print(f"\n[B] Forward split: tau chosen on {TRAIN[0][:4]}-{TRAIN[1][:4]} = {t_fwd}  -> test {TEST[0][:4]}-{TEST[1][:4]} Sharpe {sharpe(t_fwd, *TEST):+.2f}"
          f"  (rule only {sharpe(99, *TEST):+.2f}, composite only {sharpe(0, *TEST):+.2f})")
    print(f"    Reverse split: tau chosen on {TEST[0][:4]}-{TEST[1][:4]} = {t_rev}  -> test {TRAIN[0][:4]}-{TRAIN[1][:4]} Sharpe {sharpe(t_rev, *TRAIN):+.2f}"
          f"  (rule only {sharpe(99, *TRAIN):+.2f}, composite only {sharpe(0, *TRAIN):+.2f})")

    pos_wf, chosen = walk_forward_threshold(ecb, score, cont, years=range(2008, 2027))
    pnl_wf, pos_d = daily_pnl(pos_wf, cont)
    mw = metrics(pnl_wf, pos_d, *FULL)
    print(f"\n[C] Walk-forward tau (re-chosen every year on 2002..t-1, minimum 6 years): OOS 2008-26 Sharpe {mw['sharpe']:+.2f}, "
          f"ann P&L {mw['ann_ret_bp']:+.0f} bp, max DD {mw['maxdd_bp']:.0f} bp")
    print("    tau path:", chosen)
    print("    sub-periods:", {k[:7]: round(metrics(pnl_wf, pos_d, start=a, end=b)["sharpe"], 2) for k, (a, b) in SUBPERIODS.items()})
    print("    reference, rule only:", {k[:7]: round(sharpe(99, a, b), 2) for k, (a, b) in SUBPERIODS.items()})
    pd.DataFrame({"pos": pos_wf}).to_csv(RESULTS / "anchored_walkforward_positions.csv")
    grid.to_csv(RESULTS / "threshold_grid.csv")

    s = score.loc["2002-01-31":]
    sign = np.sign(s)
    run_length = sign.groupby((sign != sign.shift()).cumsum()).size()
    crossings = ((s.abs() > 0.5) != (s.abs() > 0.5).shift()).sum() / (len(s) / 12)
    print(f"\n[D] Signal (R+I+S mean of clipped z-scores), 2002-2026: monthly autocorrelation {s.autocorr(1):.2f} (3-month {s.autocorr(3):.2f}), "
          f"sd {s.std():.2f}, share of months |score|>0.5: {(s.abs() > 0.5).mean():.0%}, sign flips per year {(sign != sign.shift()).sum() / (len(s) / 12):.1f}, "
          f"median sign run {run_length.median():.0f} months, band crossings (0.5) per year {crossings:.1f}")
    G = load_group_scores()
    print("    group score sd / autocorr:", {g: (round(G[g].loc["2002":].std(), 2), round(G[g].loc["2002":].autocorr(1), 2)) for g in "RIS"})


if __name__ == "__main__":
    main()
