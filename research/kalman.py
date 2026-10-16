"""Kalman (local-level) filtering of every R, I and S feature before z-scoring.

Causal: the noise ratio q is re-estimated each December by maximum likelihood on data to date and used for the
next twelve months. Fixed-gain (steady-state) variants are a check. Rejected: no out-of-sample gain.
"""
import warnings

import numpy as np
import pandas as pd

from euribor.backtest import daily_pnl, metrics
from euribor.config import ECB_RULE, RESULTS, SUBPERIODS
from euribor.data import load_continuous, load_features, load_positions
from euribor.features import PRIOR
from euribor.signals import override, walk_forward_threshold

warnings.filterwarnings("ignore")
Q_GRID = np.logspace(-4, 1, 26)
TAUS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0]
TRAIN, TEST, FULL = ("2002-01-31", "2013-12-31"), ("2014-01-01", "2026-08-31"), ("2008-01-31", "2026-08-31")


def log_likelihood(x, q):
    """Concentrated Gaussian log-likelihood of a local-level model with observation variance 1 and state variance q."""
    a, p, ll = x[0], 1e6, 0.0
    for t in range(1, len(x)):
        p = p + q
        f = p + 1.0
        v = x[t] - a
        ll += -0.5 * (np.log(f) + v * v / f)
        k = p / f
        a = a + k * v
        p = p * (1 - k)
    return ll


def kalman_filter(x, q):
    out = np.empty(len(x))
    a, p = x[0], 1e6
    out[0] = a
    for t in range(1, len(x)):
        p = p + q
        f = p + 1.0
        k = p / f
        a = a + k * (x[t] - a)
        p = p * (1 - k)
        out[t] = a
    return out


def kalman_causal(s, min_obs=60):
    """Filter a feature with q chosen each year on the years before it. Returns the filtered series and the q path."""
    s = s.dropna()
    x = (s / s.std()).values
    out = pd.Series(np.nan, index=s.index)
    chosen = {}
    q = None
    for year in sorted(set(s.index.year)):
        history = s.index.year < year
        if history.sum() >= min_obs:
            q = Q_GRID[np.argmax([log_likelihood(x[history], qq) for qq in Q_GRID])]
            chosen[year] = q
        if q is None:
            continue
        upto = s.index.year <= year
        filtered = kalman_filter(x[upto], q) * s.std()
        out[s.index.year == year] = filtered[s.index.year[upto] == year]
    return out, chosen


def fixed_gain(s, gain):
    s = s.dropna()
    out = np.empty(len(s))
    a = s.iloc[0]
    for t, v in enumerate(s.values):
        a = a + gain * (v - a)
        out[t] = a
    return pd.Series(out, index=s.index)


def zscore(s, min_periods=36):
    return ((s - s.expanding(min_periods).mean()) / s.expanding(min_periods).std()).clip(-3, 3)


def composite_from(Ff, cols):
    Z = pd.DataFrame({c: zscore(Ff[c]) * PRIOR[c] for c in cols if PRIOR.get(c, 0) != 0})
    G = pd.DataFrame({g: Z[[c for c in Z.columns if c[0] == g]].mean(axis=1) for g in "ris"})
    return G.mean(axis=1), G


def main():
    pd.set_option("display.width", 260)
    F, _, _ = load_features()
    idx = F.index
    cont = load_continuous()
    ecb = load_positions()[ECB_RULE]
    cols = [c for c in F.columns if c[0] in "ris"]

    def evaluate(score, label):
        cache = {t: daily_pnl(override(ecb, score, t), cont) for t in TAUS}
        comp = daily_pnl(np.sign(score).reindex(idx), cont)
        train = {t: metrics(*cache[t], start=TRAIN[0], end=TRAIN[1])["sharpe"] for t in TAUS}
        best = max(train.values())
        t_star = max(t for t, v in train.items() if abs(v - best) < 1e-9)
        pos_wf, _ = walk_forward_threshold(ecb, score, cont, years=range(2008, 2027), taus=TAUS, before=ecb)
        wf = daily_pnl(pos_wf, cont)
        ss = score.loc["2002-01-31":]
        return dict(variant=label, comp_sharpe_2008_26=metrics(*comp, start=FULL[0], end=FULL[1])["sharpe"],
                    comp_test=metrics(*comp, start=TEST[0], end=TEST[1])["sharpe"], tau_train=t_star,
                    anchored_test=metrics(*cache[t_star], start=TEST[0], end=TEST[1])["sharpe"],
                    anchored_wf_2008_26=metrics(*wf, start=FULL[0], end=FULL[1])["sharpe"],
                    anchored_2008_26_at_tau=metrics(*cache[t_star], start=FULL[0], end=FULL[1])["sharpe"],
                    override_months_2008_26=int(((score.abs() > t_star) & (np.sign(score) != ecb)).loc[FULL[0]:FULL[1]].sum()),
                    autocorr=ss.autocorr(1), sd=ss.std(), flips_per_yr=(np.sign(ss) != np.sign(ss).shift()).sum() / (len(ss) / 12),
                    **{"wf " + k[:7]: metrics(*wf, start=a, end=b)["sharpe"] for k, (a, b) in SUBPERIODS.items()})

    rows = []
    score0, _ = composite_from(F[cols], cols)
    rows.append(evaluate(score0, "unfiltered (current)"))
    Fk = pd.DataFrame(index=idx)
    q_log = {}
    for c in cols:
        Fk[c], q_log[c] = kalman_causal(F[c])
    score_k, _ = composite_from(Fk, cols)
    rows.append(evaluate(score_k, "Kalman, q by ML (causal, yearly)"))
    for gain in (0.5, 0.3, 0.2, 0.1):
        Ff = pd.DataFrame({c: fixed_gain(F[c], gain) for c in cols}).reindex(idx)
        rows.append(evaluate(composite_from(Ff, cols)[0], f"fixed gain K={gain} (steady-state Kalman / EMA)"))
    T = pd.DataFrame(rows).set_index("variant")
    print(T.round(2).to_string())
    T.to_csv(RESULTS / "kalman_results.csv")
    qs = pd.DataFrame(q_log).T
    print("\nML noise ratio q (state var / obs var) chosen for 2026, by feature (small = heavy smoothing):")
    print(qs[2026].sort_values().round(4).to_string())
    print("\ncorrelation of Kalman composite with the unfiltered composite:", round(score_k.corr(score0), 3),
          "| lag-1 cross-corr (Kalman lags unfiltered):", round(score_k.corr(score0.shift(1)), 3))
    rule = daily_pnl(ecb, cont)
    print("rule only, test 2014-26:", round(metrics(*rule, start=TEST[0], end=TEST[1])["sharpe"], 2),
          "| 2008-26:", round(metrics(*rule, start=FULL[0], end=FULL[1])["sharpe"], 2))
    pd.DataFrame({"unfiltered": score0, "kalman": score_k}).to_csv(RESULTS / "kalman_scores.csv")


if __name__ == "__main__":
    main()
