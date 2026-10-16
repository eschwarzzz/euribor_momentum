import pandas as pd, numpy as np, os
ROOT = os.path.dirname(os.path.abspath(__file__)); R = f"{ROOT}/results"
Res = pd.read_csv(f"{R}/results_main.csv", index_col=0); S = pd.read_csv(f"{R}/subperiod_sharpe.csv", index_col=0)
BM = "BM follow-the-ECB (-sign of DFR 3M change)"; bm_sr = Res.loc[BM, "sharpe"]
def row(k, label=None):
    r = Res.loc[k]; return f"| {label or k} | {r.sharpe:+.2f} | {r.ann_ret_bp:+.0f} | {r.maxdd_bp:.0f} | {r.cagr_vt:+.1f}% | {r.maxdd_vt:.0f}% | {r.hit:.0f}% | {r.sharpe - bm_sr:+.2f} |"
hdr = "| Variant | Sharpe | Ann. P&L (bp) | Max DD (bp) | CAGR @10% vol | Max DD @10% vol | Monthly hit | Δ Sharpe vs follow-the-ECB |\n|---|---|---|---|---|---|---|---|"
main = [("BM long-only 2nd contract", "Benchmark: long-only, 2nd contract"), ("BM trend 12M", "Benchmark: 12M trend"), ("BM trend 3M (sign of 3M price change)", "Benchmark: 3M trend"),
        (BM, "Benchmark: follow-the-ECB (policy momentum)"), ("Prior composite, sign (R+M+I+S)", "Macro composite, prior signs, ±1"), ("Prior composite, scaled (clip +/-2)", "Macro composite, prior signs, scaled"),
        ("Prior composite, user factors only (R+M+S)", "Macro composite, prior signs, no inflation"), ("Ridge all factors (a=10), sign", "Ridge, all 37 features, α=10, ±1"), ("Ridge all factors (a=100), sign", "Ridge, α=100, ±1"),
        ("Ridge all factors (a=10), scaled", "Ridge, α=10, scaled"), ("Logit direction (C=0.1), sign", "Logistic direction, ±1"), ("Lasso all factors (a=0.01), sign", "Lasso, ±1"),
        ("Ridge user factors only (R+M+D+S)", "Ridge, user factors only (no inflation)"), ("Ridge all + US rates + TIC holdings", "Ridge + US rates + Treasury holdings (from 2009)"),
        ("Combo: prior sign + ridge sign (avg)", "Combo: composite + ridge (post hoc)"), ("Combo: prior sign + follow-the-ECB (avg)", "Combo: composite + follow-the-ECB (post hoc)"), ("PLACEBO ridge on shuffled target", "Placebo: ridge on shuffled target")]
groups = [("Rates / policy", "Prior group R only", "Ridge group R only", "Prior composite drop R", "Ridge drop group R"), ("Money supply", "Prior group M only", "Ridge group M only", "Prior composite drop M", "Ridge drop group M"),
          ("Debt holdings", None, "Ridge group D only", None, "Ridge drop group D"), ("Inflation (added)", "Prior group I only", "Ridge group I only", "Prior composite drop I", "Ridge drop group I"),
          ("Sentiment / political", "Prior group S only", "Ridge group S only", "Prior composite drop S", "Ridge drop group S")]
def sr(k): return "n/a" if k is None else f"{Res.loc[k, 'sharpe']:+.2f}"
sens = [("Prior composite, sign (R+M+I+S)", "Composite, expanding z-scores (base)"), ("Prior composite, rolling 60M z-scores", "Composite, rolling 60M z-scores"), ("Prior composite, FRONT contract", "Composite traded on the front contract"),
        ("Prior composite, 3RD contract", "Composite traded on the 3rd contract"), ("Prior composite, 3M smoothed signal", "Composite, 3-month smoothed signal"), ("Prior composite, cost 1bp/side", "Composite, cost 1 bp per side"),
        ("Prior composite, cost 2bp/side", "Composite, cost 2 bp per side"), ("Ridge all factors (a=1), sign", "Ridge α=1"), ("Ridge all factors (a=10), sign", "Ridge α=10 (base)"), ("Ridge all factors (a=100), sign", "Ridge α=100"),
        ("Ridge all factors (a=1000), sign", "Ridge α=1000"), ("Ridge all, min_train 120 (OOS from 2012)", "Ridge, 10-year minimum training, OOS from 2012"), ("Ridge all, FRONT contract", "Ridge traded on the front contract")]
subkeys = [("BM long-only 2nd contract", "Long-only"), ("BM trend 12M", "12M trend"), (BM, "Follow-the-ECB"), ("Prior composite, sign (R+M+I+S)", "Composite, prior signs"), ("Prior composite, scaled (clip +/-2)", "Composite, scaled"),
           ("Ridge all factors (a=10), sign", "Ridge α=10"), ("Logit direction (C=0.1), sign", "Logit"), ("Combo: prior sign + follow-the-ECB (avg)", "Combo composite + ECB (post hoc)")]
sub_hdr = "| Variant | " + " | ".join(S.columns) + " |\n|---|" + "---|" * len(S.columns)
sub_rows = "\n".join("| " + lab + " | " + " | ".join("n/a" if pd.isna(v) else f"{v:+.2f}" for v in S.loc[k]) + " |" for k, lab in subkeys)
n_var = len(Res)
md = f"""# Euribor 3M futures: macro-factor direction strategy

Backtest report, 24 September 2026. Instrument: synthetic 3-month Euribor future, second quarterly contract (3 to 6 months to expiry). Monthly rebalancing at month-end, positions applied from the next trading day, half a basis point (one tick) per side plus quarterly roll costs. Out-of-sample window for every variant: January 2008 to August 2026 (224 months). Data and construction are in the appendix.

## 1. Hypothesis

The direction of the 3M Euribor future over the next month is predictable from the ECB's reaction function: policy-rate momentum and the money-market curve (rates), M1/M3 growth and the Eurosystem balance sheet (money supply), euro-area banks' holdings of euro versus foreign or dollar debt (debt holdings), and political or policy stress measured by news-based policy-uncertainty indices, periphery sovereign spreads and systemic-stress gauges (sentiment). Inflation is added as an explicit extension because it is the ECB's mandate variable and the natural bar for the other factors.

## 2. Benchmark

- **Primary benchmark: follow-the-ECB.** Hold the future long if the deposit rate was cut in the last three months, short if it was raised, keep the previous position otherwise. This is the simplest thing a rates trader would do and it turns out to be hard to beat.
- **Secondary benchmarks:** long-only (roll the second contract), 3-month and 12-month price trend.
- **Universe and window:** one instrument, daily P&L in basis points of price, Jan 2008 to Aug 2026. Fitted models train on data from Dec 2001 onward with an expanding window (minimum 72 months), refit every month, and never see the month they predict. The 2002 to 2007 period is reported separately as a quasi-in-sample check for the unfitted rules.

## 3. Variants

{n_var} variants were run in total (all rows are in `results/results_main.csv`). They fall into four families:

| Family | What varies | Count |
|---|---|---|
| Benchmarks | long-only, 3M trend, 12M trend, follow-the-ECB | 4 |
| Prior-sign composite (no fitting) | z-score each feature, multiply by its theory sign, average within and across groups; ±1 vs scaled sizing; with and without inflation; single group and drop-one-group; expanding vs rolling 60M z-scores; front, 2nd, 3rd contract; 3M smoothed signal; 1 bp and 2 bp costs | 17 |
| Fitted, walk-forward | ridge (α = 1, 10, 100, 1000), lasso, logistic; ±1 vs scaled; user factors only; single group and drop-one-group; plus US rates and Treasury holdings; 10-year minimum training; front contract; shuffled-target placebo | 20 |
| Combinations | composite averaged with ridge; composite averaged with follow-the-ECB | 2 |

Debt-holdings features have no theory-pinned sign, so they enter only the fitted models. Full feature list with lags and signs: appendix B.

## 4. Results

{hdr}
{chr(10).join(row(k, l) for k, l in main)}

CAGR and drawdown at 10% volatility are ex-post scalings of the same P&L to a common risk level, so they are comparable across rows but are not what one unlevered contract earns. The two combination rows were formed after seeing the single-model results and should be read as candidates, not findings.

![Cumulative P&L](results/fig1_cumulative_pnl.png)

**Which factor groups carry the result.** Single-group models and drop-one ablations, Sharpe after costs:

| Group | Alone, prior signs | Alone, ridge | Composite without it | Ridge without it |
|---|---|---|---|---|
{chr(10).join(f"| {g} | {sr(a)} | {sr(b)} | {sr(c)} | {sr(d)} |" for g, a, b, c, d in groups)}

Reference: composite with all groups {Res.loc['Prior composite, sign (R+M+I+S)', 'sharpe']:+.2f}, ridge with all groups {Res.loc['Ridge all factors (a=10), sign', 'sharpe']:+.2f}.

![Sharpe by factor group](results/fig2_group_sharpe.png)

## 5. Robustness

**Sub-periods (Sharpe).** The edge is regime-dependent, not universal: it appears when the ECB is moving (2008 to 2012, 2022 to 2026) and vanishes at the zero lower bound (2013 to 2019), where the contract barely moved and the monthly hit rate was a coin flip.

{sub_hdr}
{sub_rows}

**Parameter and implementation sensitivity (Sharpe, 2008 to 2026).**

| Variant | Sharpe |
|---|---|
{chr(10).join(f"| {lab} | {Res.loc[k, 'sharpe']:+.2f} |" for k, lab in sens)}

**Placebo.** Ridge trained on a shuffled target scores {Res.loc['PLACEBO ridge on shuffled target', 'sharpe']:+.2f}, so the pipeline has no structural leak or drift bias. (An earlier build that bootstrapped the forward from the Euribor deposit curve gave the placebo a Sharpe near 1 and long-only a Sharpe above 6 in 2013 to 2019, which is how the tenor-basis flaw in the synthetic price was found; see appendix A.)

**Overlap with the benchmark.** The composite and follow-the-ECB agree on direction in only 50% of months and their monthly P&L correlation is 0.21, so the composite is not a relabelled policy-momentum rule. Follow-the-ECB is long 81% of the time; the composite is long 49% of the time and changes sign about twice a year, the ridge about three times a year.

**Fitted-model stability.** Ridge coefficients (mean over refits) are largest on 3M changes in the 12M Euribor and in the deposit rate (negative, i.e. rate momentum continues), the Eurosystem balance-sheet 3M change (positive, i.e. QE lowers expected rates), the curve slope (positive) and the 3M price change (negative, i.e. short-horizon mean reversion, opposite to the composite's prior). Rates and inflation coefficients keep their sign in about 90% of monthly refits; the least stable are money-supply terms (M3 six-month growth and balance-sheet YoY keep their sign in fewer than half of the refits) and the CISS level (two thirds).

## 6. Verdict

**Context-dependent.** The macro composite beats long-only and both trend benchmarks and matches the follow-the-ECB rule (Sharpe {Res.loc['Prior composite, sign (R+M+I+S)', 'sharpe']:+.2f} vs {bm_sr:+.2f}, t ≈ {Res.loc['Prior composite, sign (R+M+I+S)', 't_stat']:.1f}), but almost all of the value sits in the rates/policy block plus inflation; money supply and political sentiment add little on their own and nothing incremental, and debt holdings add about +0.1 Sharpe inside the fitted model only. A tradeable version would be the composite (or the composite averaged with policy momentum) run only when the ECB is in an active cycle, with the expectation of flat results at the lower bound.

Caveats, in order of importance:

1. **Prices are synthetic.** No free source of ICE Euribor futures exists, so the contract is priced from daily 3M Euribor plus the AAA government forward premium. It settles exactly at 100 minus 3M Euribor, but intra-life marks carry government-curve noise and ignore the Euribor-OIS basis and convexity. Validate on real settlement prices before trading.
2. **Multiple testing.** {n_var} variants; the best fitted Sharpe (α = 100, {Res.loc['Ridge all factors (a=100), sign', 'sharpe']:+.2f}) and the post hoc combination ({Res.loc['Combo: prior sign + follow-the-ECB (avg)', 'sharpe']:+.2f}) should be discounted. The composite's signs were fixed from theory before running, which limits but does not remove this.
3. **The composite failed in 2002 to 2007** (Sharpe {S.loc['Prior composite, sign (R+M+I+S)', S.columns[0]]:+.2f}) while follow-the-ECB worked (+0.81). One full hiking cycle out of two in the sample was missed.
4. **Feature effective sample is small.** Eighteen years contain three ECB cycles; single-group results move by ±0.3 Sharpe when the window shifts.
5. **Data gaps.** Treasury holdings for Germany, Italy and the Netherlands are carried forward from Nov 2025; BIS bank claims are quarterly with a five-month publication lag; monthly macro is used with a one-month lag (two for unemployment and Treasury data), and 2026 inflation comes from Eurostat's new ECOICOP-v2 series spliced onto the ECB history.

## Appendix A. Instrument construction

- **Underlying rates:** Bundesbank daily Euribor 1W to 12M (Dec 1998 to Sep 2026), cross-checked against Banque de France and a Kaggle copy (identical to 0.1 bp).
- **Contract price:** for expiry T with t₁ days to go, futures rate = 3M Euribor(t) + [AAA govt forward(t₁, t₁+91) − AAA govt spot 3M], using the ECB AAA zero curve (3M, 6M, 1Y) with log-linear discount-factor interpolation; price = 100 − rate. Before Sep 2004 (no ECB curve) the forward comes from the Euribor deposit curve, when the 3M/6M tenor basis was 1 to 3 bp.
- **Why not the deposit curve throughout:** post-2008 the 6M and 12M deposit rates carry a larger credit premium than 3M, so a single-curve forward overstates the expected rate and every contract drifts upward into expiry. That produced a long-only Sharpe above 6 in 2013 to 2019 and a placebo Sharpe near 1; the government-curve construction removes it (long-only 2013 to 2019: +0.16).
- **Continuous series:** constant-rank roll on the front expiry (IMM Wednesday); same-contract daily changes; roll cost = two ticks × position.
- **Sanity checks:** expiry price equals 100 − spot 3M Euribor exactly; implied futures-minus-spot averages +55 bp in 2022 (hikes priced) and −57 bp in 2024 (cuts priced); largest daily moves fall on 14 and 16 March 2023 and in October 2008.

## Appendix B. Features (all known at the month-end they are used)

| Group | Feature | Lag | Prior sign on price |
|---|---|---|---|
| Rates | DFR change 3M, 6M | daily | − |
| Rates | Euribor 12M − 3M slope; its 3M change | daily | +, − |
| Rates | 12M Euribor 3M change | daily | − |
| Rates | 3M Euribor − DFR (money-market stress) | daily | + |
| Rates | 2nd-contract price momentum 3M, 12M | daily | + |
| Money | M1, M3 YoY; M3 6M annualised; M3 acceleration; real M1 | 1 month | − |
| Money | Eurosystem total assets YoY, 3M change | 1 week | + |
| Debt | MFI holdings of non-euro-area debt: share change 12M, YoY; euro-area debt YoY; difference | 1 month | learned |
| Debt | Euro-area banks' cross-border claims: USD share change 12M, USD YoY, EUR YoY (BIS) | 5 months, quarterly | learned |
| Debt (ext.) | Euro-area holdings of US Treasuries: 7-country and 4-country YoY, share change (TIC) | 2 months | learned |
| Inflation | HICP, core; 3M changes; unemployment 6M change | 1 month (2 for unemployment) | −, −, −, −, + |
| Sentiment | Europe EPU: expanding z-score, 3M log change; periphery-minus-core EPU and its change | 1 month | + |
| Sentiment | IT/ES minus DE 10Y spread and 3M change; CISS and 3M change; ESI z-score and 3M change | monthly / daily | +, +, +, +, −, − |
| US (ext.) | US 2Y and fed funds 3M change; US 2Y − Euribor 12M | daily | −, −, 0 |

## Appendix C. Files

`data/` raw downloads and `features_monthly.csv`; `results/results_main.csv` (all {n_var} variants), `subperiod_sharpe.csv`, `daily_pnl_curves.csv`, `monthly_positions.csv`, `ridge_coefs.csv`; scripts `fetch_ecb.py`, `build_futures.py`, `features.py`, `backtest.py`, `make_charts.py`, `make_report.py`. Rerun in that order.
"""
open(f"{ROOT}/REPORT.md", "w").write(md); print("REPORT.md written,", len(md), "chars")
