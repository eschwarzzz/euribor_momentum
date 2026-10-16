"""Write the Markdown reports from the files in results/.

* ``research_report``  -> reports/REPORT.md: the original six-section test report on one contract.
* ``account_report``   -> reports/BACKTEST_50K.md (six sections) and reports/BACKTEST_50K_APPENDIX.md
  (A: the last five years as a fresh account, B: correlation with the trend-following book).

Rerun after any of backtest, montecarlo, account, charts or the research scripts the appendices draw on.
"""
import datetime as dt
import json

import numpy as np
import pandas as pd

from .backtest import daily_pnl, metrics
from .config import (COMPOSITE, COMPOSITE_SCALED, ECB_RULE, LOGIT, LONG_ONLY, OOS_END, OOS_START, PLACEBO, REPORTS,
                     RESULTS, RIDGE_10, RIDGE_100, TICK_COST, TREND_12M, TREND_3M)
from .data import load_continuous, load_features, load_group_scores, load_positions, load_results_table
from .signals import frozen_spec, risk_score

MINUS = "−"


def sg(x, nd=2):
    """Signed number with a real minus sign."""
    return ("+" if x >= 0 else MINUS) + f"{abs(x):.{nd}f}"


def pc(x, nd=1):
    return (MINUS if x < 0 else "") + f"{abs(x):.{nd}f}%"


def spc(x, nd=1):
    return ("+" if x >= 0 else MINUS) + f"{abs(x):.{nd}f}%"


def eur(x, nd=0):
    return (MINUS if x < 0 else "") + "€" + f"{abs(x):,.{nd}f}"


def seur(x):
    return ("+" if x >= 0 else MINUS) + "€" + f"{abs(x):,.0f}"


def k(x):
    return "€" + f"{x / 1000:,.0f}k"


def sk(x):
    return ("+" if x >= 0 else MINUS) + "€" + f"{abs(x) / 1000:,.1f}k"


def pv(p, n):
    return f"0 of {n:,}" if p == 0 else f"{p:.3f}"


def today():
    return dt.date.today().strftime("%-d %B %Y")


# ================================================================ REPORT.md
def research_report():
    Res = load_results_table()
    S = pd.read_csv(RESULTS / "subperiod_sharpe.csv", index_col=0)
    bm_sr = Res.loc[ECB_RULE, "sharpe"]

    def row(key, label=None):
        r = Res.loc[key]
        return (f"| {label or key} | {r.sharpe:+.2f} | {r.ann_ret_bp:+.0f} | {r.maxdd_bp:.0f} | {r.cagr_vt:+.1f}% | {r.maxdd_vt:.0f}% | "
                f"{r.hit:.0f}% | {r.sharpe - bm_sr:+.2f} |")

    hdr = ("| Variant | Sharpe | Ann. P&L (bp) | Max DD (bp) | CAGR @10% vol | Max DD @10% vol | Monthly hit | Δ Sharpe vs follow-the-ECB |\n"
           "|---|---|---|---|---|---|---|---|")
    main = [(LONG_ONLY, "Benchmark: long-only, 2nd contract"), (TREND_12M, "Benchmark: 12M trend"), (TREND_3M, "Benchmark: 3M trend"),
            (ECB_RULE, "Benchmark: follow-the-ECB (policy momentum)"), (COMPOSITE, "Macro composite, prior signs, ±1"),
            (COMPOSITE_SCALED, "Macro composite, prior signs, scaled"),
            ("Prior composite, user factors only (R+M+S)", "Macro composite, prior signs, no inflation"),
            (RIDGE_10, "Ridge, all 37 features, α=10, ±1"), (RIDGE_100, "Ridge, α=100, ±1"), ("Ridge all factors (a=10), scaled", "Ridge, α=10, scaled"),
            (LOGIT, "Logistic direction, ±1"), ("Lasso all factors (a=0.01), sign", "Lasso, ±1"),
            ("Ridge user factors only (R+M+D+S)", "Ridge, user factors only (no inflation)"),
            ("Ridge all + US rates + TIC holdings", "Ridge + US rates + Treasury holdings (from 2009)"),
            ("Combo: prior sign + ridge sign (avg)", "Combo: composite + ridge (post hoc)"),
            ("Combo: prior sign + follow-the-ECB (avg)", "Combo: composite + follow-the-ECB (post hoc)"),
            (PLACEBO, "Placebo: ridge on shuffled target")]
    groups = [("Rates / policy", "Prior group R only", "Ridge group R only", "Prior composite drop R", "Ridge drop group R"),
              ("Money supply", "Prior group M only", "Ridge group M only", "Prior composite drop M", "Ridge drop group M"),
              ("Debt holdings", None, "Ridge group D only", None, "Ridge drop group D"),
              ("Inflation (added)", "Prior group I only", "Ridge group I only", "Prior composite drop I", "Ridge drop group I"),
              ("Sentiment / political", "Prior group S only", "Ridge group S only", "Prior composite drop S", "Ridge drop group S")]

    def sr(key):
        return "n/a" if key is None else f"{Res.loc[key, 'sharpe']:+.2f}"

    sens = [(COMPOSITE, "Composite, expanding z-scores (base)"), ("Prior composite, rolling 60M z-scores", "Composite, rolling 60M z-scores"),
            ("Prior composite, FRONT contract", "Composite traded on the front contract"),
            ("Prior composite, 3RD contract", "Composite traded on the 3rd contract"),
            ("Prior composite, 3M smoothed signal", "Composite, 3-month smoothed signal"),
            ("Prior composite, cost 1bp/side", "Composite, cost 1 bp per side"), ("Prior composite, cost 2bp/side", "Composite, cost 2 bp per side"),
            ("Ridge all factors (a=1), sign", "Ridge α=1"), (RIDGE_10, "Ridge α=10 (base)"), (RIDGE_100, "Ridge α=100"),
            ("Ridge all factors (a=1000), sign", "Ridge α=1000"),
            ("Ridge all, min_train 120 (OOS from 2012)", "Ridge, 10-year minimum training, OOS from 2012"),
            ("Ridge all, FRONT contract", "Ridge traded on the front contract")]
    subkeys = [(LONG_ONLY, "Long-only"), (TREND_12M, "12M trend"), (ECB_RULE, "Follow-the-ECB"), (COMPOSITE, "Composite, prior signs"),
               (COMPOSITE_SCALED, "Composite, scaled"), (RIDGE_10, "Ridge α=10"), (LOGIT, "Logit"),
               ("Combo: prior sign + follow-the-ECB (avg)", "Combo composite + ECB (post hoc)")]
    sub_hdr = "| Variant | " + " | ".join(S.columns) + " |\n|---|" + "---|" * len(S.columns)
    sub_rows = "\n".join("| " + lab + " | " + " | ".join("n/a" if pd.isna(v) else f"{v:+.2f}" for v in S.loc[key]) + " |" for key, lab in subkeys)
    n_var = len(Res)
    nl = chr(10)
    return f"""# Euribor 3M futures: macro-factor direction strategy

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
{nl.join(row(key, l) for key, l in main)}

CAGR and drawdown at 10% volatility are ex-post scalings of the same P&L to a common risk level, so they are comparable across rows but are not what one unlevered contract earns. The two combination rows were formed after seeing the single-model results and should be read as candidates, not findings.

![Cumulative P&L](figures/fig1_cumulative_pnl.png)

**Which factor groups carry the result.** Single-group models and drop-one ablations, Sharpe after costs:

| Group | Alone, prior signs | Alone, ridge | Composite without it | Ridge without it |
|---|---|---|---|---|
{nl.join(f"| {g} | {sr(a)} | {sr(b)} | {sr(c)} | {sr(d)} |" for g, a, b, c, d in groups)}

Reference: composite with all groups {Res.loc[COMPOSITE, 'sharpe']:+.2f}, ridge with all groups {Res.loc[RIDGE_10, 'sharpe']:+.2f}.

![Sharpe by factor group](figures/fig2_group_sharpe.png)

## 5. Robustness

**Sub-periods (Sharpe).** The edge is regime-dependent, not universal: it appears when the ECB is moving (2008 to 2012, 2022 to 2026) and vanishes at the zero lower bound (2013 to 2019), where the contract barely moved and the monthly hit rate was a coin flip.

{sub_hdr}
{sub_rows}

**Parameter and implementation sensitivity (Sharpe, 2008 to 2026).**

| Variant | Sharpe |
|---|---|
{nl.join(f"| {lab} | {Res.loc[key, 'sharpe']:+.2f} |" for key, lab in sens)}

**Placebo.** Ridge trained on a shuffled target scores {Res.loc[PLACEBO, 'sharpe']:+.2f}, so the pipeline has no structural leak or drift bias. (An earlier build that bootstrapped the forward from the Euribor deposit curve gave the placebo a Sharpe near 1 and long-only a Sharpe above 6 in 2013 to 2019, which is how the tenor-basis flaw in the synthetic price was found; see appendix A.)

**Overlap with the benchmark.** The composite and follow-the-ECB agree on direction in only 50% of months and their monthly P&L correlation is 0.21, so the composite is not a relabelled policy-momentum rule. Follow-the-ECB is long 81% of the time; the composite is long 49% of the time and changes sign about twice a year, the ridge about three times a year.

**Fitted-model stability.** Ridge coefficients (mean over refits) are largest on 3M changes in the 12M Euribor and in the deposit rate (negative, i.e. rate momentum continues), the Eurosystem balance-sheet 3M change (positive, i.e. QE lowers expected rates), the curve slope (positive) and the 3M price change (negative, i.e. short-horizon mean reversion, opposite to the composite's prior). Rates and inflation coefficients keep their sign in about 90% of monthly refits; the least stable are money-supply terms (M3 six-month growth and balance-sheet YoY keep their sign in fewer than half of the refits) and the CISS level (two thirds).

## 6. Verdict

**Context-dependent.** The macro composite beats long-only and both trend benchmarks and matches the follow-the-ECB rule (Sharpe {Res.loc[COMPOSITE, 'sharpe']:+.2f} vs {bm_sr:+.2f}, t ≈ {Res.loc[COMPOSITE, 't_stat']:.1f}), but almost all of the value sits in the rates/policy block plus inflation; money supply and political sentiment add little on their own and nothing incremental, and debt holdings add about +0.1 Sharpe inside the fitted model only. A tradeable version would be the composite (or the composite averaged with policy momentum) run only when the ECB is in an active cycle, with the expectation of flat results at the lower bound.

Caveats, in order of importance:

1. **Prices are synthetic.** No free source of ICE Euribor futures exists, so the contract is priced from daily 3M Euribor plus the AAA government forward premium. It settles exactly at 100 minus 3M Euribor, but intra-life marks carry government-curve noise and ignore the Euribor-OIS basis and convexity. Validate on real settlement prices before trading.
2. **Multiple testing.** {n_var} variants; the best fitted Sharpe (α = 100, {Res.loc[RIDGE_100, 'sharpe']:+.2f}) and the post hoc combination ({Res.loc['Combo: prior sign + follow-the-ECB (avg)', 'sharpe']:+.2f}) should be discounted. The composite's signs were fixed from theory before running, which limits but does not remove this.
3. **The composite failed in 2002 to 2007** (Sharpe {S.loc[COMPOSITE, S.columns[0]]:+.2f}) while follow-the-ECB worked (+0.81). One full hiking cycle out of two in the sample was missed.
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

`data/raw/` holds the downloaded sources and `data/processed/` the synthetic futures and `features_monthly.csv`; `results/results_main.csv` (all {n_var} variants), `subperiod_sharpe.csv`, `daily_pnl_curves.csv`, `monthly_positions.csv`, `ridge_coefs.csv`. Pipeline: `python -m euribor fetch`, `futures`, `features`, `backtest`, `montecarlo`, `charts`, `reports`, in that order (or `make all`); the code is in the `euribor/` package.
"""


# ================================================================ BACKTEST_50K.md and its appendix
def account_report():
    """Return (main report, appendix) as Markdown strings."""
    S = pd.read_csv(RESULTS / "bt50k_variants.csv", index_col=0)
    YR = pd.read_csv(RESULTS / "bt50k_by_year.csv", index_col=0)
    SUB = pd.read_csv(RESULTS / "bt50k_subperiods.csv", index_col=0)
    mc = json.load(open(RESULTS / "bt50k_mc.json"))
    d = pd.read_csv(RESULTS / "bt50k_daily.csv", index_col=0, parse_dates=True)
    m = pd.read_csv(RESULTS / "bt50k_monthly.csv", index_col=0, parse_dates=True)
    S5 = pd.read_csv(RESULTS / "bt50k_5y_variants.csv", index_col=0)
    YR5 = pd.read_csv(RESULTS / "bt50k_5y_by_year.csv", index_col=0)
    SY5 = pd.read_csv(RESULTS / "bt50k_5y_sharpe_by_year.csv", index_col=0)
    mc5 = json.load(open(RESULTS / "bt50k_5y_mc.json"))
    d5 = pd.read_csv(RESULTS / "bt50k_5y_daily.csv", index_col=0, parse_dates=True)
    m5 = pd.read_csv(RESULTS / "bt50k_5y_monthly.csv", index_col=0, parse_dates=True)
    CB = mc["cost_bp"]
    CPS = CB * 25
    FZ, WF, EC, LO, TR = ("Frozen spec, 10% vol target", "Walk-forward threshold, 10% vol", "Follow-the-ECB only, 10% vol", "Long-only, 10% vol",
                          "12M trend, 10% vol")
    F, _, _ = load_features()
    cont = load_continuous()
    P, G = load_positions(), load_group_scores()
    ecb = P[ECB_RULE]
    score = risk_score(G)
    frozen = frozen_spec(ecb, score)
    u_old = metrics(*daily_pnl(frozen, cont, cost=TICK_COST), start=OOS_START, end=OOS_END)["sharpe"]
    u_new = mc["unit_check"]["sharpe"]

    # derived figures, main window
    eq = d["equity"]
    dds = eq / eq.cummax() - 1
    trough = dds.idxmin()
    peak = eq.loc[:trough].idxmax()
    rec = eq.loc[trough:][eq.loc[trough:] >= eq.loc[peak]].index
    under = int((dds < 0).astype(int).groupby((dds == 0).cumsum()).sum().max())
    ret_m = m["ret"]
    wm, bm = ret_m.idxmin() + pd.offsets.MonthEnd(1), ret_m.idxmax() + pd.offsets.MonthEnd(1)      # decision at month-end t -> P&L month is t+1
    fees = d["fees"].sum()
    gross = d["pnl"].sum() + fees
    flips = int((np.sign(m["contracts"]).diff().abs() > 0).sum())
    resized = int((m["traded"] > 0).sum())
    lr = np.log1p(d["ret"])
    share = lambda a, b: lr.loc[a:b].sum() / lr.sum()      # noqa: E731
    tot = m["pnl"].sum()
    top5 = m["pnl"].nlargest(5).sum() / tot
    top10 = m["pnl"].nlargest(10).sum() / tot
    era = {}
    for lab, (a, b) in {"2008–12": ("2008", "2012"), "2013–21": ("2013", "2021"), "2022–26": ("2022", "2026")}.items():
        x = d.loc[a:b]
        era[lab] = (x["contracts"].abs().mean(), x["margin"].mean(), x["margin_pct"].mean() * 100, x["margin_stress_pct"].max() * 100)
    sides_roll = 2 * (m["rolls"] * m["contracts"].abs()).sum()
    sides_trade = m["traded"].sum()
    yrs = len(m) / 12
    nl, ds, bs, bp = mc["nulls"], mc["deflated"], mc["bootstrap_sharpe"], mc["bootstrap_pnl"]
    sr0_45, sr0_70 = 0.53, 0.57
    roll60 = ret_m.rolling(60).apply(lambda x: x.mean() / x.std() * np.sqrt(12))

    def row(name, label=None, bold=False, base=None):
        r = S.loc[name]
        delta = "n/a" if base is None else ("0" if name == base else sg(r["sharpe"] - S.loc[base, "sharpe"]))
        cells = [label or name, sg(r["sharpe"]), pc(r["cagr_pct"]), pc(r["maxdd_pct"]), eur(r["final_equity"]), delta]
        return "| " + " | ".join(f"**{c}**" if bold else c for c in cells) + " |"

    MAIN = f"""# Euribor macro strategy: €50,000 account backtest

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
| Costs | {CB} bp per side = €{CPS:.2f} per contract (half a one-tick spread plus exchange, clearing and broker fees); roll = €{2 * CPS:.0f} per contract, four times a year |
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
| Costs paid | {eur(fees)}, about {fees / gross:.0%} of gross profit |
| Direction changes | {flips} in {yrs:.1f} years; position resized in {resized} of {len(m)} months |

Margin deployed (Figure 7, bottom panel):

| Period | Avg contracts | Avg margin | Share of equity | Peak share if margin had scaled with volatility |
|---|---|---|---|---|
""" + "\n".join(f"| {lab} | {v[0]:.1f} | {eur(v[1])} | {pc(v[2])} | {pc(v[3])} |" for lab, v in era.items()) + f"""
| Whole window | {S.loc[FZ, "avg_contracts"]:.1f} | {eur(d["margin"].mean())} | {pc(S.loc[FZ, "avg_margin_pct"])} (peak {pc(S.loc[FZ, "peak_margin_pct"])}) | {pc(S.loc[FZ, "peak_margin_stress_pct"])} |

Calendar years, frozen spec:

| Year | P&L € | Return | Year-end equity | Avg contracts (+ long, − short) |
|---|---|---|---|---|
""" + "\n".join(f"| {y if y != 2026 else '2026 (to Aug)'} | {('+' if r.pnl_eur >= 0 else MINUS)}{abs(r.pnl_eur):,.0f} | {spc(r.ret_pct)} | {r.equity_end:,.0f} | {sg(r.avg_contracts, 1)} |"
                for y, r in YR.iterrows()) + f"""

![Figure 6. Equity and drawdown, January 2008 to August 2026](figures/fig6_bt50k_equity.png)

*Figure 6. Account equity for the four strategies and the frozen spec's drawdown.*

![Figure 7. Signal, volatility, contracts and margin](figures/fig7_bt50k_signal_vol_margin.png)

*Figure 7. The signal, the volatility used for sizing, contracts held and margin deployed.*

## 5. Robustness

**Regimes.** The result is regime dependent, not universal.

| Sharpe by period | 2008–12 crisis | 2013–19 ZLB/QE | 2020–21 COVID | 2022–26 hikes + cuts |
|---|---|---|---|---|
""" + "\n".join(f"| {lab} | " + " | ".join(sg(SUB.loc[key_, c]) for c in SUB.columns) + " |"
                for lab, key_ in [("Frozen spec", FZ), ("Walk-forward threshold", WF), ("Follow-the-ECB", EC), ("Long-only", LO)]) + f"""

{share('2008', '2012'):.0%} of the account's growth came in 2008–12, {share('2022', '2026'):.0%} in 2022–26 and {share('2013', '2021'):.0%} in the nine years 2013–21. The best 5 months are {top5:.0%} of total P&L and the best 10 are {top10:.0%}.

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

![Figure 8. Monte Carlo, full window](figures/fig8_bt50k_montecarlo.png)

*Figure 8. Bootstrap Sharpe with medians, bootstrap equity paths, bootstrap drawdown, and the no-skill shuffle test.*

**Sizing.** Volatility targeting costs Sharpe here: {sg(S.loc['Frozen, fixed 1 contract', 'sharpe'])} with one fixed contract against {sg(S.loc[FZ, 'sharpe'])} at a 10% target, because the strategy earns most when volatility is high, which is when the target cuts the position. Without the long-run blend the account ran up to {int(S.loc['Frozen, 60-day vol only (no long-run blend)', 'max_contracts'])} contracts in the zero-rate years and Sharpe fell to {sg(S.loc['Frozen, 60-day vol only (no long-run blend)', 'sharpe'])}. Higher targets scale return and drawdown together (20% target: {pc(S.loc['Frozen, 20% vol target', 'maxdd_pct'])} drawdown, a {pc(S.loc['Frozen, 20% vol target', 'worst_month_pct'], 0)} month).

**Costs.** Sharpe {sg(S.loc['Frozen, cost 0.5 bp/side', 'sharpe'])} at 0.5 bp per side (one full tick), {sg(S.loc['Frozen, cost 1 bp/side', 'sharpe'])} at 1 bp and {sg(S.loc['Frozen, cost 2 bp/side', 'sharpe'])} at 2 bp. Rolls are {sides_roll / (sides_roll + sides_trade):.0%} of the contract-sides traded: at a 10% target the account rolls about {S.loc[FZ, 'avg_contracts']:.0f} contracts four times a year, against {flips} direction changes in {yrs:.1f} years.

**Instrument.** On the OIS-spliced prices for 2005–14 the frozen spec is {sg(S.loc['Frozen, OIS-spliced prices 2005-14', 'sharpe'])} ({k(S.loc['Frozen, OIS-spliced prices 2005-14', 'final_equity'])}) against {sg(S.loc[FZ, 'sharpe'])} ({k(S.loc[FZ, 'final_equity'])}); follow-the-ECB goes from {sg(S.loc[EC, 'sharpe'])} to {sg(S.loc['Follow-the-ECB, OIS-spliced prices', 'sharpe'])}.

**Margin.** Margin is never the constraint. It averaged {pc(S.loc[FZ, 'avg_margin_pct'])} of equity and peaked at {pc(S.loc[FZ, 'peak_margin_pct'])}; even with margin scaled up with volatility the peak stays at {pc(S.loc[FZ, 'peak_margin_stress_pct'])}. The binding limit is the volatility target, and 95% of the account sits in cash, which this backtest credits no interest on.
"""

    # ---------- appendix A: last five years
    FZ5, EC5 = FZ, EC
    e5 = d5["equity"]
    dd5 = e5 / e5.cummax() - 1
    tr5 = dd5.idxmin()
    pk5 = e5.loc[:tr5].idxmax()
    rec5 = e5.loc[tr5:][e5.loc[tr5:] >= e5.loc[pk5]].index
    wm5 = m5["ret"].idxmin() + pd.offsets.MonthEnd(1)
    run_id = (np.sign(m5["contracts"]) != np.sign(m5["contracts"]).shift()).cumsum()
    runs = []
    for _, g in m5.groupby(run_id):
        runs.append((("Short" if g["contracts"].iloc[0] < 0 else "Long"), g.index[0] + pd.offsets.MonthEnd(1), g.index[-1] + pd.offsets.MonthEnd(1),
                     len(g), g["chg_pts"].sum() * 100, g["pnl"].sum()))
    flips5 = [(t + pd.offsets.MonthEnd(1)) for t in m5.index[np.sign(m5["contracts"]).diff().abs() > 0]]
    fire = ((score.abs() > 0.5) & (np.sign(score) != ecb)).loc["2021-08-31":"2026-07-31"]
    n_fire = int(fire.sum())
    ov_move = cont["chg1"].loc["2021-09-01":"2022-07-31"].sum() * 100
    ov_pos = m5.loc[fire[fire].index]
    ov_gain = ov_pos[ov_pos["pnl"] > 0]["contracts"].abs()
    jul = m5.loc["2022-06-30"]
    worst_long = m5.loc[(m5["contracts"] > 0)].sort_values("pnl").iloc[0]
    prelong = m5.loc["2025-10-31":"2026-01-31", "contracts"]
    bs5, bp5, nl5, ds5 = mc5["bootstrap_sharpe"], mc5["bootstrap_pnl"], mc5["nulls"], mc5["deflated"]
    tot5 = m5["pnl"].sum()
    top5_5 = m5["pnl"].nlargest(5).sum() / tot5
    mp5 = d5["margin_pct"]

    def row5(name, label=None, bold=False):
        r = S5.loc[name]
        cells = [label or name, sg(r["sharpe"]), pc(r["cagr_pct"]), pc(r["maxdd_pct"]), eur(r["final_equity"]),
                 ("0" if name == LO else sg(r["sharpe"] - S5.loc[LO, "sharpe"]))]
        return "| " + " | ".join(f"**{c}**" if bold else c for c in cells) + " |"

    def yl(y):
        return {2021: "2021 (Sep–Dec)", 2026: "2026 (Jan–Aug)"}.get(y, str(y))

    APPA = f"""# Appendix A. The last five years: September 2021 to August 2026

A new €50,000 account opened on 1 September 2021, same rules, sizing, costs ({CB} bp per side) and margin as the main test. 60 months, covering the 2022–23 hiking cycle, the 2024–25 cuts and the June 2026 hike. The walk-forward threshold is 0.5 in every one of these years, so it is the frozen spec here and is not shown separately. Output: `results/bt50k_5y_*.csv`, figures `reports/figures/fig9_bt50k_5y_account.png` and `reports/figures/fig10_bt50k_5y_montecarlo.png`. Both pages in one file: `reports/figures/bt50k_5y_pages.pdf` (page 1 account, page 2 Sharpe and Monte Carlo analysis).

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
""" + "\n".join(f"| {yl(y)} | {('+' if r.pnl_eur >= 0 else MINUS)}{abs(r.pnl_eur):,.0f} | {spc(r.ret_pct)} | {r.equity_end:,.0f} | {sg(r.avg_contracts, 1)} | {pc(r.avg_margin_pct)} |"
                for y, r in YR5.iterrows()) + f"""

![Figure 9. Last five years: account page](figures/fig9_bt50k_5y_account.png)

*Figure 9. New €50,000 account from September 2021: equity, signal, volatility, contracts and margin.*

## A2. Sharpe analysis and Monte Carlo

Sharpe by calendar year (2021 = Sep–Dec, 2026 = Jan–Aug):

| Year | Frozen spec, 10% vol | Follow-the-ECB, 10% vol | Long-only, 10% vol | Frozen spec, 1 contract | Follow-the-ECB, 1 contract |
|---|---|---|---|---|---|
""" + "\n".join(("| **All 60 months** | " + " | ".join(f"**{sg(v)}**" for v in r) + " |") if y == "all 60 months"
                else ("| " + str(y) + " | " + " | ".join(sg(v) for v in r) + " |") for y, r in SY5.iterrows()) + f"""

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

![Figure 10. Monte Carlo, last five years](figures/fig10_bt50k_5y_montecarlo.png)

*Figure 10. The same four Monte Carlo panels for the 60-month window.*

## A3. Reading

1. **One trade made the money.** {runs[0][5] / tot5:.0%} of the P&L is the {runs[0][3]}-month short through the hiking cycle. The two-year long through the cuts {"lost " + eur(-runs[1][5]) if runs[1][5] < 0 else "made " + eur(runs[1][5])} even though the contract rose {runs[1][4]:.0f} bp, because {(worst_long.name + pd.offsets.MonthEnd(1)):%B %Y} cost {eur(-worst_long['pnl'])} on {int(worst_long['contracts'])} contracts. The best 5 months are {top5_5:.0%} of the P&L.
2. **The override added nothing on equal sizing.** With 3 fixed contracts the frozen spec ends at {eur(S5.loc['Frozen, fixed 3 contracts', 'final_equity'])} and plain follow-the-ECB at {eur(S5.loc['Follow-the-ECB, fixed 3 contracts', 'final_equity'])} (Sharpe {sg(S5.loc['Frozen, fixed 3 contracts', 'sharpe'])} and {sg(S5.loc['Follow-the-ECB, fixed 3 contracts', 'sharpe'])}; {sg(mc5['unit_check']['sharpe'])} and {sg(mc5['unit_check_ecb']['sharpe'])} on one contract). The 2nd contract moved {sg(ov_move, 0)} bp net over the {n_fire} override months. The gap at a 10% target ({sg(S5.loc[FZ5, 'sharpe'])} against {sg(S5.loc[EC5, 'sharpe'])}) comes from sizing: the override was short {int(ov_gain.min())} to {int(ov_gain.max())} contracts in the months it gained, and {int(abs(jul['contracts']))} contracts in July 2022, when the contract bounced {abs(jul['chg_pts']) * 100:.0f} bp against it.
3. **Fixed contracts beat volatility targeting in this window.** Three fixed contracts made {"the same money as" if abs(S5.loc['Frozen, fixed 3 contracts', 'pnl_eur'] / S5.loc[FZ5, 'pnl_eur'] - 1) < 0.1 else eur(S5.loc['Frozen, fixed 3 contracts', 'pnl_eur']) + " against " + eur(S5.loc[FZ5, 'pnl_eur']) + " for"} the 10% target with a {pc(S5.loc['Frozen, fixed 3 contracts', 'maxdd_pct'])} drawdown instead of {pc(S5.loc[FZ5, 'maxdd_pct'])} and a worst month of {pc(S5.loc['Frozen, fixed 3 contracts', 'worst_month_pct'])} instead of {pc(S5.loc[FZ5, 'worst_month_pct'])}. Low volatility in late 2025 took the target to {int(prelong.min())} to {int(prelong.max())} contracts just before the {wm5:%B %Y} move.
4. **This window is better than typical, not typical.** The rolling 60-month Sharpe of the 2008-start account is {sg(roll60.iloc[-1])} now against a median of {sg(roll60.median())} across {int(roll60.notna().sum())} windows (range {sg(roll60.min())} to {sg(roll60.max())}); the current window beats {(roll60.dropna() < roll60.iloc[-1]).mean():.0%} of them. Five years with a full hiking cycle and a cutting cycle are the conditions the rule is built for.
5. **Sixty months, three position runs.** The shuffle tests reject luck (p = {nl5['Frozen spec']['p_perm']:.3f}), but with {len(flips5)} direction changes they have little to work with, and the bootstrap interval is wide: {sg(bs5['Frozen spec']['p05'])} to {sg(bs5['Frozen spec']['p95'])}.
6. **Prices are still synthetic here, and this is where they are weakest.** The synthetic takes its forward premium from the AAA government curve, and in 2022–23 short government yields moved away from Euribor-linked rates. Real ICE prices exist for this whole window (Databento, December 2018 onward); rerunning this page on them is the check that matters most.

**Verdict for the window: context-dependent.** If the ECB keeps moving rates, the last five years support the plain follow-the-ECB rule at about Sharpe +1 on fixed contracts; they give no support for the override beyond the sizing effect, and none for volatility targeting over a fixed position. {len(S5)} further account variants were run for this page; no parameter was changed.
"""

    # ---------- appendix B: correlation with the trend-following book (numbers from research/trend_correlation.py)
    BYF = pd.read_csv(RESULTS / "trendcorr_by_frequency.csv", index_col=0)
    MCR = pd.read_csv(RESULTS / "trendcorr_monthly.csv", index_col=0)
    TY = pd.read_csv(RESULTS / "trendcorr_by_year.csv", index_col=0)
    tc = json.load(open(RESULTS / "trendcorr.json"))
    MP = pd.read_csv(RESULTS / "trendcorr_monthly_pnl.csv", index_col=0, parse_dates=True)
    rc = MP["Frozen spec, 1 contract"].rolling(36).corr(MP["Whole trend book"])
    sub, bi, cd, cb = tc["subperiods"], tc["bootstrap"], tc["conditional"], tc["combinations"]
    nF = [c.split("(n=")[1].rstrip(")") for c in BYF.columns]

    def c2(x):
        return sg(x) if abs(x) >= 0.005 else "0.00"

    APPB = f"""# Appendix B. Correlation with the trend-following book

Does the Euribor strategy add something the rest of the portfolio does not already have? Tested against the AlgoGators trend-following backtest (run `TREND_FOLLOWING_20260505_010930_346`, 34 CME markets, per-market daily P&L in dollars from `trend_risk/.../phase2/pnl_panel.csv`). Window 4 April 2011 to 30 April 2026: {nF[0]} days, {nF[2]} months. Euribor side: frozen spec on one contract unless stated. Script `research/trend_correlation.py`, output `results/trendcorr_*.csv`, `results/trendcorr.json`, figure `reports/figures/fig11_bt50k_trend_correlation.png`.

## B1. Correlations

Frozen spec, one contract, against the trend book and its sleeves:

| Trend book | Daily ({nF[0]}) | Weekly ({nF[1]}) | Monthly ({nF[2]}) | Quarterly ({nF[3]}) | Annual ({nF[4]}) |
|---|---|---|---|---|---|
""" + "\n".join(f"| {lab} | " + " | ".join((f"**{c2(v)}**" if (lab == 'Whole book' and j == 2) else c2(v)) for j, v in enumerate(BYF.loc[key_])) + " |"
                for lab, key_ in [("Whole book", "Whole trend book"), ("US rates sleeve (ZT, ZF, ZN, UB)", "US rates sleeve"),
                                  ("Currency sleeve (9 pairs)", "Currency sleeve"), ("Everything except rates", "Everything except rates")]) + f"""

Monthly correlation for the other Euribor versions:

| Euribor version | Whole book | US rates sleeve | Currency sleeve | Everything except rates |
|---|---|---|---|---|
""" + "\n".join(f"| {lab} | " + " | ".join(c2(v) for v in MCR.loc[key_]) + " |"
                for lab, key_ in [("Frozen spec, 1 contract", "Frozen spec, 1 contract"),
                                  ("Frozen spec, €50,000 account (10% vol target)", "Frozen spec, EUR 50k account"),
                                  ("Follow-the-ECB, 1 contract", "Follow-the-ECB, 1 contract")]) + f"""

Monthly correlation by sub-period and its sampling range (block bootstrap, 12-month blocks, 10,000 draws):

| | 2011–15 ({int(sub['2011-2015']['months'])} months) | 2016–20 ({int(sub['2016-2020']['months'])}) | 2021–26 ({int(sub['2021-2026']['months'])}) | Full window | Bootstrap 5th to 95th percentile |
|---|---|---|---|---|---|
| Whole book | {c2(sub['2011-2015']['Whole trend book'])} | {c2(sub['2016-2020']['Whole trend book'])} | {c2(sub['2021-2026']['Whole trend book'])} | {c2(bi['Whole trend book']['observed'])} | {sg(bi['Whole trend book']['p05'])} to {sg(bi['Whole trend book']['p95'])} |
| US rates sleeve | {c2(sub['2011-2015']['US rates sleeve'])} | {c2(sub['2016-2020']['US rates sleeve'])} | {c2(sub['2021-2026']['US rates sleeve'])} | {c2(bi['US rates sleeve']['observed'])} | {sg(bi['US rates sleeve']['p05'])} to {sg(bi['US rates sleeve']['p95'])} |
| Currency sleeve | | | | {c2(bi['Currency sleeve']['observed'])} | {sg(bi['Currency sleeve']['p05'])} to {sg(bi['Currency sleeve']['p95'])} |

The rolling 36-month correlation with the whole book stays between {sg(rc.min())} and {sg(rc.max())} throughout, inside the range two unrelated series would produce (Figure 11, top).

![Figure 11. Correlation with the trend-following book](figures/fig11_bt50k_trend_correlation.png)

*Figure 11. Rolling 36-month correlation, and each year's P&L for both strategies in units of own volatility.*

## B2. Year by year

P&L in each strategy's own units, and scaled by its own annual volatility so the two are comparable (2011 from April, 2026 to April):

| Year | Trend book $ | Trend book, vol units | Euribor bp | Euribor, vol units |
|---|---|---|---|---|
""" + "\n".join(f"| {y} | {('+' if r.trend_book_usd >= 0 else MINUS)}{abs(r.trend_book_usd):,.0f} | {sg(r.trend_in_vol_units)} | {sg(r.euribor_bp, 0)} | {sg(r.euribor_in_vol_units)} |"
                for y, r in TY.iterrows()) + f"""

Euribor in the trend book's extreme months:

| Months | Trend book mean | Euribor mean | Euribor months positive |
|---|---|---|---|
""" + "\n".join(f"| {lab} | {('+' if v['trend_mean_usd'] >= 0 else MINUS)}${abs(v['trend_mean_usd']):,.0f} | {sg(v['euribor_mean_bp'], 1)} bp | {v['euribor_share_positive']:.0%} |"
                for lab, v in [("Trend book's 15 worst", cd["trend book's 15 worst months"]), ("Trend book's 15 best", cd["trend book's 15 best months"]),
                               (f"All {nF[2]}", cd["all months"])]) + f"""

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

    def rename(text):
        for a, b in [("Follow-the-ECB", "ECB rate momentum"), ("follow-the-ECB", "ECB rate momentum"), ("ECB rule", "ECB rate momentum"),
                     ("R+I+S", "risk-factor")]:
            text = text.replace(a, b)
        return text

    appendix = (f"# Euribor macro strategy: appendices to the €50,000 account backtest\n\nGenerated with the main report on {today()} "
                f"(cost {CB} bp per side). Appendix A is the last-five-years account (September 2021 to August 2026); Appendix B is the "
                f"correlation with the trend-following book. Section numbers refer to the main report.\n\n---\n\n" + APPA + "\n---\n\n" + APPB)
    return rename(MAIN), rename(appendix)


def main():
    REPORTS.mkdir(exist_ok=True)
    text = research_report()
    (REPORTS / "REPORT.md").write_text(text)
    print("REPORT.md written,", len(text), "chars")
    if (RESULTS / "bt50k_variants.csv").exists():
        main_text, appendix = account_report()
        (REPORTS / "BACKTEST_50K.md").write_text(main_text)
        (REPORTS / "BACKTEST_50K_APPENDIX.md").write_text(appendix)
        print("BACKTEST_50K.md and BACKTEST_50K_APPENDIX.md written")


if __name__ == "__main__":
    main()
