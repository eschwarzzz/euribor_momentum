# Euribor macro strategy: status as of 28 October 2026

## 1. What exists

**Instrument.** Synthetic 3M Euribor future, 2nd quarterly contract, daily from Dec 1998. Futures rate = spot 3M Euribor (Bundesbank daily fixings) + risk-free forward premium from the ECB AAA curve (2004-09 onward; deposit curve before). Converges exactly to 100 − fixing at expiry. A second construction from the EONIA swap (OIS) curve exists for 2005-06 to 2014-06. Real Eurex settlements are being collected from 27 Aug 2026 (`python -m euribor collect-eurex`, run every 2–3 weeks).

**Data.** ECB (policy rates, EONIA and €STR, M1/M3, bank debt holdings, yield curves, CISS, balance sheet, long-term yields), Eurostat (HICP incl. the 2026 ECOICOP-v2 series, ESI, fixed investment by asset, capital-goods output by industry, construction), Bundesbank (Euribor curve, EONIA swaps), BIS (euro-area banks' USD vs EUR cross-border claims), US Treasury TIC (euro-area holdings of Treasuries), FRED (US rates), policyuncertainty.com (Europe EPU), ECB Bank Lending Survey. All free; keys and quirks recorded in memory and script headers.

**Signals.** Monthly, point-in-time, publication lags applied. Groups: rates/policy (R), money (M, dropped), debt holdings (D, fitted models only), inflation (I), sentiment/political stress (S), credit demand (C, rejected). Composite = equal-weighted mean of clipped expanding z-scores with signs fixed from theory. Fitted alternatives: ridge, lasso, logit, walk-forward, monthly refit.

**Review.** An external review (18 October 2026) recommended four changes: read the ECB rule on both policy rates, credit the override only for what it adds, change the sizing, cut the factor list. All four are in specification v2 (section 5), with its smaller suggestions (cash interest, synthetic-error range, regime dependence stated up front, bootstrap reworded, the inconsistencies below corrected).

## 2. What the evidence says (Jan 2008 – Aug 2026, 224 months, after costs)

| Strategy | Sharpe | Ann. P&L | Max DD | Status |
|---|---|---|---|---|
| Long-only 2nd contract | +0.27 | +18 bp | −470 bp | benchmark |
| 12M price trend | +0.50 | +35 bp | −243 bp | benchmark |
| Follow-the-ECB on the deposit rate alone | +0.85 | +58 bp | −162 bp | v1 anchor, superseded |
| **Follow-the-ECB on both policy rates** | **+1.07** | +73 bp | −137 bp | the backbone |
| Composite R+M+I+S, ±1 | +0.79 | +55 bp | −140 bp | superseded |
| v1: DFR anchor + 23-series R+I+S override (\|score\| > 0.5) | +1.09 in-sample, +0.88 walk-forward threshold | +75 bp | −137 bp | superseded |
| **v2: both-rates anchor + five-input override (\|score\| > 0.5)** | **+1.06**, +1.08 walk-forward threshold | +73 bp | −137 bp | current specification |
| Ridge / logit / nested ridge | +0.58 / +0.67 / +0.61 | | | inferior, unproven |
| Credit-demand block (capex by industry, GFCF, BLS) | +0.42 alone; hurts the composite | | | rejected |
| Kalman-filtered features | no out-of-sample gain; override worse | | | rejected |
| Placebo (shuffled target) | −0.21 | | | pipeline clean |

As a €50,000 account (v2, per-euro sizing, cash at EONIA/€STR, 0.3 bp per side): Sharpe +1.00 over cash, CAGR 15.0%, realised volatility 14.2%, worst drawdown −22.6%, €708k at the end. v1 as reported: +0.85, 9.0%, −20.1%, €256k.

The anchor fix changes the position in one month only, October 2008 (next month +142 bp). It removes the override's main episode: v1's override earned +284 bp of its total in that month. v2's override fires in 10 months, all September 2021 to June 2022, and nets −8 bp on one contract. Its value depends on sizing: −0.01 Sharpe on one contract, 0.00 with per-euro sizing, +0.08 under the v1 volatility target. Read the strategy as ECB rate momentum plus a sizing rule.

Factor verdicts (review appendix B): rate momentum and the HICP level carry information after 2012; unemployment change, CISS, ESI and the periphery spread work only in 2008–12; the slope, core HICP change, CISS change and periphery policy uncertainty add nothing; the sentiment group stopped working after 2012 and fought the inflation group in 2022–26. Money supply and capex/credit demand fail the same way (real-economy weakness reads as "cuts" while inflation forbids cuts); debt holdings add ~0.1 Sharpe inside fitted models only.

## 3. Validation done

- Placebo ≈ 0; circular-shift and block-permutation nulls give p < 0.001 for v2 on one contract and in the account.
- Block bootstrap, account: v2 Sharpe 90% interval +0.50 to +1.37; beats long-only in 98% of paths and the plain ECB rule in 50%. Every resampled path contains 2008 and 2022, so this measures the order of returns, not the edge.
- Deflated Sharpe, account: 0.96 for the 50 variants on file, 0.91 for about 105 looks at the sample.
- CPCV (10 groups, purge + embargo): every backtest path positive for ridge and logit (+0.25 to +0.69).
- Threshold: for v2, every threshold from 0.1 to 1.5 gives +1.04 to +1.11 on one contract (rule alone +1.07); v1's 0.5 was a knife-edge (+0.74 to +1.09).
- Instrument: OIS-based and government-curve synthetics agree at monthly frequency (corr 0.90); government version overstated the 2005–14 rally by ~150 bp; Sharpe rankings unchanged on the spliced instrument.
- Real data: 20 Eurex days (27 Aug – 23 Sep 2026), contracts matched by expiry month: the synthetic is −3.3 bp off on average, error sd 8.5 bp, AR(1) 0.86; daily change correlation 0.63. (The 25 September note gave 0.18, from comparing by rank rather than by expiry.) Added to the whole history, an error of that size puts the v2 one-contract Sharpe at 0.70–0.78; quote it as roughly 0.7 to 1.1.
- September 2026: every version was short. On raw settlements, short the 2nd contract from 31 Aug to 30 Sep, rolling at the 14 Sep expiry, made +13.5 bp before costs (+14 to +17 bp on other roll days). The 25 September note's "+55 bp" was wrong; no contract or roll gives it.
- Trading: v2 flips 6 times in 18.7 years plus 4 rolls a year; costs +0.98 Sharpe at 0.5 bp/side, +0.78 at 2 bp/side in the account.
- Trend book: monthly correlation 0.00 (bootstrap −0.08 to +0.13), uncorrelated, not a hedge.

## 4. What is not proven

1. Prices are synthetic before 2019; the measured error alone takes the one-contract Sharpe from 1.06 to about 0.74.
2. The override adds nothing measurable. The five inputs were chosen on economics after reading the review's factor table, so the choice is not blind.
3. About 105 looks at the same 224 months; no untouched hold-out remains inside the sample.
4. Three ECB cycles in the sample; performance is regime-dependent (on-hold months earn +2.1 bp a month against +10.4 bp after a move; 2013–21 added 1% of the account's growth).
5. Per-euro sizing runs 14% realised volatility, not 10%, because it holds full size in a crisis.

## 5. Current specification (v2, frozen 28 October 2026)

Month-end: anchor = −sign(3M change in the MRO + 3M change in the deposit facility rate), else unchanged. Score = equal-weight mean of the signed, clipped (±3) expanding z-scores of the deposit-rate 3M change (−), HICP yoy (−), core HICP yoy (−), unemployment 6M change (+) and the CISS level (+). Position for next month = anchor unless |score| > 0.5, in which case position = sign(score). Trade the 2nd quarterly contract, roll on the front expiry. Account: contracts = round(10% × equity ÷ (49.1 bp × €2,500)), resized monthly; 49.1 bp is the contract's average 60-day volatility over 1999–2007. No further tuning on this sample; any further variant counts as a trial.

## 6. Next steps

1. Databento IFLL.IMPACT pull (ICE Euribor, Dec 2018 onward): validate the synthetic, rerun on real prices, calibrate measurement error.
2. Keep the Eurex collector running; treat every month from Sep 2026 as the true hold-out.
3. Bloomberg export at UF for 1999–2018 real prices if the Databento validation passes.
4. Answer the review's open questions: what the strategy should do when the ECB is on hold, and whether 10% risk per euro is the right level given 14% realised volatility.
5. Paper-trade the frozen specification in trade-ngin only after step 1.

## 7. Files

`euribor/` package (`config`, `sources`, `futures`, `features`, `signals`, `backtest`, `montecarlo`, `account`, `charts`, `reports`, `render`; run as `python -m euribor <step>` or `make all`) and `research/` (`threshold`, `divergence`, `corrections`, `credit_demand`, `kalman`, `compare_instruments`, `trend_correlation`; `threshold` and `trend_correlation` were rerun on v2, the others last ran on the v1 deposit-rate anchor). Data in `data/raw` (sources) and `data/processed` (synthetic futures, features); tables in `results/` (CSV per test, logs in `results/logs`; `synthetic_error*.{csv,json}` hold the pricing-error range); figures `fig1`–`fig11` in `reports/figures`. Reports: `REPORT.md` (original six-section test, benchmark updated), `BACKTEST_50K.md` (€50,000 account for v2 with v1 as a comparison row, six sections, figures 6–8), `BACKTEST_50K_APPENDIX.md` (A = last five years as a fresh account from Sep 2021, figures 9–10; B = correlation with the AlgoGators trend-following backtest, figure 11), `EU_rate_backtest.pdf` (PDF export of the account report). The review itself is outside the repository.
