"""Override threshold: train/optimise/test split, reverse split, and walk-forward selection. Signal statistics."""
import numpy as np, pandas as pd, os, sys, warnings
warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT); D = f"{ROOT}/data"; R = f"{ROOT}/results"
from backtest import daily_pnl, metrics, SUBS
F = pd.read_csv(f"{D}/features_monthly.csv", index_col=0, parse_dates=True); y = F["y_next"] * 100; idx = F.index
cont = pd.read_csv(f"{D}/euribor_futures_continuous.csv", index_col=0, parse_dates=True)
P = pd.read_csv(f"{R}/monthly_positions.csv", index_col=0, parse_dates=True); G = pd.read_csv(f"{R}/prior_group_scores.csv", index_col=0, parse_dates=True)
ecb = P["BM follow-the-ECB (-sign of DFR 3M change)"]; score = G[["R", "I", "S"]].mean(axis=1)
TAUS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.25, 1.5, 99.0]
def anchored(tau): return pd.Series(np.where(score.abs() > tau, np.sign(score), ecb), index=idx)
cache = {t: daily_pnl(anchored(t), cont) for t in TAUS}
def sr(t, a, b): return metrics(*cache[t], start=a, end=b)["sharpe"]
TRAIN = ("2002-01-31", "2013-12-31"); TEST = ("2014-01-01", "2026-08-31"); FULL = ("2008-01-31", "2026-08-31")
grid = pd.DataFrame({"train 2002-13": [sr(t, *TRAIN) for t in TAUS], "test 2014-26": [sr(t, *TEST) for t in TAUS], "2008-26 (report window)": [sr(t, *FULL) for t in TAUS],
                     "override months (test)": [int(((score.abs() > t) & (np.sign(score) != ecb)).loc[TEST[0]:TEST[1]].sum()) for t in TAUS]}, index=[("composite only" if t == 0 else "rule only" if t == 99 else t) for t in TAUS])
pd.set_option("display.width", 200); print("[A] Sharpe by threshold (rows 'composite only' = tau 0, 'rule only' = never override):"); print(grid.round(2).to_string())
def pick(a, b):
    s = pd.Series({t: sr(t, a, b) for t in TAUS if t not in (0.0, 99.0)}); best = s.max(); return max(t for t, v in s.items() if abs(v - best) < 1e-9)
t_fwd = pick(*TRAIN); t_rev = pick(*TEST)
print(f"\n[B] Forward split: tau chosen on {TRAIN[0][:4]}-{TRAIN[1][:4]} = {t_fwd}  -> test {TEST[0][:4]}-{TEST[1][:4]} Sharpe {sr(t_fwd, *TEST):+.2f}  (rule only {sr(99, *TEST):+.2f}, composite only {sr(0, *TEST):+.2f})")
print(f"    Reverse split: tau chosen on {TEST[0][:4]}-{TEST[1][:4]} = {t_rev}  -> test {TRAIN[0][:4]}-{TRAIN[1][:4]} Sharpe {sr(t_rev, *TRAIN):+.2f}  (rule only {sr(99, *TRAIN):+.2f}, composite only {sr(0, *TRAIN):+.2f})")
# ---- walk-forward threshold selection: re-pick each December using all data from 2002 to that date, apply next year ----
pos_wf = ecb.copy() * np.nan; chosen = {}
for yr in range(2008, 2027):
    t_star = pick("2002-01-31", f"{yr-1}-12-31"); chosen[yr] = t_star
    m = (idx.year == yr); pos_wf[m] = anchored(t_star)[m]
pnl_wf, pd_wf = daily_pnl(pos_wf, cont); mw = metrics(pnl_wf, pd_wf, *FULL)
print(f"\n[C] Walk-forward tau (re-chosen every year on 2002..t-1, minimum 6 years): OOS 2008-26 Sharpe {mw['sharpe']:+.2f}, ann P&L {mw['ann_ret_bp']:+.0f} bp, max DD {mw['maxdd_bp']:.0f} bp")
print("    tau path:", chosen)
print("    sub-periods:", {k[:7]: round(metrics(pnl_wf, pd_wf, start=a, end=b)["sharpe"], 2) for k, (a, b) in SUBS.items()})
print("    reference, rule only:", {k[:7]: round(sr(99, a, b), 2) for k, (a, b) in SUBS.items()})
pd.DataFrame({"pos": pos_wf}).to_csv(f"{R}/anchored_walkforward_positions.csv"); grid.to_csv(f"{R}/threshold_grid.csv")
# ---- signal statistics ----
s = score.loc["2002-01-31":]; sgn = np.sign(s); runs = (sgn != sgn.shift()).cumsum(); runlen = sgn.groupby(runs).size()
cross = ((s.abs() > 0.5) != (s.abs() > 0.5).shift()).sum() / (len(s) / 12)
print(f"\n[D] Signal (R+I+S mean of clipped z-scores), 2002-2026: monthly autocorrelation {s.autocorr(1):.2f} (3-month {s.autocorr(3):.2f}), sd {s.std():.2f}, share of months |score|>0.5: {(s.abs()>0.5).mean():.0%}, "
      f"sign flips per year {(sgn != sgn.shift()).sum()/(len(s)/12):.1f}, median sign run {runlen.median():.0f} months, band crossings (0.5) per year {cross:.1f}")
print("    group score sd / autocorr:", {g: (round(G[g].loc['2002':].std(), 2), round(G[g].loc['2002':].autocorr(1), 2)) for g in "RIS"})
