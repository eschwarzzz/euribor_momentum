"""One-off studies on top of the pipeline outputs. Run from the repository root, e.g. ``python -m research.threshold``.

Each script reads results/ and data/processed and writes its own results/*.csv. They are kept because the reports
cite them (threshold choice, divergence map, instrument comparison, trend-book correlation) and because the
rejected ideas (credit demand, Kalman filtering, post-hoc corrections) are part of the trial count.
"""
