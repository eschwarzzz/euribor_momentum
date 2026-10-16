# Euribor macro strategy: status as of 25 September 2026

## 1. What exists

**Instrument.** Synthetic 3M Euribor future, 2nd quarterly contract, daily from Dec 1998. Futures rate = spot 3M Euribor (Bundesbank daily fixings) + risk-free forward premium from the ECB AAA curve (2004-09 onward; deposit curve before). Converges exactly to 100 − fixing at expiry. A second construction from the EONIA swap (OIS) curve exists for 2005-06 to 2014-06. Real Eurex settlements are being collected from 27 Aug 2026 (`collect_eurex.py`, run every 2–3 weeks).

**Data.** ECB (policy rates, M1/M3, bank debt holdings, yield curves, CISS, balance sheet, long-term yields), Eurostat (HICP incl. the 2026 ECOICOP-v2 series, ESI, fixed investment by asset, capital-goods output by industry, construction), Bundesbank (Euribor curve, EONIA swaps), BIS (euro-area banks' USD vs EUR cross-border claims), US Treasury TIC (euro-area holdings of Treasuries), FRED (US rates), policyuncertainty.com (Europe EPU), ECB Bank Lending Survey. All free; keys and quirks recorded in memory and script headers.

**Signals.** Monthly, point-in-time, publication lags applied. Groups: rates/policy (R), money (M, now dropped), debt holdings (D, fitted models only), inflation (I), sentiment/political stress (S), credit demand (C, rejected). Composite = equal-weighted mean of clipped expanding z-scores with signs fixed from theory. Fitted alternatives: ridge, lasso, logit, walk-forward, monthly refit.

## 2. What the evidence says (Jan 2008 – Aug 2026, 224 months, after costs)

| Strategy | Sharpe | Ann. P&L | Max DD | Status |
|---|---|---|---|---|
| Long-only 2nd contract | +0.27 | +18 bp | −470 bp | benchmark |
| 12M price trend | +0.50 | +35 bp | −243 bp | benchmark |
| **Follow-the-ECB** (policy momentum) | **+0.85** | +58 bp | −162 bp | the backbone |
| Composite R+M+I+S, ±1 | +0.79 | +55 bp | −140 bp | superseded |
| Composite R+I+S (money dropped) | +0.81 | +56 bp | −181 bp | current composite |
| **ECB anchor + R+I+S override (|score| > 0.5)** | **+1.09** in-sample, **+0.87** walk-forward threshold | +75 bp | −137 bp | current specification |
| Ridge / logit / nested ridge | +0.58 / +0.67 / +0.61 | | | inferior, unproven |
| Credit-demand block (capex by industry, GFCF, BLS) | +0.42 alone; hurts the composite | | | rejected |
| Kalman-filtered features | no out-of-sample gain; override worse | | | rejected |
| Placebo (shuffled target) | −0.21 | | | pipeline clean |

Factor verdicts: rates/policy carries the result; inflation adds the 2021–22 short campaign; sentiment adds two crisis longs (Oct 2008, Sep 2011); money supply and capex/credit demand both fail the same way (real-economy weakness reads as "cuts" while inflation forbids cuts); debt holdings add ~0.1 Sharpe inside fitted models only.

The override fired 16 times in 18.7 years: two stress longs, one 2017 short, and thirteen inflation-driven shorts from Mar 2021 to Jun 2022. Relative to the rule they earned +319 bp, of which +284 bp is October 2008. With the threshold chosen out of sample the override adds 0.02–0.03 Sharpe over the plain rule.

## 3. Validation done

- Placebo ≈ 0; circular-shift and block-permutation nulls give p ≤ 0.014 for the composite.
- Block bootstrap: composite Sharpe 90% interval +0.27 to +1.19; beats long-only in 85% of paths, beats the ECB rule in 42%.
- Deflated Sharpe for 45 trials: composite 0.87, scaled composite 0.98, ridge α=10 0.51.
- CPCV (10 groups, purge + embargo): every backtest path positive for ridge and logit (+0.25 to +0.69).
- Threshold: 0.5 chosen on either half of the sample; test-half Sharpe +0.64 vs rule +0.62; walk-forward +0.87 vs +0.85.
- Instrument: OIS-based and government-curve synthetics agree at monthly frequency (corr 0.90); government version overstated the 2005–14 rally by ~150 bp; Sharpe rankings unchanged on the spliced instrument.
- Real data: 20 Eurex days show the synthetic is level-unbiased but noisy day to day (daily corr 0.18, 5-day 0.46). All models were short in Sep 2026 and made +55 bp on real settlements.
- Trading: anchored version flips 0.7 times a year plus 4 rolls; cost 0.5 bp/side; drag ≈ 5 bp/yr; composite survives 2 bp/side at +0.54.

## 4. What is not proven

1. Prices are synthetic before 2019; monthly measurement noise ≈ 10–20 bp; zero-rate-era results are noise.
2. The override's evidence is two episodes; its out-of-sample edge over the rule is ~0.02 Sharpe.
3. Feature menu chosen with hindsight; no untouched hold-out remains inside the sample. About 70 trials run in total.
4. Three ECB cycles in the sample; performance is regime-dependent (strong when the ECB moves, flat at the lower bound).

## 5. Current specification (frozen)

Month-end: compute R, I, S group scores; score = mean. Position for next month = follow-the-ECB (long if the deposit rate was cut in the last 3 months, short if raised, else unchanged) unless |score| > 0.5, in which case position = sign(score). Trade the 2nd quarterly contract, roll on the front expiry. No further tuning on this sample.

## 6. Next steps

1. Databento IFLL.IMPACT pull (ICE Euribor, Dec 2018 onward): validate the synthetic, rerun on real prices, calibrate measurement error.
2. Keep the Eurex collector running; treat every month from Sep 2026 as the true hold-out.
3. Bloomberg export at UF for 1999–2018 real prices if the Databento validation passes.
4. Paper-trade the frozen specification in trade-ngin only after step 1.

## 7. Files

Reorganised on 15 October 2026 into the `euribor/` package (`config`, `sources`, `futures`, `features`, `signals`, `backtest`, `montecarlo`, `account`, `charts`, `reports`, `render`; run as `python -m euribor <step>` or `make all`) and `research/` (`threshold`, `divergence`, `corrections`, `credit_demand`, `kalman`, `compare_instruments`, `trend_correlation`). Data in `data/raw` (sources) and `data/processed` (synthetic futures, features); tables in `results/` (CSV per test, logs in `results/logs`); figures `fig1`–`fig11` in `reports/figures`. Reports: `REPORT.md` (original six-section test), `BACKTEST_50K.md` (€50,000 account, six sections, figures 6–8, cost 0.3 bp per side from 6 October; the 0.5 bp run is archived in `results/archive_0p5bp/`), `BACKTEST_50K_APPENDIX.md` (A = last five years as a fresh account from Sep 2021, figures 9–10; B = correlation with the AlgoGators trend-following backtest, +0.01 monthly over Apr 2011 – Apr 2026, figure 11), `EU_rate_backtest.pdf` (PDF export of the account report). The rewritten pipeline reproduces every table of the original scripts byte for byte; the original flat scripts are in the first commit of the repository.
