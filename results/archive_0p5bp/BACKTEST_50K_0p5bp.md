# Euribor macro strategy: €50,000 account backtest

Test report, 1 October 2026. Scripts: `backtest_50k.py` (account simulation and Monte Carlo), `make_bt50k_charts.py`. Output: `results/bt50k_*.csv`, `results/bt50k_mc.json`, `results/fig6`–`fig8`, log in `results_bt50k.log`.

## 1. Hypothesis
The frozen specification (follow the ECB's last move, overridden by the R+I+S composite when |score| > 0.5) earns a positive return on the 2nd quarterly Euribor contract. This test asks what that edge looks like as a real account: €50,000 of capital, whole contracts, euro costs, margin, and a sizing rule, since the specification itself only says long or short.

## 2. Benchmark
Long-only, 12-month trend and the plain follow-the-ECB rule, all run through the same account and the same sizing. Window January 2008 to August 2026, 224 months, synthetic 2nd-contract prices. The account starts on 1 January 2008, a month earlier than the earlier reports' 31 January start; that month was a loss and takes the frozen spec's one-contract Sharpe from +1.09 to +1.02.

Account assumptions:

| Item | Setting |
|---|---|
| Capital | €50,000, euro account, cash earns no interest |
| Contract | €2,500 per price point, €25 per basis point |
| Sizing | contracts = round(10% × equity ÷ (σ × €2,500)), set each month-end with the signal |
| σ | 70% trailing 60-day realised volatility + 30% its long-run mean, annualised |
| Costs | 0.5 bp per side = €12.50 per contract; roll = €25 per contract, four times a year |
| Margin | €237 initial margin per contract (broker quote, September 2026), held flat through history |

The 10% volatility target and the volatility blend are my choices, not part of the frozen specification. Section 5 shows what changes with other choices.

## 3. Variants
16 account runs: 5 strategies at the 10% target (frozen, walk-forward threshold, follow-the-ECB, long-only, 12M trend); the frozen spec at 5%, 15% and 20% targets, with unblended 60-day volatility, with 1 and 3 fixed contracts, at 1 and 2 bp per side, from a 2002 start, and on the OIS-spliced price series; follow-the-ECB on the OIS-spliced series. No signal parameter was changed or tuned.

## 4. Results

| Variant | Sharpe | CAGR | Max DD | Final equity | Sharpe vs long-only |
|---|---|---|---|---|---|
| **Frozen spec, 10% vol target** | **+0.79** | **8.3%** | **−20.1%** | **€228,110** | **+0.55** |
| Walk-forward threshold, 10% vol | +0.74 | 7.7% | −20.0% | €203,432 | +0.50 |
| Follow-the-ECB only, 10% vol | +0.61 | 6.2% | −33.4% | €156,918 | +0.37 |
| Long-only, 10% vol (benchmark) | +0.24 | 2.1% | −55.7% | €73,628 | 0 |
| 12M trend, 10% vol (benchmark) | +0.24 | 2.1% | −40.5% | €73,966 | 0.00 |
| Frozen, 5% vol target | +0.67 | 3.5% | −10.4% | €96,548 | +0.43 |
| Frozen, 15% vol target | +0.75 | 11.6% | −29.2% | €400,035 | +0.51 |
| Frozen, 20% vol target | +0.75 | 15.8% | −37.5% | €809,795 | +0.51 |
| Frozen, 60-day vol only | +0.62 | 7.7% | −27.2% | €202,714 | +0.38 |
| Frozen, fixed 1 contract | +0.98 | 2.7% | −6.6% | €83,543 | +0.74 |
| Frozen, fixed 3 contracts | +0.84 | 6.0% | −18.4% | €150,628 | +0.60 |
| Frozen, cost 1 bp/side | +0.67 | 6.9% | −20.5% | €177,585 | +0.43 |
| Frozen, cost 2 bp/side | +0.43 | 4.3% | −38.6% | €111,396 | +0.19 |
| Frozen, start Jan 2002 | +0.73 | 7.5% | −20.7% | €307,018 | n/a |
| Frozen, OIS-spliced prices 2005–14 | +0.79 | 8.3% | −19.4% | €225,292 | n/a |
| Follow-the-ECB, OIS-spliced prices | +0.58 | 5.8% | −35.9% | €145,937 | n/a |

Frozen spec, account detail:

| Measure | Value |
|---|---|
| Total P&L | +€178,110 on €50,000 |
| Realised volatility | 10.9% a year against the 10% target |
| Worst drawdown | −20.1% (−€42,625 at its deepest in euros), Jan to Aug 2011, recovered Apr 2012 |
| Longest time under water | 983 trading days |
| Worst month / best month | −13.7% (Mar 2026) / +13.3% (Jul 2012) |
| Winning months | 63% |
| Contracts held | average 14.6, range 1 to 30 as equity grew and volatility fell |
| Costs paid | €35,638, about 17% of gross profit |
| Direction changes | 12 in 18.7 years; position resized in 155 of 224 months |

Margin deployed (Figure 7, bottom panel):

| Period | Avg contracts | Avg margin | Share of equity | Peak share if margin had scaled with volatility |
|---|---|---|---|---|
| 2008–12 | 7.0 | €1,648 | 1.7% | 4.5% |
| 2013–21 | 19.1 | €4,529 | 3.3% | 4.9% |
| 2022–26 | 14.0 | €3,319 | 1.6% | 3.4% |
| Whole window | 14.6 | €3,454 | 2.4% (peak 4.9%) | 4.9% |

Calendar years, frozen spec:

| Year | P&L € | Return | Year-end equity | Avg contracts (+ long, − short) |
|---|---|---|---|---|
| 2008 | +7,512 | +15.0% | 57,512 | −2.0 |
| 2009 | +32,079 | +55.8% | 89,591 | +4.9 |
| 2010 | +18,097 | +20.2% | 107,687 | +8.0 |
| 2011 | −13,974 | −13.0% | 93,713 | −0.1 |
| 2012 | +43,578 | +46.5% | 137,292 | +12.1 |
| 2013 | −10,599 | −7.7% | 126,692 | +15.6 |
| 2014 | +6,915 | +5.5% | 133,607 | +19.0 |
| 2015 | +198 | +0.1% | 133,805 | +16.2 |
| 2016 | +529 | +0.4% | 134,334 | +20.7 |
| 2017 | +10,035 | +7.5% | 144,369 | +14.1 |
| 2018 | −2,312 | −1.6% | 142,057 | +21.6 |
| 2019 | −1,783 | −1.3% | 140,274 | +20.9 |
| 2020 | −425 | −0.3% | 139,849 | +16.8 |
| 2021 | +700 | +0.5% | 140,549 | −0.2 |
| 2022 | +35,199 | +25.0% | 175,748 | −10.3 |
| 2023 | +6,469 | +3.7% | 182,216 | −7.7 |
| 2024 | +54,143 | +29.7% | 236,360 | +1.3 |
| 2025 | +693 | +0.3% | 237,053 | +18.1 |
| 2026 (to Aug) | −8,943 | −3.8% | 228,110 | +10.9 |

![Figure 6. Equity and drawdown, January 2008 to August 2026](results/fig6_bt50k_equity.png)

*Figure 6. Account equity for the four strategies and the frozen spec's drawdown.*

![Figure 7. Signal, volatility, contracts and margin](results/fig7_bt50k_signal_vol_margin.png)

*Figure 7. The signal, the volatility used for sizing, contracts held and margin deployed.*

## 5. Robustness

**Regimes.** The result is regime dependent, not universal.

| Sharpe by period | 2008–12 crisis | 2013–19 ZLB/QE | 2020–21 COVID | 2022–26 hikes + cuts |
|---|---|---|---|---|
| Frozen spec | +1.69 | +0.08 | +0.05 | +0.86 |
| Walk-forward threshold | +1.48 | +0.08 | +0.06 | +0.88 |
| Follow-the-ECB | +1.45 | +0.03 | −0.43 | +0.66 |
| Long-only | +1.91 | +0.04 | −0.43 | −0.95 |

67% of the account's growth came in 2008–12, 32% in 2022–26 and 2% in the nine years 2013–21. The best 5 months are 38% of total P&L and the best 10 are 61%.

**Monte Carlo, block bootstrap** (12-month blocks, 10,000 paths of 224 months, account returns):

| | Frozen spec | Walk-forward | Follow-the-ECB | Long-only |
|---|---|---|---|---|
| Sharpe, 5th / 50th / 95th percentile | +0.32 / +0.80 / +1.33 | +0.30 / +0.74 / +1.23 | +0.13 / +0.60 / +1.11 | −0.31 / +0.22 / +0.83 |
| P(Sharpe > 0) | 100% | 100% | 98% | 75% |
| P(beats long-only) / P(beats ECB rule) | 97% / 97% | 96% / 93% | | |
| Final equity, 5th / 50th / 95th | €85k / €222k / €667k | €81k / €199k / €548k | €59k / €152k / €453k | €23k / €71k / €253k |
| P(ending below €50,000) | 0.4% | 0.5% | 2.6% | 31% |
| Max drawdown, median / 5th / 1st percentile | −20% / −33% / −41% | −20% / −34% / −41% | −25% / −42% / −51% | −41% / −66% / −75% |
| P(drawdown worse than 20% / 30%) | 49% / 10% | 50% / 10% | 76% / 28% | 97% / 80% |
| First-year P&L, 5th / 50th / 95th | −€5.5k / +€2.3k / +€25.6k | −€5.4k / +€2.3k / +€24.0k | −€6.3k / +€1.5k / +€23.2k | −€9.8k / −€0.1k / +€25.7k |
| P(loss after 1 year / 5 years) | 29% / 9% | 29% / 10% | 38% / 18% | 50% / 43% |

**No-skill nulls** (the long/short path shifted or block-shuffled in time, position sizes left on their dates):

| | Observed Sharpe | Null mean | Null 95th pct | p, circular shift | p, block permutation |
|---|---|---|---|---|---|
| Frozen spec | +0.80 | +0.04 | +0.46 | 0 of 212 | 0 of 3,000 |
| Walk-forward threshold | +0.74 | +0.05 | +0.46 | 0.005 | 0.002 |
| Follow-the-ECB | +0.61 | +0.10 | +0.46 | 0.042 | 0.007 |

**Deflated Sharpe** (expected best-of-N Sharpe under the null: 0.53 for 45 trials, 0.57 for 70): frozen spec 0.86 / 0.83, walk-forward threshold 0.80 / 0.76, follow-the-ECB 0.63 / 0.57, long-only 0.11 / 0.08. Monthly returns have skew −0.43 and kurtosis 7.1.

![Figure 8. Monte Carlo, full window](results/fig8_bt50k_montecarlo.png)

*Figure 8. Bootstrap Sharpe with medians, bootstrap equity paths, bootstrap drawdown, and the no-skill shuffle test.*

**Sizing.** Volatility targeting costs Sharpe here: +0.98 with one fixed contract against +0.79 at a 10% target, because the strategy earns most when volatility is high, which is when the target cuts the position. Without the long-run blend the account ran up to 70 contracts in the zero-rate years and Sharpe fell to +0.62. Higher targets scale return and drawdown together (20% target: −37.5% drawdown, a −27% month).

**Costs.** Sharpe +0.67 at 1 bp per side and +0.43 at 2 bp. Rolls are the main cost: at a 10% target the account rolls about 15 contracts four times a year.

**Instrument.** On the OIS-spliced prices for 2005–14 the frozen spec is unchanged (+0.79, €225k), follow-the-ECB slips from +0.61 to +0.58.

**Margin.** Margin is never the constraint. It averaged 2.4% of equity and peaked at 4.9%; even with margin scaled up with volatility the peak stays under 5%. The binding limit is the volatility target, and 95% of the account sits in cash, which this backtest credits no interest on.

## 6. Verdict
**Accept as a paper-trading candidate, context-dependent; not yet evidence for live capital.** As an account the frozen specification turned €50,000 into €228,000 at a 10% volatility target, Sharpe +0.79 against +0.24 for long-only, with a 20% worst drawdown, and the timing survives the shuffle tests and deflation for 70 trials. The return is concentrated in two ECB cycles (2008–12 and 2022–24); from 2013 to 2021 the account was flat for nine years while holding its largest positions.

Caveats:

1. Prices are synthetic before 2019 and their day-to-day changes are noisy against real Eurex settlements (daily correlation 0.18 over 20 days), so daily volatility, drawdown depth and the March 2026 loss are approximate.
2. The 0.5 threshold was chosen on the full sample. The walk-forward threshold version (+0.74, €203k) is the fairer figure. In account terms the override looks stronger than on unit positions (+0.13 Sharpe over the rule here, +0.03 on one contract over the same window) because volatility targeting held 17 to 27 contracts short in the low-volatility months before the 2022 hikes; that is one episode.
3. 16 account variants were run on top of about 70 signal trials. No signal parameter was tuned here, but the 10% target and the 70/30 volatility blend were picked by me without a search, and the blend choice alone moves Sharpe from +0.62 to +0.79.
4. The bootstrap resamples this one history, so it inherits the two good cycles; it measures sampling noise, not the chance that the next cycle looks different.
5. Fat tails: two months lost more than 12% at a 10% volatility target (January 2008 and March 2026). In both, realised volatility ran at two to three times the estimate the position was sized on.
6. Margin of €237 is one broker's quote held flat for 18 years; real schedules were higher in 2008 and 2022–23. Account assumed in euros; a dollar account adds EUR/USD exposure on P&L.

Position a new €50,000 account would hold today under these rules: short 3 contracts, about €711 of margin. The rule is short after the June 2026 hike, the score is inside the dead band (−0.32 at end-August, −0.43 on partial September data), and sizing volatility was 62 bp on 23 September.
