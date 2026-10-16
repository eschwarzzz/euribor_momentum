# euribor_macro

Macro-factor direction strategy for 3M Euribor futures, with a synthetic price series built from public data.
Read `STATUS.md` for the current state and `REPORT.md` for the original six-section test report.

Pipeline (rerun in order, Python 3.13, pandas / numpy / scikit-learn / matplotlib / openpyxl):

    python3 fetch_ecb.py        # ECB Data Portal series -> data/ecb_*.csv
    python3 build_futures.py    # daily synthetic quarterly contracts -> data/euribor_futures_continuous.csv
    python3 features.py         # monthly feature matrix + next-month target -> data/features_monthly.csv
    python3 backtest.py         # all variants -> results/*.csv
    python3 make_charts.py      # results/fig*.png
    python3 make_report.py      # REPORT.md

Non-ECB inputs already in `data/`: Bundesbank daily Euribor (`buba_euribor_*.csv`), Eurostat HICP and ESI, policyuncertainty.com EPU,
BIS locational banking statistics (`bis_lbs_ea.csv`), US Treasury TIC holdings (`tic_ea_holdings.csv`), FRED US rates.
Source URLs and key formats are documented at the top of each script and in the report appendix.
