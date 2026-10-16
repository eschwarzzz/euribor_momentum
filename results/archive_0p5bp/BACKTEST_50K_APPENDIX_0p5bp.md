# Euribor macro strategy: appendices to the €50,000 account backtest

Cut from `BACKTEST_50K.md` on 1 October 2026. Appendix A is the last-five-years account (September 2021 to August 2026); Appendix B is the correlation with the trend-following book. Section numbers such as "section 6" refer to the main report.

---

# Appendix A. The last five years: September 2021 to August 2026

A new €50,000 account opened on 1 September 2021, same rules, sizing, costs and margin as the main test. 60 months, covering the 2022–23 hiking cycle, the 2024–25 cuts and the June 2026 hike. The walk-forward threshold is 0.5 in every one of these years, so it is the frozen spec here and is not shown separately. Output: `results/bt50k_5y_*.csv`, figures `results/fig9_bt50k_5y_account.png` and `results/fig10_bt50k_5y_montecarlo.png`. Both pages in one file: `results/bt50k_5y_pages.pdf` (page 1 account, page 2 Sharpe and Monte Carlo analysis).

## A1. Results

| Variant | Sharpe | CAGR | Max DD | Final equity | Sharpe vs long-only |
|---|---|---|---|---|---|
| **Frozen spec, 10% vol target** | **+0.88** | **10.7%** | **−17.1%** | **€83,741** | **+1.86** |
| Follow-the-ECB only, 10% vol | +0.63 | 7.4% | −24.5% | €71,973 | +1.61 |
| Long-only, 10% vol (benchmark) | −0.98 | −12.6% | −49.5% | €25,253 | 0 |
| 12M trend, 10% vol (benchmark) | +0.44 | 4.8% | −27.6% | €63,558 | +1.42 |
| Frozen, 5% vol target | +0.93 | 5.7% | −8.6% | €66,394 | +1.91 |
| Frozen, 15% vol target | +0.86 | 15.7% | −25.2% | €105,046 | +1.84 |
| Frozen, 20% vol target | +0.86 | 20.6% | −33.7% | €129,173 | +1.84 |
| Frozen, 60-day vol only | +0.85 | 10.8% | −20.4% | €84,014 | +1.83 |
| Frozen, fixed 1 contract | +1.00 | 4.0% | −4.9% | €61,051 | +1.98 |
| Frozen, fixed 3 contracts | +1.03 | 10.5% | −13.6% | €83,154 | +2.01 |
| Follow-the-ECB, fixed 3 contracts | +0.99 | 10.4% | −15.5% | €82,812 | +1.97 |
| Frozen, cost 1 bp/side | +0.79 | 9.7% | −18.8% | €80,083 | +1.77 |
| Frozen, cost 2 bp/side | +0.65 | 7.8% | −19.8% | €73,355 | +1.63 |

Frozen spec, account detail:

| Measure | Value |
|---|---|
| Total P&L | +€33,741 on €50,000 |
| Realised volatility | 12.4% a year against the 10% target |
| Worst drawdown | −17.1%, from October 2024 to March 2026, not yet recovered at end-August 2026 |
| Worst month / winning months | −13.4% (March 2026) / 68% |
| Contracts held | average 5.3, range 2 to 11 |
| Margin deployed | average €1,264 (1.8% of equity), peak €2,607; peak share 4.3% in September 2021 |
| Costs paid | €3,613 |
| Direction changes | 2 (to long at end-June 2024, back to short at end-June 2026); override fired in 11 months, all September 2021 to July 2022 |

By position run:

| Run | Months | 2nd contract move | P&L |
|---|---|---|---|
| Short, Sep 2021 to Jun 2024 | 34 | −410 bp | +€31,464 |
| Long, Jul 2024 to Jun 2026 | 24 | +21 bp | −€1,883 |
| Short, Jul to Aug 2026 | 2 | −34 bp | +€4,159 |

By calendar year:

| Year | P&L € | Return | Year-end equity | Avg contracts (+ long, − short) | Avg margin, share of equity |
|---|---|---|---|---|---|
| 2021 (Sep–Dec) | +1,135 | +2.3% | 51,135 | −8.5 | 3.9% |
| 2022 | +13,539 | +26.5% | 64,674 | −3.8 | 1.6% |
| 2023 | +2,688 | +4.2% | 67,362 | −2.8 | 1.0% |
| 2024 | +19,493 | +28.9% | 86,854 | +0.5 | 1.8% |
| 2025 | +58 | +0.1% | 86,913 | +6.6 | 1.8% |
| 2026 (Jan–Aug) | −3,172 | −3.6% | 83,741 | +4.0 | 1.9% |

![Figure 9. Last five years: account page](results/fig9_bt50k_5y_account.png)

*Figure 9. New €50,000 account from September 2021: equity, signal, volatility, contracts and margin.*

## A2. Sharpe analysis and Monte Carlo

Sharpe by calendar year (2021 = Sep–Dec, 2026 = Jan–Aug):

| Year | Frozen spec, 10% vol | Follow-the-ECB, 10% vol | Long-only, 10% vol | Frozen spec, 1 contract | Follow-the-ECB, 1 contract |
|---|---|---|---|---|---|
| 2021 | +0.82 | −1.54 | −1.54 | +0.55 | −1.27 |
| 2022 | +1.59 | +0.92 | −1.80 | +1.82 | +1.89 |
| 2023 | +0.38 | +0.50 | −0.29 | +0.50 | +0.50 |
| 2024 | +2.23 | +2.30 | −1.07 | +2.26 | +2.26 |
| 2025 | +0.05 | +0.05 | +0.01 | +0.01 | +0.01 |
| 2026 | −0.30 | −0.35 | −1.43 | +0.36 | +0.36 |
| **All 60 months** | **+0.88** | **+0.63** | **−0.98** | **+0.98** | **+0.97** |

Block bootstrap, 12-month blocks, 10,000 paths of 60 months:

| | Frozen spec | Follow-the-ECB | Long-only |
|---|---|---|---|
| Sharpe, 5th / 50th / 95th percentile | +0.25 / +1.01 / +1.77 | −0.17 / +0.65 / +1.57 | −1.59 / −1.13 / −0.51 |
| P(Sharpe > 0) | 99% | 90% | 0% |
| P(beats long-only) / P(beats ECB rule) | 100% / 80% | | |
| Final equity, 5th / 50th / 95th | €55k / €84k / €122k | €43k / €72k / €118k | €18k / €25k / €37k |
| P(ending below €50,000) | 2% | 12% | 100% |
| Max drawdown, median / 5th / 1st percentile | −13% / −21% / −26% | −17% / −33% / −39% | −52% / −66% / −70% |
| First-year P&L, 5th / 50th / 95th | −€5.4k / +€7.3k / +€13.4k | −€6.1k / +€4.5k / +€17.3k | −€12.1k / −€6.9k / +€2.3k |
| P(loss after 1 year) | 20% | 34% | 87% |

No-skill nulls (6-month blocks, because 60 months hold only five 12-month blocks):

| | Observed Sharpe | Null mean | Null 95th pct | p, circular shift | p, block permutation |
|---|---|---|---|---|---|
| Frozen spec | +0.97 | +0.10 | +0.70 | 0 of 48 | 0.008 |
| Follow-the-ECB | +0.64 | −0.23 | +0.38 | 0 of 48 | 0.009 |

Deflated Sharpe on 60 months (45 / 70 trials): frozen spec 0.79 / 0.77, follow-the-ECB 0.59 / 0.56. Monthly returns have skew −0.88 and kurtosis 8.7.

![Figure 10. Monte Carlo, last five years](results/fig10_bt50k_5y_montecarlo.png)

*Figure 10. The same four Monte Carlo panels for the 60-month window.*

## A3. Reading

1. **One trade made the money.** 93% of the P&L is the 34-month short through the hiking cycle. The two-year long through the cuts lost €1,883 even though the contract rose 21 bp, because March 2026 cost €11,919 on 10 contracts. The best 5 months are 68% of the P&L.
2. **The override added nothing on equal sizing.** With 3 fixed contracts the frozen spec ends at €83,154 and plain follow-the-ECB at €82,812 (Sharpe +1.03 and +0.99; +0.98 and +0.97 on one contract). The 2nd contract moved −2 bp net over the 11 override months. The gap at a 10% target (+0.88 against +0.63) comes from sizing: the override was short 6 to 9 contracts from September 2021 to March 2022, when its gains came, and 3 contracts in July 2022, when the contract bounced 50 bp against it.
3. **Fixed contracts beat volatility targeting in this window.** Three fixed contracts made the same money as the 10% target with a −13.6% drawdown instead of −17.1% and a worst month of −6.9% instead of −13.4%. Low volatility in late 2025 took the target to 10 and 11 contracts just before the March 2026 move.
4. **This window is better than typical, not typical.** The rolling 60-month Sharpe of the 2008-start account is +0.95 now against a median of +0.56 across 165 windows (range −0.07 to +1.71); the current window beats 76% of them. Five years with a full hiking cycle and a cutting cycle are the conditions the rule is built for.
5. **Sixty months, three position runs.** The shuffle tests reject luck (p = 0.008), but with two direction changes they have little to work with, and the bootstrap interval is wide: +0.25 to +1.77.
6. **Prices are still synthetic here, and this is where they are weakest.** The synthetic takes its forward premium from the AAA government curve, and in 2022–23 short government yields moved away from Euribor-linked rates. Real ICE prices exist for this whole window (Databento, December 2018 onward); rerunning this page on them is the check that matters most.

**Verdict for the window: context-dependent.** If the ECB keeps moving rates, the last five years support the plain follow-the-ECB rule at about Sharpe +1 on fixed contracts; they give no support for the override beyond the sizing effect, and none for volatility targeting over a fixed position. 13 further account variants were run for this page; no parameter was changed.

---

# Appendix B. Correlation with the trend-following book

Does the Euribor strategy add something the rest of the portfolio does not already have? Tested against the AlgoGators trend-following backtest (run `TREND_FOLLOWING_20260505_010930_346`, 34 CME markets, per-market daily P&L in dollars from `trend_risk/.../phase2/pnl_panel.csv`). Window 4 April 2011 to 30 April 2026: 3,857 days, 181 months. Euribor side: frozen spec on one contract unless stated. Script `portfolio_correlation.py`, output `results/trendcorr_*.csv`, `results/trendcorr.json`, figure `results/fig11_bt50k_trend_correlation.png`.

## B1. Correlations

Frozen spec, one contract, against the trend book and its sleeves:

| Trend book | Daily (3,857) | Weekly (787) | Monthly (181) | Quarterly (61) | Annual (16) |
|---|---|---|---|---|---|
| Whole book | −0.02 | −0.01 | **+0.01** | −0.06 | −0.16 |
| US rates sleeve (ZT, ZF, ZN, UB) | +0.02 | +0.02 | 0.00 | −0.05 | −0.09 |
| Currency sleeve (9 pairs) | +0.02 | +0.07 | +0.09 | −0.04 | −0.71 |
| Everything except rates | −0.03 | −0.02 | +0.01 | −0.05 | −0.15 |

Monthly correlation for the other Euribor versions:

| Euribor version | Whole book | US rates sleeve | Currency sleeve | Everything except rates |
|---|---|---|---|---|
| Frozen spec, 1 contract | +0.01 | 0.00 | +0.09 | +0.01 |
| Frozen spec, €50,000 account (10% vol target) | +0.04 | +0.03 | +0.13 | +0.04 |
| Follow-the-ECB, 1 contract | 0.00 | +0.01 | +0.09 | 0.00 |

Monthly correlation by sub-period and its sampling range (block bootstrap, 12-month blocks, 10,000 draws):

| | 2011–15 (57 months) | 2016–20 (60) | 2021–26 (64) | Full window | Bootstrap 5th to 95th percentile |
|---|---|---|---|---|---|
| Whole book | +0.09 | +0.04 | −0.02 | +0.01 | −0.07 to +0.13 |
| US rates sleeve | +0.02 | −0.14 | +0.16 | 0.00 | −0.10 to +0.14 |
| Currency sleeve | | | | +0.09 | −0.02 to +0.25 |

The rolling 36-month correlation with the whole book stays between −0.22 and +0.33 throughout, inside the range two unrelated series would produce (Figure 11, top).

![Figure 11. Correlation with the trend-following book](results/fig11_bt50k_trend_correlation.png)

*Figure 11. Rolling 36-month correlation, and each year's P&L for both strategies in units of own volatility.*

## B2. Year by year

P&L in each strategy's own units, and scaled by its own annual volatility so the two are comparable (2011 from April, 2026 to April):

| Year | Trend book $ | Trend book, vol units | Euribor bp | Euribor, vol units |
|---|---|---|---|---|
| 2011 | +1,051 | +0.02 | −12 | −0.23 |
| 2012 | +12,270 | +0.29 | +167 | +3.11 |
| 2013 | +7,754 | +0.18 | −13 | −0.23 |
| 2014 | −44,736 | −1.05 | +16 | +0.31 |
| 2015 | −15,580 | −0.36 | +9 | +0.16 |
| 2016 | −21,000 | −0.49 | +5 | +0.09 |
| 2017 | +49,519 | +1.16 | +24 | +0.44 |
| 2018 | −23,654 | −0.55 | −2 | −0.04 |
| 2019 | +37,388 | +0.87 | −3 | −0.05 |
| 2020 | +84,581 | +1.98 | +4 | +0.08 |
| 2021 | +83,290 | +1.95 | 0 | 0.00 |
| 2022 | −7,008 | −0.16 | +216 | +4.03 |
| 2023 | +22,341 | +0.52 | +63 | +1.18 |
| 2024 | +2,261 | +0.05 | +141 | +2.63 |
| 2025 | +15,763 | +0.37 | +1 | +0.01 |
| 2026 | +20,508 | +0.48 | −32 | −0.60 |

Euribor in the trend book's extreme months:

| Months | Trend book mean | Euribor mean | Euribor months positive |
|---|---|---|---|
| Trend book's 15 worst | −$19,623 | +0.5 bp | 47% |
| Trend book's 15 best | +$29,481 | +3.9 bp | 67% |
| All 181 | +$1,242 | +3.2 bp | 61% |

## B3. Combination

Each stream scaled to the same monthly volatility, then weighted (monthly, April 2011 to April 2026):

| Trend / Euribor risk weight | Sharpe | Worst drawdown, in annual volatilities |
|---|---|---|
| 100 / 0 | +0.35 | −2.43 |
| 80 / 20 | +0.51 | −2.16 |
| 50 / 50 | +0.75 | −1.26 |
| 0 / 100 | +0.72 | −1.02 |

## B4. Reading

**Accepted: the Euribor strategy is uncorrelated with the trend book over the 15 years both exist.** Monthly correlation +0.01, bootstrap range −0.07 to +0.13, the same in three sub-periods, and zero against the book's own US rates sleeve. The two earn in different years: the trend book in 2017 and 2019–21, Euribor in 2012 and 2022–24. A 20% risk weight lifts the combined Sharpe from +0.35 to +0.51.

Caveats:

1. **Uncorrelated, not a hedge.** In the trend book's 15 worst months Euribor averaged +0.5 bp against +3.2 bp in an average month. It does not lose alongside the book, and it does not offset it.
2. **2008–10 is outside the window.** The trend backtest starts in April 2011, so the years of Euribor's largest early profit, when trend strategies in general also did well, cannot be compared.
3. **The combined Sharpe leans on the Euribor Sharpe**, which carries every caveat in section 6: synthetic prices, an in-sample threshold, two good ECB cycles. The correlation finding is sturdier than the Sharpe finding, because it does not depend on the level of Euribor returns.
4. **Daily and weekly figures are biased toward zero** by the synthetic's daily noise and by the gap between European and US closes. The monthly figure is the one to use.
5. **The annual correlation with the currency sleeve, −0.71, is 16 points and one cell of 20.** It reflects three years (2012, 2022, 2024) when Euribor earned and the currency sleeve lost; treat it as an observation, not a property.
6. **One trend run.** The comparison uses a single backtest configuration, which held 5 markets on average and US rates on 9% to 21% of days. A trend book with a larger rates allocation, or one that adds European short-rate futures, would overlap more.
7. **Live trading** (October 2025 to May 2026, seven months) is too short to add anything and was not used.
