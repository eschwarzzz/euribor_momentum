# Reproduce the project. Every target logs to results/logs/<step>.log.
PY ?= python3
LOG = results/logs

.PHONY: all fetch futures features backtest montecarlo account charts reports research html pdf clean

all: futures features backtest montecarlo account charts reports

fetch:        ; $(PY) -m euribor fetch       2>&1 | tee $(LOG)/fetch.log
futures:      ; $(PY) -m euribor futures     2>&1 | tee $(LOG)/futures.log
features:     ; $(PY) -m euribor features    2>&1 | tee $(LOG)/features.log
backtest:     ; $(PY) -m euribor backtest    2>&1 | tee $(LOG)/backtest.log
montecarlo:   ; $(PY) -m euribor montecarlo  2>&1 | tee $(LOG)/montecarlo.log
account:      ; $(PY) -m euribor account     2>&1 | tee $(LOG)/account.log
charts:       ; $(PY) -m euribor charts      2>&1 | tee $(LOG)/charts.log
reports:      ; $(PY) -m euribor reports     2>&1 | tee $(LOG)/reports.log
html:         ; $(PY) -m euribor render BACKTEST_50K.md
pdf:          ; $(PY) -m euribor render --pdf BACKTEST_50K.md

# The research scripts the reports cite (threshold choice, divergence map, instrument comparison, rejected ideas).
# trend_correlation needs the private trend-book P&L panel: set TREND_PANEL=/path/to/pnl_panel.csv.
research:
	$(PY) -m research.threshold            2>&1 | tee $(LOG)/threshold.log
	$(PY) -m research.compare_instruments  2>&1 | tee $(LOG)/compare_instruments.log
	$(PY) -m research.divergence           2>&1 | tee $(LOG)/divergence.log
	$(PY) -m research.corrections          2>&1 | tee $(LOG)/corrections.log
	$(PY) -m research.credit_demand        2>&1 | tee $(LOG)/credit_demand.log
	$(PY) -m research.kalman               2>&1 | tee $(LOG)/kalman.log

clean:
	rm -rf euribor/__pycache__ research/__pycache__ results/_* reports/*.html reports/*.tex
