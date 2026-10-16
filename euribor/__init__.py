"""Euribor momentum: an ECB policy-momentum strategy on 3M Euribor futures with a macro risk-factor override.

Pipeline (each step is a subcommand of ``python -m euribor``):

    fetch      download the public source series into data/raw
    futures    build the synthetic quarterly Euribor futures      -> data/processed
    features   build the monthly feature matrix and target        -> data/processed
    backtest   run every strategy variant on one contract         -> results
    montecarlo bootstrap, no-skill nulls, deflated Sharpe, CPCV  -> results
    account    EUR 50,000 account simulation and its Monte Carlo  -> results
    charts     all figures                                        -> reports/figures
    reports    REPORT.md and BACKTEST_50K*.md                     -> reports
"""
