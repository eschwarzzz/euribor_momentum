"""Write BACKTEST_50K.md (main six-section report) and BACKTEST_50K_APPENDIX.md (A: last five years, B: trend-book correlation)
from the files that backtest_50k.py, make_bt50k_charts.py and portfolio_correlation.py leave in results/. Rerun after any of them."""
import numpy as np, pandas as pd, json, os, sys, datetime as dt
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT); D = f"{ROOT}/data"; R = f"{ROOT}/results"
from backtest import daily_pnl, metrics
MINUS = "−"
def sg(x, nd=2): return ("+" if x >= 0 else MINUS) + f"{abs(x):.{nd}f}"            # signed number with a real minus sign
def pc(x, nd=1): return (MINUS if x < 0 else "") + f"{abs(x):.{nd}f}%"
def spc(x, nd=1): return ("+" if x >= 0 else MINUS) + f"{abs(x):.{nd}f}%"
def eur(x, nd=0): return (MINUS if x < 0 else "") + "€" + f"{abs(x):,.{nd}f}"
def seur(x): return ("+" if x >= 0 else MINUS) + "€" + f"{abs(x):,.0f}"
def k(x): return "€" + f"{x/1000:,.0f}k"
def sk(x): return ("+" if x >= 0 else MINUS) + "€" + f"{abs(x)/1000:,.1f}k"
def pv(p, n): return f"0 of {n:,}" if p == 0 else f"{p:.3f}"
def shp(x): return x.mean() / x.std() * np.sqrt(252)
TODAY = dt.date.today().strftime("%-d %B %Y")

# ---------- inputs ----------
S = pd.read_csv(f"{R}/bt50k_variants.csv", index_col=0); YR = pd.read_csv(f"{R}/bt50k_by_year.csv", index_col=0); SUB = pd.read_csv(f"{R}/bt50k_subperiods.csv", index_col=0)
mc = json.load(open(f"{R}/bt50k_mc.json")); d = pd.read_csv(f"{R}/bt50k_daily.csv", index_col=0, parse_dates=True); m = pd.read_csv(f"{R}/bt50k_monthly.csv", index_col=0, parse_dates=True)
S5 = pd.read_csv(f"{R}/bt50k_5y_variants.csv", index_col=0); YR5 = pd.read_csv(f"{R}/bt50k_5y_by_year.csv", index_col=0); SY5 = pd.read_csv(f"{R}/bt50k_5y_sharpe_by_year.csv", index_col=0)
mc5 = json.load(open(f"{R}/bt50k_5y_mc.json")); d5 = pd.read_csv(f"{R}/bt50k_5y_daily.csv", index_col=0, parse_dates=True); m5 = pd.read_csv(f"{R}/bt50k_5y_monthly.csv", index_col=0, parse_dates=True)
CB = mc["cost_bp"]; CPS = CB * 25; FZ = "Frozen spec, 10% vol target"; WF = "Walk-forward threshold, 10% vol"; EC = "Follow-the-ECB only, 10% vol"; LO = "Long-only, 10% vol"; TR = "12M trend, 10% vol"
F = pd.read_csv(f"{D}/features_monthly.csv", index_col=0, parse_dates=True); cont = pd.read_csv(f"{D}/euribor_futures_continuous.csv", index_col=0, parse_dates=True)
P = pd.read_csv(f"{R}/monthly_positions.csv", index_col=0, parse_dates=True); G = pd.read_csv(f"{R}/prior_group_scores.csv", index_col=0, parse_dates=True)
ecb = P["BM follow-the-ECB (-sign of DFR 3M change)"]; score = G[["R", "I", "S"]].mean(axis=1); frozen = pd.Series(np.where(score.abs() > 0.5, np.sign(score), ecb), index=F.index)
tau = {int(k_): v for k_, v in mc["tau_path"].items()}; pos_wf = pd.Series(np.where(score.abs() > pd.Series(F.index.year.map(lambda y: tau.get(y, 0.5)), index=F.index), np.sign(score), ecb), index=F.index)
u_old = metrics(*daily_pnl(frozen, cont, cost=0.005), start="2008-01-31", end="2026-08-31")["sharpe"]; u_new = mc["unit_check"]["sharpe"]
u_wf = metrics(*daily_pnl(pos_wf, cont, cost=CB / 100), start="2008-01-01", end="2026-08-31")["sharpe"]; u_ecb = metrics(*daily_pnl(ecb, cont, cost=CB / 100), start="2008-01-01", end="2026-08-31")["sharpe"]

# ---------- derived figures, main window ----------
eq = d["equity"]; dds = eq / eq.cummax() - 1; trough = dds.idxmin(); peak = eq.loc[:trough].idxmax(); rec = eq.loc[trough:][eq.loc[trough:] >= eq.loc[peak]].index; under = int((dds < 0).astype(int).groupby((dds == 0).cumsum()).sum().max())
ret_m = m["ret"]; wm, bm = ret_m.idxmin() + pd.offsets.MonthEnd(1), ret_m.idxmax() + pd.offsets.MonthEnd(1)       # decision at month-end t -> P&L month is t+1
fees = d["fees"].sum(); gross = d["pnl"].sum() + fees; flips = int((np.sign(m["contracts"]).diff().abs() > 0).sum()); resized = int((m["traded"] > 0).sum())
lr = np.log1p(d["ret"]); share = lambda a, b: lr.loc[a:b].sum() / lr.sum(); tot = m["pnl"].sum(); top5 = m["pnl"].nlargest(5).sum() / tot; top10 = m["pnl"].nlargest(10).sum() / tot
era = {}
for lab, (a, b) in {"2008–12": ("2008", "2012"), "2013–21": ("2013", "2021"), "2022–26": ("2022", "2026")}.items():
    x = d.loc[a:b]; era[lab] = (x["contracts"].abs().mean(), x["margin"].mean(), x["margin_pct"].mean() * 100, x["margin_stress_pct"].max() * 100)
sides_roll = 2 * (m["rolls"] * m["contracts"].abs()).sum(); sides_trade = m["traded"].sum(); yrs = len(m) / 12
big = ret_m[ret_m < -0.12]; big_names = [(t + pd.offsets.MonthEnd(1)).strftime("%B %Y") for t in big.index]
ratio = [cont["chg1"].loc[t + pd.offsets.Day(1):t + pd.offsets.MonthEnd(1)].std() * np.sqrt(252) * 100 / m.loc[t, "sigma_bp"] for t in big.index]
pre22 = m.loc["2021-08-31":"2022-02-28", "contracts"].abs(); jul22 = m.loc["2022-06-30"]
v60 = cont["chg1"].rolling(60).std() * np.sqrt(252); vb = 0.7 * v60 + 0.3 * v60.expanding(250).mean(); vlast = vb.iloc[-1]; vdate = vb.index[-1]
n_new = int(np.round(0.10 * 50000 / (vlast * 2500))); s_aug = score.loc["2026-08-31"]; s_sep = score.loc["2026-09-30"]; dir_now = "short" if frozen.iloc[-1] < 0 else "long"
nl = mc["nulls"]; ds = mc["deflated"]; bs = mc["bootstrap_sharpe"]; bp = mc["bootstrap_pnl"]; sr0_45, sr0_70 = 0.53, 0.57
roll60 = ret_m.rolling(60).apply(lambda x: x.mean() / x.std() * np.sqrt(12))

def row(name, label=None, bold=False, base=None):
    r = S.loc[name]; delta = "n/a" if base is None else ("0" if name == base else sg(r["sharpe"] - S.loc[base, "sharpe"]))
    cells = [label or name, sg(r["sharpe"]), pc(r["cagr_pct"]), pc(r["maxdd_pct"]), eur(r["final_equity"]), delta]
    return "| " + " | ".join(f"**{c}**" if bold else c for c in cells) + " |"
MAIN = [f"""# Euribor macro strategy: €50,000 account backtest

## 1. Hypothesis
The frozen specification earns a positive return on the 2nd quarterly Euribor contract. It has two parts. **ECB rate momentum** sets the default position: long if the deposit facility rate was cut in the last three months, short if it was raised, otherwise the position is kept. **The risk factors** can override it: when the risk-factor score is above +0.5 the position is long, when it is below −0.5 the position is short, whatever the ECB did last. The position is decided at each month-end and held for the next month. This test asks what that edge looks like as a real account: €50,000 of capital, whole contracts, euro costs, margin, and a sizing rule, since the specification itself only says long or short.

**The risk factors.** Three groups of monthly macro series, each turned into a score and averaged into one number:

| Group | What it captures | Series (sign: + argues for a higher futures price, i.e. lower rates) | Publication lag |
|---|---|---|---|
| Rates and policy | where policy and the money-market curve have been moving | deposit rate change over 3 and 6 months (−); 12M minus 3M Euribor slope (+) and its 3-month change (−); 12M Euribor 3-month change (−); 3M Euribor minus the deposit rate (+); 2nd-contract price momentum over 3 and 12 months (+) | none |
| Inflation | whether the ECB has room to ease | headline and core HICP, year on year (−), and their 3-month changes (−); unemployment rate, 6-month change (+) | HICP 1 month, unemployment 2 months |
| Sentiment and stress | financial and political stress that pushes the ECB toward easing | Europe economic policy uncertainty index, level and 3-month change (+); Italy plus Spain minus Germany plus France uncertainty, level and change (+); Italian and Spanish minus German 10-year yield spread, level and change (+); ECB composite systemic stress indicator, level and change (+); economic sentiment indicator, level and change (−) | uncertainty and sentiment 1 month, others none |

Each series is converted to an expanding z-score (at least 36 months of history), clipped to ±3 and multiplied by its sign; the signs were fixed from theory, not fitted. Series are averaged within each group, and the risk-factor score is the mean of the three group scores.

## 2. Benchmark
Long-only, 12-month trend and the plain follow-the-ECB rule, all run through the same account and the same sizing. Window January 2008 to August 2026, 224 months, synthetic 2nd-contract prices. The account starts on 1 January 2008, a month earlier than the earlier reports' 31 January start; that month was a loss, and with the cost change below the frozen spec's one-contract Sharpe goes from {sg(u_old)} (earlier reports) to {sg(u_new)} here.

Account assumptions:

| Item | Setting |
|---|---|
| Capital | €50,000, euro account, cash earns no interest |
| Contract | €2,500 per price point, €25 per basis point |
| Sizing | contracts = round(10% × equity ÷ (σ × €2,500)), set each month-end with the signal |
| σ | 70% trailing 60-day realised volatility + 30% its long-run mean, annualised |
| Costs | {CB} bp per side = €{CPS:.2f} per contract (half a one-tick spread plus exchange, clearing and broker fees); roll = €{2*CPS:.0f} per contract, four times a year |
| Margin | €237 initial margin per contract (broker quote, September 2026), held flat through history |

The 10% volatility target and the volatility blend are my choices, not part of the frozen specification. Section 5 shows what changes with other choices. The {CB} bp cost is a realistic figure for the ICE contract; 0.5 bp (one full tick) is kept as a sensitivity row and is about what Eurex FEU3 would cost.

## 3. Variants
{len(S)} account runs: 5 strategies at the 10% target (frozen, walk-forward threshold, follow-the-ECB, long-only, 12M trend); the frozen spec at 5%, 15% and 20% targets, with unblended 60-day volatility, with 1 and 3 fixed contracts, at 0.5, 1 and 2 bp per side, from a 2002 start, and on the OIS-spliced price series; follow-the-ECB on the OIS-spliced series. No signal parameter was changed or tuned.

## 4. Results

| Variant | Sharpe | CAGR | Max DD | Final equity | Sharpe vs long-only |
|---|---|---|---|---|---|
{row(FZ, bold=True, base=LO)}
{row(WF, base=LO)}
{row(EC, base=LO)}
{row(LO, "Long-only, 10% vol (benchmark)", base=LO)}
{row(TR, "12M trend, 10% vol (benchmark)", base=LO)}
{row("Frozen, 5% vol target", base=LO)}
{row("Frozen, 15% vol target", base=LO)}
{row("Frozen, 20% vol target", base=LO)}
{row("Frozen, 60-day vol only (no long-run blend)", "Frozen, 60-day vol only", base=LO)}
{row("Frozen, fixed 1 contract", base=LO)}
{row("Frozen, fixed 3 contracts", base=LO)}
{row("Frozen, cost 0.5 bp/side", base=LO)}
{row("Frozen, cost 1 bp/side", base=LO)}
{row("Frozen, cost 2 bp/side", base=LO)}
{row("Frozen, start Jan 2002")}
{row("Frozen, OIS-spliced prices 2005-14", "Frozen, OIS-spliced prices 2005–14")}
{row("Follow-the-ECB, OIS-spliced prices")}

Frozen spec, account detail:

| Measure | Value |
|---|---|
| Total P&L | {seur(S.loc[FZ, "pnl_eur"])} on €50,000 |
| Realised volatility | {pc(S.loc[FZ, "vol_pct"])} a year against the 10% target |
| Worst drawdown | {pc(S.loc[FZ, "maxdd_pct"])} ({eur(S.loc[FZ, "maxdd_eur"])} at its deepest in euros), {peak:%b %Y} to {trough:%b %Y}, recovered {rec[0]:%b %Y} |
| Longest time under water | {under} trading days |
| Worst month / best month | {pc(S.loc[FZ, "worst_month_pct"])} ({wm:%b %Y}) / {spc(S.loc[FZ, "best_month_pct"])} ({bm:%b %Y}) |
| Winning months | {S.loc[FZ, "hit_pct"]:.0f}% |
| Contracts held | average {S.loc[FZ, "avg_contracts"]:.1f}, range {int(d["contracts"].abs().min())} to {int(S.loc[FZ, "max_contracts"])} as equity grew and volatility fell |
| Costs paid | {eur(fees)}, about {fees/gross:.0%} of gross profit |
| Direction changes | {flips} in {yrs:.1f} years; position resized in {resized} of {len(m)} months |

Margin deployed (Figure 7, bottom panel):

| Period | Avg contracts | Avg margin | Share of equity | Peak share if margin had scaled with volatility |
|---|---|---|---|---|
""" + "\n".join(f"| {lab} | {v[0]:.1f} | {eur(v[1])} | {pc(v[2])} | {pc(v[3])} |" for lab, v in era.items()) + f"""
| Whole window | {S.loc[FZ, "avg_contracts"]:.1f} | {eur(d["margin"].mean())} | {pc(S.loc[FZ, "avg_margin_pct"])} (peak {pc(S.loc[FZ, "peak_margin_pct"])}) | {pc(S.loc[FZ, "peak_margin_stress_pct"])} |

Calendar years, frozen spec:

| Year | P&L € | Return | Year-end equity | Avg contracts (+ long, − short) |
|---|---|---|---|---|
""" + "\n".join(f"| {y if y != 2026 else '2026 (to Aug)'} | {('+' if r.pnl_eur >= 0 else MINUS)}{abs(r.pnl_eur):,.0f} | {spc(r.ret_pct)} | {r.equity_end:,.0f} | {sg(r.avg_contracts, 1)} |" for y, r in YR.iterrows()) + f"""

![Figure 6. Equity and drawdown, January 2008 to August 2026](results/fig6_bt50k_equity.png)

*Figure 6. Account equity for the four strategies and the frozen spec's drawdown.*

![Figure 7. Signal, volatility, contracts and margin](results/fig7_bt50k_signal_vol_margin.png)

*Figure 7. The signal, the volatility used for sizing, contracts held and margin deployed.*

## 5. Robustness

**Regimes.** The result is regime dependent, not universal.

| Sharpe by period | 2008–12 crisis | 2013–19 ZLB/QE | 2020–21 COVID | 2022–26 hikes + cuts |
|---|---|---|---|---|
""" + "\n".join(f"| {lab} | " + " | ".join(sg(SUB.loc[key_, c]) for c in SUB.columns) + " |" for lab, key_ in [("Frozen spec", FZ), ("Walk-forward threshold", WF), ("Follow-the-ECB", EC), ("Long-only", LO)]) + f"""

{share('2008','2012'):.0%} of the account's growth came in 2008–12, {share('2022','2026'):.0%} in 2022–26 and {share('2013','2021'):.0%} in the nine years 2013–21. The best 5 months are {top5:.0%} of total P&L and the best 10 are {top10:.0%}.

**Monte Carlo, block bootstrap** (12-month blocks, 10,000 paths of 224 months, account returns):

| | Frozen spec | Walk-forward | Follow-the-ECB | Long-only |
|---|---|---|---|---|
| Sharpe, 5th / 50th / 95th percentile | """ + " | ".join(f"{sg(bs[k_]['p05'])} / {sg(bs[k_]['p50'])} / {sg(bs[k_]['p95'])}" for k_ in bs) + f""" |
| P(Sharpe > 0) | """ + " | ".join(f"{bs[k_]['prob_gt0']:.0%}" for k_ in bs) + f""" |
| P(beats long-only) / P(beats ECB rule) | {bs['Frozen spec']['prob_beats_longonly']:.0%} / {bs['Frozen spec']['prob_beats_ecb']:.0%} | {bs['Walk-forward threshold']['prob_beats_longonly']:.0%} / {bs['Walk-forward threshold']['prob_beats_ecb']:.0%} | | |
| Final equity, 5th / 50th / 95th | """ + " | ".join(f"{k(bp[k_]['final_p05'])} / {k(bp[k_]['final_p50'])} / {k(bp[k_]['final_p95'])}" for k_ in bp) + f""" |
| P(ending below €50,000) | """ + " | ".join(f"{bp[k_]['prob_end_below_start']:.1%}" if bp[k_]['prob_end_below_start'] < 0.1 else f"{bp[k_]['prob_end_below_start']:.0%}" for k_ in bp) + f""" |
| Max drawdown, median / 5th / 1st percentile | """ + " | ".join(f"{pc(bp[k_]['maxdd_p50'], 0)} / {pc(bp[k_]['maxdd_p05'], 0)} / {pc(bp[k_]['maxdd_p01'], 0)}" for k_ in bp) + f""" |
| P(drawdown worse than 20% / 30%) | """ + " | ".join(f"{bp[k_]['prob_dd_gt20']:.0%} / {bp[k_]['prob_dd_gt30']:.0%}" for k_ in bp) + f""" |
| First-year P&L, 5th / 50th / 95th | """ + " | ".join(f"{sk(bp[k_]['pnl1y_p05'])} / {sk(bp[k_]['pnl1y_p50'])} / {sk(bp[k_]['pnl1y_p95'])}" for k_ in bp) + f""" |
| P(loss after 1 year / 5 years) | """ + " | ".join(f"{bp[k_]['prob_loss_1y']:.0%} / {bp[k_]['prob_loss_5y']:.0%}" for k_ in bp) + f""" |

**No-skill nulls** (the long/short path shifted or block-shuffled in time, position sizes left on their dates):

| | Observed Sharpe | Null mean | Null 95th pct | p, circular shift | p, block permutation |
|---|---|---|---|---|---|
""" + "\n".join(f"| {k_} | {sg(v['observed'])} | {sg(v['perm_mean'])} | {sg(v['perm_p95'])} | {pv(v['p_shift'], 212)} | {pv(v['p_perm'], 3000)} |" for k_, v in nl.items()) + f"""

**Deflated Sharpe** (expected best-of-N Sharpe under the null: {sr0_45} for 45 trials, {sr0_70} for 70): frozen spec {ds['Frozen spec']['dsr_45']:.2f} / {ds['Frozen spec']['dsr_70']:.2f}, walk-forward threshold {ds['Walk-forward threshold']['dsr_45']:.2f} / {ds['Walk-forward threshold']['dsr_70']:.2f}, follow-the-ECB {ds['Follow-the-ECB']['dsr_45']:.2f} / {ds['Follow-the-ECB']['dsr_70']:.2f}, long-only {ds['Long-only']['dsr_45']:.2f} / {ds['Long-only']['dsr_70']:.2f}. Monthly returns have skew {sg(ds['Frozen spec']['skew'])} and kurtosis {ds['Frozen spec']['kurt']:.1f}.

![Figure 8. Monte Carlo, full window](results/fig8_bt50k_montecarlo.png)

*Figure 8. Bootstrap Sharpe with medians, bootstrap equity paths, bootstrap drawdown, and the no-skill shuffle test.*

**Sizing.** Volatility targeting costs Sharpe here: {sg(S.loc['Frozen, fixed 1 contract', 'sharpe'])} with one fixed contract against {sg(S.loc[FZ, 'sharpe'])} at a 10% target, because the strategy earns most when volatility is high, which is when the target cuts the position. Without the long-run blend the account ran up to {int(S.loc['Frozen, 60-day vol only (no long-run blend)', 'max_contracts'])} contracts in the zero-rate years and Sharpe fell to {sg(S.loc['Frozen, 60-day vol only (no long-run blend)', 'sharpe'])}. Higher targets scale return and drawdown together (20% target: {pc(S.loc['Frozen, 20% vol target', 'maxdd_pct'])} drawdown, a {pc(S.loc['Frozen, 20% vol target', 'worst_month_pct'], 0)} month).

**Costs.** Sharpe {sg(S.loc['Frozen, cost 0.5 bp/side', 'sharpe'])} at 0.5 bp per side (one full tick), {sg(S.loc['Frozen, cost 1 bp/side', 'sharpe'])} at 1 bp and {sg(S.loc['Frozen, cost 2 bp/side', 'sharpe'])} at 2 bp. Rolls are {sides_roll/(sides_roll+sides_trade):.0%} of the contract-sides traded: at a 10% target the account rolls about {S.loc[FZ, 'avg_contracts']:.0f} contracts four times a year, against {flips} direction changes in {yrs:.1f} years.

**Instrument.** On the OIS-spliced prices for 2005–14 the frozen spec is {sg(S.loc['Frozen, OIS-spliced prices 2005-14', 'sharpe'])} ({k(S.loc['Frozen, OIS-spliced prices 2005-14', 'final_equity'])}) against {sg(S.loc[FZ, 'sharpe'])} ({k(S.loc[FZ, 'final_equity'])}); follow-the-ECB goes from {sg(S.loc[EC, 'sharpe'])} to {sg(S.loc['Follow-the-ECB, OIS-spliced prices', 'sharpe'])}.

**Margin.** Margin is never the constraint. It averaged {pc(S.loc[FZ, 'avg_margin_pct'])} of equity and peaked at {pc(S.loc[FZ, 'peak_margin_pct'])}; even with margin scaled up with volatility the peak stays at {pc(S.loc[FZ, 'peak_margin_stress_pct'])}. The binding limit is the volatility target, and 95% of the account sits in cash, which this backtest credits no interest on.
"""]

# ---------- appendix A: last five years ----------
FZ5 = FZ; EC5 = EC; e5 = d5["equity"]; dd5 = e5 / e5.cummax() - 1; tr5 = dd5.idxmin(); pk5 = e5.loc[:tr5].idxmax(); rec5 = e5.loc[tr5:][e5.loc[tr5:] >= e5.loc[pk5]].index
wm5 = m5["ret"].idxmin() + pd.offsets.MonthEnd(1); run = (np.sign(m5["contracts"]) != np.sign(m5["contracts"]).shift()).cumsum(); runs = []
for _, g in m5.groupby(run): runs.append((("Short" if g["contracts"].iloc[0] < 0 else "Long"), g.index[0] + pd.offsets.MonthEnd(1), g.index[-1] + pd.offsets.MonthEnd(1), len(g), g["chg_pts"].sum() * 100, g["pnl"].sum()))
flips5 = [(t + pd.offsets.MonthEnd(1)) for t in m5.index[np.sign(m5["contracts"]).diff().abs() > 0]]; fire = ((score.abs() > 0.5) & (np.sign(score) != ecb)).loc["2021-08-31":"2026-07-31"]; n_fire = int(fire.sum())
ov_move = cont["chg1"].loc["2021-09-01":"2022-07-31"].sum() * 100; ov_pos = m5.loc[fire[fire].index]; ov_gain = ov_pos[ov_pos["pnl"] > 0]["contracts"].abs()
jul = m5.loc["2022-06-30"]; worst_long = m5.loc[(m5["contracts"] > 0)].sort_values("pnl").iloc[0]; prelong = m5.loc["2025-10-31":"2026-01-31", "contracts"]
bs5 = mc5["bootstrap_sharpe"]; bp5 = mc5["bootstrap_pnl"]; nl5 = mc5["nulls"]; ds5 = mc5["deflated"]; tot5 = m5["pnl"].sum(); top5_5 = m5["pnl"].nlargest(5).sum() / tot5
mp5 = d5["margin_pct"]; pk_m = d5["margin"].idxmax()
def row5(name, label=None, bold=False):
    r = S5.loc[name]; cells = [label or name, sg(r["sharpe"]), pc(r["cagr_pct"]), pc(r["maxdd_pct"]), eur(r["final_equity"]), ("0" if name == LO else sg(r["sharpe"] - S5.loc[LO, "sharpe"]))]
    return "| " + " | ".join(f"**{c}**" if bold else c for c in cells) + " |"
def yl(y): return {2021: "2021 (Sep–Dec)", 2026: "2026 (Jan–Aug)"}.get(y, str(y))
APPA = f"""# Appendix A. The last five years: September 2021 to August 2026

A new €50,000 account opened on 1 September 2021, same rules, sizing, costs ({CB} bp per side) and margin as the main test. 60 months, covering the 2022–23 hiking cycle, the 2024–25 cuts and the June 2026 hike. The walk-forward threshold is 0.5 in every one of these years, so it is the frozen spec here and is not shown separately. Output: `results/bt50k_5y_*.csv`, figures `results/fig9_bt50k_5y_account.png` and `results/fig10_bt50k_5y_montecarlo.png`. Both pages in one file: `results/bt50k_5y_pages.pdf` (page 1 account, page 2 Sharpe and Monte Carlo analysis).

## A1. Results

| Variant | Sharpe | CAGR | Max DD | Final equity | Sharpe vs long-only |
|---|---|---|---|---|---|
{row5(FZ5, bold=True)}
{row5(EC5)}
{row5(LO, "Long-only, 10% vol (benchmark)")}
{row5(TR, "12M trend, 10% vol (benchmark)")}
{row5("Frozen, 5% vol target")}
{row5("Frozen, 15% vol target")}
{row5("Frozen, 20% vol target")}
{row5("Frozen, 60-day vol only (no long-run blend)", "Frozen, 60-day vol only")}
{row5("Frozen, fixed 1 contract")}
{row5("Frozen, fixed 3 contracts")}
{row5("Follow-the-ECB, fixed 3 contracts")}
{row5("Frozen, cost 0.5 bp/side")}
{row5("Frozen, cost 1 bp/side")}
{row5("Frozen, cost 2 bp/side")}

Frozen spec, account detail:

| Measure | Value |
|---|---|
| Total P&L | {seur(S5.loc[FZ5, "pnl_eur"])} on €50,000 |
| Realised volatility | {pc(S5.loc[FZ5, "vol_pct"])} a year against the 10% target |
| Worst drawdown | {pc(S5.loc[FZ5, "maxdd_pct"])}, from {pk5:%B %Y} to {tr5:%B %Y}, {"recovered " + rec5[0].strftime("%B %Y") if len(rec5) else "not yet recovered at end-August 2026"} |
| Worst month / winning months | {pc(S5.loc[FZ5, "worst_month_pct"])} ({wm5:%B %Y}) / {S5.loc[FZ5, "hit_pct"]:.0f}% |
| Contracts held | average {S5.loc[FZ5, "avg_contracts"]:.1f}, range {int(d5["contracts"].abs().min())} to {int(S5.loc[FZ5, "max_contracts"])} |
| Margin deployed | average {eur(d5["margin"].mean())} ({pc(S5.loc[FZ5, "avg_margin_pct"])} of equity), peak {eur(d5["margin"].max())}; peak share {pc(S5.loc[FZ5, "peak_margin_pct"])} in {mp5.idxmax():%B %Y} |
| Costs paid | {eur(d5["fees"].sum())} |
| Direction changes | {len(flips5)} ({", ".join(("to long" if m5.loc[t - pd.offsets.MonthEnd(1), "contracts"] > 0 else "to short") + " at end-" + (t - pd.offsets.MonthEnd(1)).strftime("%B %Y") for t in flips5)}); override fired in {n_fire} months, all September 2021 to July 2022 |

By position run:

| Run | Months | 2nd contract move | P&L |
|---|---|---|---|
""" + "\n".join(f"| {a}, {b:%b %Y} to {c:%b %Y} | {n} | {sg(mv, 0)} bp | {seur(p)} |" for a, b, c, n, mv, p in runs) + f"""

By calendar year:

| Year | P&L € | Return | Year-end equity | Avg contracts (+ long, − short) | Avg margin, share of equity |
|---|---|---|---|---|---|
""" + "\n".join(f"| {yl(y)} | {('+' if r.pnl_eur >= 0 else MINUS)}{abs(r.pnl_eur):,.0f} | {spc(r.ret_pct)} | {r.equity_end:,.0f} | {sg(r.avg_contracts, 1)} | {pc(r.avg_margin_pct)} |" for y, r in YR5.iterrows()) + f"""

![Figure 9. Last five years: account page](results/fig9_bt50k_5y_account.png)

*Figure 9. New €50,000 account from September 2021: equity, signal, volatility, contracts and margin.*

## A2. Sharpe analysis and Monte Carlo

Sharpe by calendar year (2021 = Sep–Dec, 2026 = Jan–Aug):

| Year | Frozen spec, 10% vol | Follow-the-ECB, 10% vol | Long-only, 10% vol | Frozen spec, 1 contract | Follow-the-ECB, 1 contract |
|---|---|---|---|---|---|
""" + "\n".join(("| **All 60 months** | " + " | ".join(f"**{sg(v)}**" for v in r) + " |") if y == "all 60 months" else ("| " + str(y) + " | " + " | ".join(sg(v) for v in r) + " |") for y, r in SY5.iterrows()) + f"""

Block bootstrap, 12-month blocks, 10,000 paths of 60 months:

| | Frozen spec | Follow-the-ECB | Long-only |
|---|---|---|---|
| Sharpe, 5th / 50th / 95th percentile | """ + " | ".join(f"{sg(bs5[k_]['p05'])} / {sg(bs5[k_]['p50'])} / {sg(bs5[k_]['p95'])}" for k_ in bs5) + f""" |
| P(Sharpe > 0) | """ + " | ".join(f"{bs5[k_]['prob_gt0']:.0%}" for k_ in bs5) + f""" |
| P(beats long-only) / P(beats ECB rule) | {bs5['Frozen spec']['prob_beats_longonly']:.0%} / {bs5['Frozen spec']['prob_beats_ecb']:.0%} | | |
| Final equity, 5th / 50th / 95th | """ + " | ".join(f"{k(bp5[k_]['final_p05'])} / {k(bp5[k_]['final_p50'])} / {k(bp5[k_]['final_p95'])}" for k_ in bp5) + f""" |
| P(ending below €50,000) | """ + " | ".join(f"{bp5[k_]['prob_end_below_start']:.0%}" for k_ in bp5) + f""" |
| Max drawdown, median / 5th / 1st percentile | """ + " | ".join(f"{pc(bp5[k_]['maxdd_p50'], 0)} / {pc(bp5[k_]['maxdd_p05'], 0)} / {pc(bp5[k_]['maxdd_p01'], 0)}" for k_ in bp5) + f""" |
| First-year P&L, 5th / 50th / 95th | """ + " | ".join(f"{sk(bp5[k_]['pnl1y_p05'])} / {sk(bp5[k_]['pnl1y_p50'])} / {sk(bp5[k_]['pnl1y_p95'])}" for k_ in bp5) + f""" |
| P(loss after 1 year) | """ + " | ".join(f"{bp5[k_]['prob_loss_1y']:.0%}" for k_ in bp5) + f""" |

No-skill nulls (6-month blocks, because 60 months hold only five 12-month blocks):

| | Observed Sharpe | Null mean | Null 95th pct | p, circular shift | p, block permutation |
|---|---|---|---|---|---|
""" + "\n".join(f"| {k_} | {sg(v['observed'])} | {sg(v['perm_mean'])} | {sg(v['perm_p95'])} | {pv(v['p_shift'], 48)} | {pv(v['p_perm'], 3000)} |" for k_, v in nl5.items()) + f"""

Deflated Sharpe on 60 months (45 / 70 trials): frozen spec {ds5['Frozen spec']['dsr_45']:.2f} / {ds5['Frozen spec']['dsr_70']:.2f}, follow-the-ECB {ds5['Follow-the-ECB']['dsr_45']:.2f} / {ds5['Follow-the-ECB']['dsr_70']:.2f}. Monthly returns have skew {sg(ds5['Frozen spec']['skew'])} and kurtosis {ds5['Frozen spec']['kurt']:.1f}.

![Figure 10. Monte Carlo, last five years](results/fig10_bt50k_5y_montecarlo.png)

*Figure 10. The same four Monte Carlo panels for the 60-month window.*

## A3. Reading

1. **One trade made the money.** {runs[0][5]/tot5:.0%} of the P&L is the {runs[0][3]}-month short through the hiking cycle. The two-year long through the cuts {"lost " + eur(-runs[1][5]) if runs[1][5] < 0 else "made " + eur(runs[1][5])} even though the contract rose {runs[1][4]:.0f} bp, because {(worst_long.name + pd.offsets.MonthEnd(1)):%B %Y} cost {eur(-worst_long['pnl'])} on {int(worst_long['contracts'])} contracts. The best 5 months are {top5_5:.0%} of the P&L.
2. **The override added nothing on equal sizing.** With 3 fixed contracts the frozen spec ends at {eur(S5.loc['Frozen, fixed 3 contracts', 'final_equity'])} and plain follow-the-ECB at {eur(S5.loc['Follow-the-ECB, fixed 3 contracts', 'final_equity'])} (Sharpe {sg(S5.loc['Frozen, fixed 3 contracts', 'sharpe'])} and {sg(S5.loc['Follow-the-ECB, fixed 3 contracts', 'sharpe'])}; {sg(mc5['unit_check']['sharpe'])} and {sg(mc5['unit_check_ecb']['sharpe'])} on one contract). The 2nd contract moved {sg(ov_move, 0)} bp net over the {n_fire} override months. The gap at a 10% target ({sg(S5.loc[FZ5, 'sharpe'])} against {sg(S5.loc[EC5, 'sharpe'])}) comes from sizing: the override was short {int(ov_gain.min())} to {int(ov_gain.max())} contracts in the months it gained, and {int(abs(jul['contracts']))} contracts in July 2022, when the contract bounced {abs(jul['chg_pts'])*100:.0f} bp against it.
3. **Fixed contracts beat volatility targeting in this window.** Three fixed contracts made {"the same money as" if abs(S5.loc['Frozen, fixed 3 contracts', 'pnl_eur'] / S5.loc[FZ5, 'pnl_eur'] - 1) < 0.1 else eur(S5.loc['Frozen, fixed 3 contracts', 'pnl_eur']) + " against " + eur(S5.loc[FZ5, 'pnl_eur']) + " for"} the 10% target with a {pc(S5.loc['Frozen, fixed 3 contracts', 'maxdd_pct'])} drawdown instead of {pc(S5.loc[FZ5, 'maxdd_pct'])} and a worst month of {pc(S5.loc['Frozen, fixed 3 contracts', 'worst_month_pct'])} instead of {pc(S5.loc[FZ5, 'worst_month_pct'])}. Low volatility in late 2025 took the target to {int(prelong.min())} to {int(prelong.max())} contracts just before the {wm5:%B %Y} move.
4. **This window is better than typical, not typical.** The rolling 60-month Sharpe of the 2008-start account is {sg(roll60.iloc[-1])} now against a median of {sg(roll60.median())} across {int(roll60.notna().sum())} windows (range {sg(roll60.min())} to {sg(roll60.max())}); the current window beats {(roll60.dropna() < roll60.iloc[-1]).mean():.0%} of them. Five years with a full hiking cycle and a cutting cycle are the conditions the rule is built for.
5. **Sixty months, three position runs.** The shuffle tests reject luck (p = {nl5['Frozen spec']['p_perm']:.3f}), but with {len(flips5)} direction changes they have little to work with, and the bootstrap interval is wide: {sg(bs5['Frozen spec']['p05'])} to {sg(bs5['Frozen spec']['p95'])}.
6. **Prices are still synthetic here, and this is where they are weakest.** The synthetic takes its forward premium from the AAA government curve, and in 2022–23 short government yields moved away from Euribor-linked rates. Real ICE prices exist for this whole window (Databento, December 2018 onward); rerunning this page on them is the check that matters most.

**Verdict for the window: context-dependent.** If the ECB keeps moving rates, the last five years support the plain follow-the-ECB rule at about Sharpe +1 on fixed contracts; they give no support for the override beyond the sizing effect, and none for volatility targeting over a fixed position. {len(S5)} further account variants were run for this page; no parameter was changed.
"""

# ---------- appendix B: correlation (numbers from portfolio_correlation.py) ----------
BYF = pd.read_csv(f"{R}/trendcorr_by_frequency.csv", index_col=0); MCR = pd.read_csv(f"{R}/trendcorr_monthly.csv", index_col=0); TY = pd.read_csv(f"{R}/trendcorr_by_year.csv", index_col=0); tc = json.load(open(f"{R}/trendcorr.json"))
MP = pd.read_csv(f"{R}/trendcorr_monthly_pnl.csv", index_col=0, parse_dates=True); rc = MP["Frozen spec, 1 contract"].rolling(36).corr(MP["Whole trend book"])
sub = tc["subperiods"]; bi = tc["bootstrap"]; cd = tc["conditional"]; cb = tc["combinations"]; nF = [c.split("(n=")[1].rstrip(")") for c in BYF.columns]
def c2(x): return sg(x) if abs(x) >= 0.005 else "0.00"
APPB = f"""# Appendix B. Correlation with the trend-following book

Does the Euribor strategy add something the rest of the portfolio does not already have? Tested against the AlgoGators trend-following backtest (run `TREND_FOLLOWING_20260505_010930_346`, 34 CME markets, per-market daily P&L in dollars from `trend_risk/.../phase2/pnl_panel.csv`). Window 4 April 2011 to 30 April 2026: {nF[0]} days, {nF[2]} months. Euribor side: frozen spec on one contract unless stated. Script `portfolio_correlation.py`, output `results/trendcorr_*.csv`, `results/trendcorr.json`, figure `results/fig11_bt50k_trend_correlation.png`.

## B1. Correlations

Frozen spec, one contract, against the trend book and its sleeves:

| Trend book | Daily ({nF[0]}) | Weekly ({nF[1]}) | Monthly ({nF[2]}) | Quarterly ({nF[3]}) | Annual ({nF[4]}) |
|---|---|---|---|---|---|
""" + "\n".join(f"| {lab} | " + " | ".join((f"**{c2(v)}**" if (lab == 'Whole book' and j == 2) else c2(v)) for j, v in enumerate(BYF.loc[key_])) + " |" for lab, key_ in [("Whole book", "Whole trend book"), ("US rates sleeve (ZT, ZF, ZN, UB)", "US rates sleeve"), ("Currency sleeve (9 pairs)", "Currency sleeve"), ("Everything except rates", "Everything except rates")]) + f"""

Monthly correlation for the other Euribor versions:

| Euribor version | Whole book | US rates sleeve | Currency sleeve | Everything except rates |
|---|---|---|---|---|
""" + "\n".join(f"| {lab} | " + " | ".join(c2(v) for v in MCR.loc[key_]) + " |" for lab, key_ in [("Frozen spec, 1 contract", "Frozen spec, 1 contract"), ("Frozen spec, €50,000 account (10% vol target)", "Frozen spec, EUR 50k account"), ("Follow-the-ECB, 1 contract", "Follow-the-ECB, 1 contract")]) + f"""

Monthly correlation by sub-period and its sampling range (block bootstrap, 12-month blocks, 10,000 draws):

| | 2011–15 ({int(sub['2011-2015']['months'])} months) | 2016–20 ({int(sub['2016-2020']['months'])}) | 2021–26 ({int(sub['2021-2026']['months'])}) | Full window | Bootstrap 5th to 95th percentile |
|---|---|---|---|---|---|
| Whole book | {c2(sub['2011-2015']['Whole trend book'])} | {c2(sub['2016-2020']['Whole trend book'])} | {c2(sub['2021-2026']['Whole trend book'])} | {c2(bi['Whole trend book']['observed'])} | {sg(bi['Whole trend book']['p05'])} to {sg(bi['Whole trend book']['p95'])} |
| US rates sleeve | {c2(sub['2011-2015']['US rates sleeve'])} | {c2(sub['2016-2020']['US rates sleeve'])} | {c2(sub['2021-2026']['US rates sleeve'])} | {c2(bi['US rates sleeve']['observed'])} | {sg(bi['US rates sleeve']['p05'])} to {sg(bi['US rates sleeve']['p95'])} |
| Currency sleeve | | | | {c2(bi['Currency sleeve']['observed'])} | {sg(bi['Currency sleeve']['p05'])} to {sg(bi['Currency sleeve']['p95'])} |

The rolling 36-month correlation with the whole book stays between {sg(rc.min())} and {sg(rc.max())} throughout, inside the range two unrelated series would produce (Figure 11, top).

![Figure 11. Correlation with the trend-following book](results/fig11_bt50k_trend_correlation.png)

*Figure 11. Rolling 36-month correlation, and each year's P&L for both strategies in units of own volatility.*

## B2. Year by year

P&L in each strategy's own units, and scaled by its own annual volatility so the two are comparable (2011 from April, 2026 to April):

| Year | Trend book $ | Trend book, vol units | Euribor bp | Euribor, vol units |
|---|---|---|---|---|
""" + "\n".join(f"| {y} | {('+' if r.trend_book_usd >= 0 else MINUS)}{abs(r.trend_book_usd):,.0f} | {sg(r.trend_in_vol_units)} | {sg(r.euribor_bp, 0)} | {sg(r.euribor_in_vol_units)} |" for y, r in TY.iterrows()) + f"""

Euribor in the trend book's extreme months:

| Months | Trend book mean | Euribor mean | Euribor months positive |
|---|---|---|---|
""" + "\n".join(f"| {lab} | {('+' if v['trend_mean_usd'] >= 0 else MINUS)}${abs(v['trend_mean_usd']):,.0f} | {sg(v['euribor_mean_bp'], 1)} bp | {v['euribor_share_positive']:.0%} |" for lab, v in [("Trend book's 15 worst", cd["trend book's 15 worst months"]), ("Trend book's 15 best", cd["trend book's 15 best months"]), (f"All {nF[2]}", cd["all months"])]) + f"""

## B3. Combination

Each stream scaled to the same monthly volatility, then weighted (monthly, April 2011 to April 2026):

| Trend / Euribor risk weight | Sharpe | Worst drawdown, in annual volatilities |
|---|---|---|
""" + "\n".join(f"| {w.replace('/', ' / ')} | {sg(v['sharpe'])} | {sg(v['maxdd_in_annual_vols'])} |" for w, v in cb.items()) + f"""

## B4. Reading

**Accepted: the Euribor strategy is uncorrelated with the trend book over the 15 years both exist.** Monthly correlation {c2(bi['Whole trend book']['observed'])}, bootstrap range {sg(bi['Whole trend book']['p05'])} to {sg(bi['Whole trend book']['p95'])}, the same in three sub-periods, and zero against the book's own US rates sleeve. The two earn in different years: the trend book in 2017 and 2019–21, Euribor in 2012 and 2022–24. A 20% risk weight lifts the combined Sharpe from {sg(cb['100/0']['sharpe'])} to {sg(cb['80/20']['sharpe'])}.

Caveats:

1. **Uncorrelated, not a hedge.** In the trend book's 15 worst months Euribor averaged {sg(cd["trend book's 15 worst months"]['euribor_mean_bp'], 1)} bp against {sg(cd['all months']['euribor_mean_bp'], 1)} bp in an average month. It does not lose alongside the book, and it does not offset it.
2. **2008–10 is outside the window.** The trend backtest starts in April 2011, so the years of Euribor's largest early profit, when trend strategies in general also did well, cannot be compared.
3. **The combined Sharpe leans on the Euribor Sharpe**, which carries the main report's caveats: synthetic prices, an in-sample threshold, two good ECB cycles. The correlation finding is sturdier than the Sharpe finding, because it does not depend on the level of Euribor returns.
4. **Daily and weekly figures are biased toward zero** by the synthetic's daily noise and by the gap between European and US closes. The monthly figure is the one to use.
5. **The annual correlation with the currency sleeve, {sg(BYF.loc['Currency sleeve'].iloc[4])}, is 16 points and one cell of 20.** It reflects three years (2012, 2022, 2024) when Euribor earned and the currency sleeve lost; treat it as an observation, not a property.
6. **One trend run.** The comparison uses a single backtest configuration, which held 5 markets on average and US rates on 9% to 21% of days. A trend book with a larger rates allocation, or one that adds European short-rate futures, would overlap more.
7. **Live trading** (October 2025 to May 2026, seven months) is too short to add anything and was not used.
"""
def rename(t):
    for a, b in [("Follow-the-ECB", "ECB rate momentum"), ("follow-the-ECB", "ECB rate momentum"), ("ECB rule", "ECB rate momentum"), ("R+I+S", "risk-factor")]: t = t.replace(a, b)
    return t
open(f"{ROOT}/BACKTEST_50K.md", "w").write(rename(MAIN[0]))
open(f"{ROOT}/BACKTEST_50K_APPENDIX.md", "w").write(rename(f"# Euribor macro strategy: appendices to the €50,000 account backtest\n\nGenerated with the main report on {TODAY} (cost {CB} bp per side). Appendix A is the last-five-years account (September 2021 to August 2026); Appendix B is the correlation with the trend-following book. Section numbers refer to the main report.\n\n---\n\n" + APPA + "\n---\n\n" + APPB))
print("BACKTEST_50K.md and BACKTEST_50K_APPENDIX.md written at", CB, "bp per side")
