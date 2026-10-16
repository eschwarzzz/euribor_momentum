# Euribor momentum

A systematic strategy on the three-month Euribor future: **ECB policy momentum** as the backbone, with a
**macro risk-factor override**. Built from free public data, including a synthetic futures price series,
because no free history of ICE or Eurex Euribor futures exists. Research period September to October 2026.

**Status: research complete, specification frozen, not traded.** Prices are synthetic before 2019 and the
override's edge rests on two episodes. `reports/STATUS.md` has the full state of the evidence and the next steps.

## The strategy

Position for next month on the second quarterly contract, decided at each month-end:

1. **Anchor, ECB rate momentum.** Long if the deposit facility rate was cut in the last three months, short if it
   was raised, otherwise keep the previous position.
2. **Override, risk-factor score.** Three groups of monthly macro series (rates and policy, inflation, sentiment
   and stress), each turned into an expanding z-score with its sign fixed from theory, averaged into one number.
   When the score is above +0.5 the position is long, below −0.5 short, whatever the ECB did last.

Trade the second contract, roll on the front expiry. No further tuning on this sample.

## Headline results

One contract, January 2008 to August 2026 (224 months), after 0.5 bp per side and roll costs, synthetic prices:

| Strategy | Sharpe | Ann. P&L | Max DD |
|---|---|---|---|
| Long-only 2nd contract (benchmark) | +0.27 | +18 bp | −470 bp |
| 12-month price trend (benchmark) | +0.50 | +35 bp | −243 bp |
| ECB rate momentum alone | +0.85 | +58 bp | −162 bp |
| Macro composite alone (R+I+S) | +0.81 | +56 bp | −181 bp |
| **Frozen spec: anchor + override above 0.5** | **+1.09** in-sample, **+0.87** with a walk-forward threshold | +75 bp | −137 bp |
| Placebo (ridge on a shuffled target) | −0.21 | | |

As a €50,000 account at a 10% volatility target and 0.3 bp per side (`reports/BACKTEST_50K.md`): Sharpe +0.85,
CAGR 9.0%, worst drawdown −20%, final equity €256k; one fixed contract instead of volatility targeting gives
Sharpe +1.02. Block-bootstrap 90% interval for the Sharpe +0.3 to +1.2; no-skill nulls p ≤ 0.014. The result is
regime dependent: strong when the ECB moves (2008–12, 2022–26), flat at the zero lower bound (2013–19).

What did not work, and is kept in `research/` for the trial count: money supply, a credit-demand block (capex by
industry, investment by asset, bank lending survey), Kalman-filtered features, fitted ridge, lasso and logit models.

## Repository layout

```
euribor/            the implementation, one module per pipeline step
  config.py         paths, contract conventions, evaluation windows, variant names
  sources.py        downloads: ECB, Bundesbank, Eurostat, policyuncertainty.com, FRED, BIS, TIC, Eurex
  futures.py        synthetic quarterly futures from Euribor plus a forward premium (govt or OIS curve)
  features.py       monthly feature matrix with publication lags, prior signs, next-month target
  signals.py        ECB rate momentum, prior-sign composite, override, walk-forward threshold
  backtest.py       one-contract P&L engine, metrics, walk-forward models, the 45 variants
  montecarlo.py     block bootstrap, no-skill nulls, deflated Sharpe, CPCV, nested walk-forward
  account.py        EUR 50,000 account simulation and its Monte Carlo (full window and last five years)
  charts.py         figures 1 to 11;  plotting.py: shared style
  reports.py        REPORT.md and BACKTEST_50K*.md from results/;  render.py: HTML and PDF
research/           one-off studies the reports cite: threshold choice, divergence map, instrument
                    comparison, trend-book correlation, and the rejected ideas
data/raw/           downloaded sources (committed, so the backtest reruns offline)
data/processed/     synthetic futures and the feature matrix (rebuilt by `futures` and `features`)
results/            tables, Monte Carlo output, logs of every run; results/archive_0p5bp = the 0.5 bp account run
reports/            REPORT.md (original six-section test), BACKTEST_50K.md and its appendix, STATUS.md,
                    the PDF export, figures/
```

## Reproduce

Python 3.11 or later.

```sh
pip install -r requirements.txt
make all            # futures -> features -> backtest -> montecarlo -> account -> charts -> reports (~10 min)
make research       # the research scripts (kalman is the slow one)
make html           # self-contained HTML of the account report (needs markdown-it-py)
make pdf            # PDF through pandoc and tectonic
python -m euribor fetch                  # refresh every source in data/raw (network)
python -m euribor fetch --source ecb fred
python -m euribor collect-eurex          # append the trailing three weeks of real FEU3 settlements
```

Every step is also `python -m euribor <step>`; `python -m euribor --help` lists them. Each `make` target logs to
`results/logs/`. Large regenerable outputs (daily P&L curves, bootstrap draws) are not committed; `make all`
rebuilds them. The trend-book correlation (`research/trend_correlation.py`) needs a private P&L panel; its outputs
are committed so the appendix and figure 11 rebuild without it.

Rerunning the pipeline reproduces the committed results byte for byte (same data, same seeds).

## Data

| Source | Series | Files in `data/raw` |
|---|---|---|
| [Bundesbank BBIG1](https://api.statistiken.bundesbank.de) | daily Euribor 1W–12M since Dec 1998; EONIA swap curve 2005–14 | `buba_euribor_*.csv`, `euribor_daily.csv`, `eonia_swap_daily.csv` |
| [ECB Data Portal](https://data.ecb.europa.eu) | DFR, MRO, M1–M3, loans, MFI debt holdings, unemployment, AAA and all-issuer yield curves, CISS, Eurosystem assets, long-term yields | `ecb_*.csv` |
| [Eurostat](https://ec.europa.eu/eurostat) | HICP headline and core (ECOICOP v2, continues past 2025), economic sentiment indicator | `eurostat_hicp.csv`, `eurostat_esi.csv` |
| [policyuncertainty.com](https://www.policyuncertainty.com/europe_monthly.html) | European news-based policy uncertainty, EU and DE/FR/IT/ES | `epu_europe.xlsx` |
| [FRED](https://fred.stlouisfed.org) | US 2-year yield, fed funds, 3-month bill, 2s10s | `fred_*.csv` |
| [BIS LBS](https://stats.bis.org) | euro-area banks' cross-border claims by currency (13 countries summed) | `bis_lbs_ea.csv` |
| [US Treasury TIC](https://ticdata.treasury.gov) | euro-area holdings of US Treasuries | `tic_*.txt`, `tic_ea_holdings.csv` |
| [Eurex](https://www.eurex.com) | FEU3 settlements, collected from 27 Aug 2026 | `eurex_feu3_history.csv` |

The synthetic contract: futures rate = spot 3M Euribor + (AAA government forward − government spot) from the ECB
yield curve, deposit-curve fallback before September 2004; converges exactly to 100 − fixing at expiry. Pricing
off the Euribor deposit curve alone embeds the 3M/6M tenor basis and creates a fake convergence drift (long-only
Sharpe above 6 in 2013–19), which is how the construction was found. An OIS-based construction for 2005–14 agrees
at monthly frequency (correlation 0.90) and is run as a sensitivity. Twenty days of real Eurex settlements show the
synthetic is level-unbiased but noisy day to day.

## Caveats

1. Prices are synthetic before 2019; monthly measurement noise is about 10–20 bp.
2. The override's evidence is two episodes (October 2008, the 2021–22 inflation shorts); out of sample it adds
   about 0.02 Sharpe over the plain ECB rule.
3. The feature menu was chosen with hindsight and about 70 trials were run; the deflated Sharpe accounts for 45 to 70.
4. Three ECB cycles in the sample. Treat every month from September 2026 as the true hold-out.
