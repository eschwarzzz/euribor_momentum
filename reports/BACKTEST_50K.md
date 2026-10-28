# Euribor macro strategy: €50,000 account backtest

Frozen specification v2, fixed on 28 October 2026; generated 28 October 2026. v1, as reported in September and October, is kept as a comparison row throughout.

## 1. Hypothesis
ECB policy rates move in runs, so the direction of the last move predicts the next month on the 2nd quarterly Euribor contract. The frozen specification has two parts. **ECB rate momentum** sets the default position: long if the main refinancing rate and the deposit facility rate together were cut over the last three months, short if they were raised, otherwise the position is kept. **The risk-factor score** can override it: above +0.5 the position is long, below −0.5 short, whatever the ECB did last. The position is decided at each month-end and held for the next month. This test asks what that edge looks like as a real account: €50,000, whole contracts, euro costs, margin, interest on cash and a sizing rule.

**The edge is regime dependent; expect long quiet stretches.** Half the months carry the strategy. In the other half, when the ECB has been on hold, the signal has little to say:

| State at month-end | Months | Frozen spec, bp a month (one contract, gross) | Score's correlation with next month's move | Average size of next month's move |
|---|---|---|---|---|
| ECB moved in the last 6 months | 111 | +10.4 | +0.49 | 16.2 bp |
| ECB on hold for 6 months or more | 113 | +2.1 | +0.11 | 9.6 bp |

The best 10 of 224 months are 58% of the account's trading P&L, and the nine years 2013–21 added 1% of its growth.

**The risk-factor score.** Five monthly inputs, one for each channel the ECB reacts to. Each is turned into an expanding z-score (at least 36 months), clipped to ±3 and multiplied by a sign fixed from theory. The score is their plain mean, so each input weighs 20%.

| Input | Channel | Sign (+ argues for a higher price, i.e. lower rates) | Publication lag |
|---|---|---|---|
| Deposit facility rate, 3-month change | policy persistence | − | none |
| HICP, year on year | the mandate | − | 1 month |
| Core HICP, year on year | how persistent inflation is | − | 1 month |
| Unemployment rate, 6-month change | slack | + | 2 months |
| ECB composite indicator of systemic stress (CISS), level | financial stress | + | none |

**What changed from v1, and why.** An external review (18 October 2026) recommended four changes; all four are in v2.

| | v1 (September 2026) | v2 (frozen) | Reason |
|---|---|---|---|
| Anchor | deposit rate alone | main refinancing rate plus deposit rate | On 9 October 2008, the day after a 50 bp cut, the ECB narrowed the corridor and put the deposit rate back to its July level. The deposit-rate rule saw no cut and stayed short into a 142 bp rally. It is the only month from 1999 to 2026 where the choice of rate changes the position. |
| Score | 23 series in three groups, averaged within groups first | 5 inputs, plain mean | Four rates series were one signal (correlations 0.62 to 0.93); the group step set hidden weights; four inputs worked only in 2008–12 and several added nothing. |
| Sizing | 10% volatility target on a 60-day/long-run blend | 10% of equity at a fixed volatility, the 1999–2007 average | The strategy earns when volatility is high, so the target held its smallest positions when the signal paid (section 5). |
| Cash | earns nothing | EONIA, then €STR | About 98% of the account is cash. |

The five inputs were picked on economic grounds and fixed before any test of the reduced score, but after reading the review's factor-by-factor evidence, so the choice is not blind; it is counted as a trial. The 0.5 threshold was kept from v1 without retesting.

## 2. Benchmark
Long-only, 12-month trend and ECB rate momentum alone, all through the same account and sizing, plus v1 as reported. Window January 2008 to August 2026, 224 months, synthetic 2nd-contract prices. On one contract at 0.3 bp per side from 1 January 2008 the frozen spec scores +1.02; the one-contract report (0.5 bp, from 31 January) gives +1.06.

Account assumptions:

| Item | Setting |
|---|---|
| Capital | €50,000, euro account |
| Contract | €2,500 per price point, €25 per basis point |
| Sizing | contracts = round(10% × equity ÷ (σ × €2,500)), set each month-end with the signal |
| σ | 49.1 bp a year: the average 60-day realised volatility of the contract over 1999–2007, known before the account opens. That is one contract per €12,287 of equity; size follows equity, not volatility |
| Cash | equity above initial margin earns EONIA to September 2019, then €STR, including the negative rates of 2015–22. Sharpe ratios are on returns in excess of that rate |
| Costs | 0.3 bp per side = €7.50 per contract (half a one-tick spread plus exchange, clearing and broker fees); roll = €15 per contract, four times a year |
| Margin | €237 initial margin per contract (broker quote, September 2026), held flat through history |

The sizing rule uses no volatility observed after the account opens, as the review asked. It does not target a realised volatility either; section 5 shows what that costs. The 0.3 bp cost is a realistic figure for the ICE contract; 0.5 bp (one full tick) is kept as a sensitivity row and is about what Eurex FEU3 would cost.

## 3. Variants
23 account runs. Five strategies with per-euro sizing: the frozen spec, a walk-forward threshold, ECB rate momentum, long-only and 12-month trend. v1 as reported and v1 with per-euro sizing; ECB rate momentum on the deposit rate alone. The frozen spec and ECB rate momentum at the v1 10% volatility target, and the frozen spec with unblended 60-day volatility. The frozen spec at 5%, 15% and 20% risk per euro, with 1 and 3 fixed contracts, without interest, at 0.5, 1 and 2 bp per side, from a 2002 start and on the OIS-spliced price series; ECB rate momentum on the OIS-spliced series. No signal parameter was tuned on these runs.

## 4. Results

| Variant | Sharpe | CAGR | Max DD | Final equity | Sharpe vs long-only |
|---|---|---|---|---|---|
| **Frozen spec, per-euro sizing** | **+1.00** | **15.0%** | **−22.6%** | **€708,208** | **+0.67** |
| Walk-forward threshold, per-euro sizing | +1.01 | 15.1% | −22.6% | €723,676 | +0.67 |
| ECB rate momentum only, per-euro sizing | +1.01 | 15.1% | −24.8% | €714,419 | +0.67 |
| Long-only, per-euro sizing (benchmark) | +0.34 | 4.6% | −60.8% | €117,030 | 0 |
| 12M trend, per-euro sizing (benchmark) | +0.44 | 6.4% | −44.7% | €162,615 | +0.11 |
| v1 spec, 10% vol target, no interest (as reported) | +0.85 | 9.0% | −20.1% | €255,769 | +0.51 |
| v1 spec, per-euro sizing | +1.03 | 15.5% | −22.6% | €764,380 | +0.69 |
| ECB rate momentum, DFR only, per-euro sizing | +0.76 | 11.3% | −34.1% | €382,066 | +0.43 |
| Frozen, 10% vol target | +0.77 | 8.9% | −19.6% | €251,354 | +0.44 |
| ECB rate momentum, 10% vol target | +0.70 | 8.0% | −33.2% | €213,974 | +0.36 |
| Frozen, 10% vol target, 60-day vol only | +0.61 | 8.3% | −26.2% | €227,385 | +0.27 |
| Frozen, 5% risk per euro | +1.05 | 8.0% | −11.1% | €215,189 | +0.71 |
| Frozen, 15% risk per euro | +0.93 | 21.7% | −38.4% | €2,078,212 | +0.60 |
| Frozen, 20% risk per euro | +0.93 | 28.0% | −47.3% | €5,421,637 | +0.59 |
| Frozen, fixed 1 contract | +0.97 | 3.4% | −5.1% | €94,301 | +0.63 |
| Frozen, fixed 3 contracts | +0.83 | 6.6% | −16.7% | €167,647 | +0.50 |
| Frozen, no interest on cash | +1.00 | 14.1% | −24.2% | €608,654 | +0.66 |
| Frozen, cost 0.5 bp/side | +0.98 | 14.6% | −22.8% | €664,533 | +0.64 |
| Frozen, cost 1 bp/side | +0.91 | 13.5% | −23.2% | €552,762 | +0.57 |
| Frozen, cost 2 bp/side | +0.78 | 11.5% | −25.0% | €393,563 | +0.44 |
| Frozen, start Jan 2002 | +0.92 | 13.7% | −25.7% | €1,255,918 | n/a |
| Frozen, OIS-spliced prices 2005–14 | +0.92 | 11.3% | −20.7% | €383,402 | n/a |
| ECB rate momentum, OIS-spliced prices | +0.93 | 11.5% | −24.2% | €391,564 | n/a |

Frozen spec, account detail:

| Measure | Value |
|---|---|
| Total P&L | +€658,208 on €50,000: +€598,927 trading, +€59,281 interest |
| Realised volatility | 14.2% a year; the rule aims at 10% only when volatility is at its 1999–2007 average |
| Worst drawdown | −22.6% (−€92,081 at its deepest in euros), Jun 2008 to Oct 2008, recovered Oct 2008 |
| Longest time under water | 999 trading days |
| Worst month / best month | −16.2% (Jan 2008) / +31.8% (Nov 2008) |
| Winning months, over cash | 62% |
| Contracts held | average 25.5, range 3 to 57 as equity grew |
| Costs paid | €31,762, about 5% of gross trading profit |
| Direction changes | 6 in 18.7 years; position resized in 104 of 224 months |

Margin deployed (Figure 7, bottom panel):

| Period | Avg contracts | Avg margin | Share of equity | Peak share if margin had scaled with volatility |
|---|---|---|---|---|
| 2008–12 | 13.5 | €3,207 | 1.9% | 10.5% |
| 2013–21 | 22.9 | €5,422 | 1.9% | 2.1% |
| 2022–26 | 43.3 | €10,260 | 1.9% | 6.1% |
| Whole window | 25.5 | €6,034 | 1.9% (peak 2.3%) | 10.5% |

Calendar years, frozen spec:

| Year | Trading P&L € | Interest € | Return | Year-end equity | Avg contracts (+ long, − short) |
|---|---|---|---|---|---|
| 2008 | +37,802 | +2,010 | +79.6% | 89,812 | −2.3 |
| 2009 | +90,099 | +919 | +101.3% | 180,830 | +11.5 |
| 2010 | +36,353 | +889 | +20.6% | 218,073 | +16.8 |
| 2011 | −27,968 | +1,670 | −12.1% | 191,774 | −2.5 |
| 2012 | +76,453 | +530 | +40.1% | 268,758 | +19.3 |
| 2013 | −6,659 | +234 | −2.4% | 262,332 | +21.2 |
| 2014 | +9,542 | +256 | +3.7% | 272,130 | +21.8 |
| 2015 | +5,392 | −289 | +1.9% | 277,234 | +22.3 |
| 2016 | +3,802 | −906 | +1.0% | 280,130 | +23.0 |
| 2017 | +9,345 | −1,015 | +3.0% | 288,460 | +23.5 |
| 2018 | −570 | −1,061 | −0.6% | 286,828 | +23.8 |
| 2019 | −1,060 | −1,200 | −0.8% | 284,569 | +23.8 |
| 2020 | +3,091 | −1,559 | +0.5% | 286,101 | +23.2 |
| 2021 | −8,306 | −1,595 | −3.5% | 276,200 | +11.3 |
| 2022 | +136,194 | +289 | +49.4% | 412,683 | −25.7 |
| 2023 | +54,733 | +14,776 | +16.8% | 482,192 | −37.2 |
| 2024 | +157,109 | +22,004 | +37.1% | 661,304 | +4.6 |
| 2025 | +2,115 | +14,483 | +2.5% | 677,902 | +54.6 |
| 2026 (to Aug) | +21,460 | +8,846 | +4.5% | 708,208 | +25.4 |

![Figure 6. Equity and drawdown, January 2008 to August 2026](figures/fig6_bt50k_equity.png)

*Figure 6. Account equity for the four strategies and v1 as reported (log scale), and the frozen spec's drawdown.*

![Figure 7. Signal, volatility, contracts and margin](figures/fig7_bt50k_signal_vol_margin.png)

*Figure 7. The signal, the contract's volatility against the fixed sizing volatility, contracts held and margin deployed.*

## 5. Robustness

**Regimes.** The result is regime dependent, not universal.

| Sharpe by period | 2008–12 crisis | 2013–19 ZLB/QE | 2020–21 COVID | 2022–26 hikes + cuts |
|---|---|---|---|---|
| Frozen spec | +1.74 | +0.22 | −0.14 | +1.04 |
| Walk-forward threshold | +1.74 | +0.39 | −0.13 | +0.99 |
| ECB rate momentum | +1.74 | +0.22 | −0.16 | +1.05 |
| Long-only | +1.78 | +0.23 | −0.14 | −0.96 |
| v1 as reported | +1.71 | +0.16 | +0.17 | +0.92 |

63% of the account's growth came in 2008–12, 36% in 2022–26 and 1% in the nine years 2013–21. The best 5 months are 37% of trading P&L and the best 10 are 58%.

**What the override adds.** In basis points, each version's override rests on one episode. Gain over the plain rule, one contract, gross, by month-end decision (the P&L is the following month):

| Spec | Decided | Months | Override position | Gain over the rule |
|---|---|---|---|---|
| v2 (frozen) | Sep 2021 – Jun 2022 | 10 | short (rule long) | −8 bp |
| v1 | Oct 2008 | 1 | long (rule short) | +284 bp |
| v1 | Sep 2011 | 1 | long (rule short) | +14 bp |
| v1 | May 2017 | 1 | short (rule long) | +11 bp |
| v1 | Mar 2021 – Apr 2021 | 2 | short (rule long) | +6 bp |
| v1 | Aug 2021 – Jun 2022 | 11 | short (rule long) | +4 bp |

v1's value was October 2008, when the deposit-rate anchor was wrong; the both-rates anchor is already long that month. What is left for v2 is the 2021–22 inflation short: 10 months from September 2021 to June 2022, net −8 bp. Its value depends on the sizing rule:

| Sharpe | One contract | Per-euro sizing | 10% volatility target |
|---|---|---|---|
| Frozen spec | +1.06 | +1.00 | +0.77 |
| ECB rate momentum alone | +1.07 | +1.01 | +0.70 |
| What the override adds | −0.01 | 0.00 | +0.08 |

Under the volatility target, record-low volatility in 2021 put on large inflation shorts while they paid, and the July 2022 loss came on a smaller position. With size fixed per euro that effect goes, and so does the override's value. Read the override as one episode whose value depends on sizing, not as a source of return.

**Threshold.** No longer a knife-edge. On one contract every threshold from 0.1 to 1.5 gives +1.04 to +1.11, against +1.07 for the anchor alone; v1 ranged from +0.74 to +1.09, with 0.5 at the peak. A walk-forward threshold picks 1.5 until 2011 and 0.3 from 2012, and scores +1.01 in the account.

**Sizing.** The volatility target worked against the signal. Split by the v1 sizing volatility at each month-end:

| Volatility third | Months | Avg sizing volatility | Contracts per €50,000, 10% target | Contracts per €50,000, per-euro | P&L per contract, bp a month | Sharpe per contract | Share of one-contract P&L |
|---|---|---|---|---|---|---|---|
| Low | 75 | 26 bp | 7.7 | 4.1 | −0.3 | −0.15 | −2% |
| Middle | 74 | 41 bp | 5.1 | 4.1 | +3.7 | +1.02 | 20% |
| High | 75 | 83 bp | 2.7 | 4.1 | +15.1 | +1.56 | 82% |

*Frozen spec on one contract, gross, January 2008 to August 2026.*

With the same signals, per-euro sizing scores +1.00 against +0.77 at the 10% target and +0.61 with unblended 60-day volatility. The cost is risk. Realised volatility is 14.2% a year, not 10%, because the account holds full size through 2008 and 2022–23, when the contract's volatility peaked at 7 and 4 times σ. The worst month was the first, January 2008 (−16.2%). At 5% risk per euro, volatility is 6.8% and the worst drawdown −11.1%; at 20% they are 30.5% and −47.3%. Any further sizing variant tested on this sample counts as another trial.

**Synthetic price error.** Against 20 days of real Eurex settlements (27 August to 23 September 2026, contracts matched by expiry month) the synthetic is −3.3 bp off on average, with a standard deviation of 8.5 bp; the error persists (day-to-day autocorrelation 0.86) and daily changes correlate 0.63. Added to the whole history as a persistent random error, signals unchanged, an error of that size gives these one-contract Sharpe ratios:

| One-contract Sharpe | No added error | Measured size, median (5th–95th) | Twice the size, median |
|---|---|---|---|
| Frozen spec | +1.06 | +0.74 (0.70–0.78) | +0.47 |
| ECB rate momentum, both rates | +1.07 | +0.75 (0.71–0.78) | +0.47 |
| v1 spec | +1.09 | +0.76 (0.71–0.82) | +0.48 |
| ECB rate momentum, deposit rate only | +0.85 | +0.59 (0.55–0.63) | +0.37 |
| Long-only | +0.27 | +0.19 (0.18–0.20) | +0.12 |

The bound is pessimistic, since the added error only adds variance, and the ranking does not change. Quote the frozen spec's one-contract Sharpe as roughly 0.7 to 1.1, not as a point.

**No-skill nulls**, the stronger test (the long/short path shifted or block-shuffled in time, position sizes left on their dates):

| | Observed Sharpe | Null mean | Null 95th pct | p, circular shift | p, block permutation |
|---|---|---|---|---|---|
| Frozen spec | +0.94 | +0.15 | +0.57 | 0 of 212 | 0 of 3,000 |
| Walk-forward threshold | +0.95 | +0.17 | +0.58 | 0 of 212 | 0.000 |
| ECB rate momentum | +0.95 | +0.20 | +0.56 | 0 of 212 | 0.001 |

**Block bootstrap** (12-month blocks, 10,000 paths of 224 months, account returns). It resamples the strategy's own months, so every path contains 2008 and 2022: it shows how much the order of returns matters, not that the edge is proven.

| | Frozen spec | Walk-forward | ECB rate momentum | Long-only |
|---|---|---|---|---|
| Sharpe, 5th / 50th / 95th percentile | +0.50 / +0.94 / +1.37 | +0.51 / +0.96 / +1.38 | +0.48 / +0.95 / +1.38 | −0.33 / +0.30 / +0.90 |
| P(beats long-only) / P(beats ECB rate momentum) | 98% / 50% | 98% / 54% | | |
| Final equity, 5th / 50th / 95th | €139k / €632k / €4,975k | €142k / €645k / €5,055k | €130k / €640k / €5,268k | €19k / €109k / €844k |
| P(ending below €50,000) | 0.1% | 0.1% | 0.1% | 24% |
| Max drawdown, median / 5th / 1st percentile | −17% / −28% / −33% | −18% / −29% / −35% | −18% / −30% / −36% | −48% / −78% / −86% |
| P(drawdown worse than 20% / 30%) | 27% / 3% | 32% / 4% | 37% / 5% | 97% / 84% |
| First-year P&L, 5th / 50th / 95th | −€3.0k / +€1.9k / +€50.7k | −€3.2k / +€2.1k / +€50.7k | −€5.0k / +€1.8k / +€50.7k | −€16.4k / +€0.5k / +€36.6k |
| P(loss after 1 year / 5 years) | 24% / 5% | 20% / 5% | 26% / 7% | 40% / 37% |

**Deflated Sharpe** (expected best-of-N Sharpe under the null: 0.62 for the 50 variants on file, 0.69 for about 105 looks at this sample in all): frozen spec 0.96 / 0.91, walk-forward threshold 0.96 / 0.91, ECB rate momentum 0.96 / 0.91, long-only 0.08 / 0.04. Monthly returns have skew +2.34 and kurtosis 16.7.

![Figure 8. Monte Carlo, full window](figures/fig8_bt50k_montecarlo.png)

*Figure 8. Bootstrap Sharpe with medians, bootstrap equity paths, bootstrap drawdown, and the no-skill shuffle test.*

**Costs.** Sharpe +0.98 at 0.5 bp per side (one full tick), +0.91 at 1 bp and +0.78 at 2 bp. Rolls are 89% of the contract-sides traded: the account rolls about 25 contracts four times a year, against 6 direction changes in 18.7 years.

**Instrument.** On the OIS-spliced prices for 2005–14 the frozen spec is +0.92 (€383k) against +1.00 (€708k); ECB rate momentum goes from +1.01 to +0.93.

**Margin and cash.** Margin is never the constraint. It averaged 1.9% of equity and peaked at 2.3%; with margin scaled up with volatility the peak is 10.5%. Interest on the rest added €59,281: CAGR 15.0% against 14.1% without it, with the Sharpe over cash unchanged (+1.00 and +1.00). Negative rates in 2015–22 cost little because they were shallow.

## 6. Verdict
**Context-dependent: accept as a diversifier, and read it as ECB rate momentum.** After the review's four changes the account earns +1.00 over cash (15.0% CAGR, −22.6% worst drawdown) against +0.85 for v1 as reported. The gain comes from the corrected anchor and a sizing rule that no longer works against the signal; the override adds 0.00 Sharpe.

Caveats, in order of importance:

1. **Multiple testing.** About 105 looks have been taken at the same 224 months, including the review's and the v2 choices. The deflated Sharpe at that count is 0.91.
2. **The five inputs were chosen after seeing the review's factor table.** The choice rests on economics, but it is not blind. The override fires in 10 months of 224 and adds nothing, so the inputs matter little to the result.
3. **Prices are synthetic.** The measured pricing error puts the one-contract Sharpe at roughly 0.7 to 1.1. Real ICE prices exist from December 2018 (Databento); rerunning on them is the check that matters most.
4. **Regime dependence.** Three ECB cycles in the sample; on-hold months earn +2.1 bp a month on one contract; 2013–21 added 1% of the growth.
5. **Risk is above the nominal 10%.** Realised volatility 14.2%, worst month −16.2%. Size fixed per euro means full size in a crisis; 5% risk per euro halves both.
6. **Uncorrelated, not a hedge** (appendix B). Present it as an independent return stream.
7. **Hold-out.** Every month from September 2026 is out of sample; nothing in v2 was fitted to it.
