"""Kalman (local-level) filtering of every feature before z-scoring. Causal: the noise ratio q is re-estimated each December by
maximum likelihood on data to date and used for the next 12 months. Fixed-gain (steady-state) variants as a check."""
import numpy as np, pandas as pd, os, sys, warnings
warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT); D = f"{ROOT}/data"; R = f"{ROOT}/results"
from backtest import daily_pnl, metrics, SUBS
from features import PRIOR
F = pd.read_csv(f"{D}/features_monthly.csv", index_col=0, parse_dates=True); y = F.pop("y_next"); F.pop("y0_next"); idx = F.index
cont = pd.read_csv(f"{D}/euribor_futures_continuous.csv", index_col=0, parse_dates=True)
P = pd.read_csv(f"{R}/monthly_positions.csv", index_col=0, parse_dates=True); ecb = P["BM follow-the-ECB (-sign of DFR 3M change)"]
cols = [c for c in F.columns if c[0] in "ris"]
QGRID = np.logspace(-4, 1, 26)
def ll_local_level(x, q):
    """Concentrated Gaussian log-likelihood of a local-level model with obs variance 1 and state variance q (scale-free)."""
    a, p, ll, n = x[0], 1e6, 0.0, 0
    for t in range(1, len(x)):
        p = p + q; f = p + 1.0; v = x[t] - a; ll += -0.5 * (np.log(f) + v * v / f); n += 1
        k = p / f; a = a + k * v; p = p * (1 - k)
    return ll
def kalman_filter(x, q):
    out = np.empty(len(x)); a, p = x[0], 1e6; out[0] = a
    for t in range(1, len(x)):
        p = p + q; f = p + 1.0; k = p / f; a = a + k * (x[t] - a); p = p * (1 - k); out[t] = a
    return out
def kalman_causal(s, min_obs=60):
    s = s.dropna(); x = (s / s.std()).values; out = pd.Series(np.nan, index=s.index); qs = {}
    years = sorted(set(s.index.year)); q = None
    for yr in years:
        hist = s.index.year < yr
        if hist.sum() >= min_obs:
            q = QGRID[np.argmax([ll_local_level(x[hist], qq) for qq in QGRID])]; qs[yr] = q
        if q is None: continue
        upto = s.index.year <= yr; filt = kalman_filter(x[upto], q) * s.std(); sel = s.index.year == yr; out[sel] = filt[upto][sel[upto]] if False else filt[np.where(upto)[0][sel[upto]] if False else (s.index.year[upto] == yr)]
    return out, qs
def fixed_gain(s, K):
    s = s.dropna(); out = np.empty(len(s)); a = s.iloc[0]
    for t, v in enumerate(s.values): a = a + K * (v - a); out[t] = a
    return pd.Series(out, index=s.index)
def z(s, minp=36): m = s.expanding(minp).mean(); sd = s.expanding(minp).std(); return ((s - m) / sd).clip(-3, 3)
def composite_from(Ff):
    Z = pd.DataFrame({c: z(Ff[c]) * PRIOR[c] for c in cols if PRIOR.get(c, 0) != 0})
    G = pd.DataFrame({g: Z[[c for c in Z.columns if c[0] == g]].mean(axis=1) for g in "ris"}); return G.mean(axis=1), G
TAUS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0]; TRAIN = ("2002-01-31", "2013-12-31"); TEST = ("2014-01-01", "2026-08-31"); FULL = ("2008-01-31", "2026-08-31")
def evaluate(score, label):
    def anchored(t): return pd.Series(np.where(score.abs() > t, np.sign(score), ecb), index=idx)
    cache = {t: daily_pnl(anchored(t), cont) for t in TAUS}; comp = daily_pnl(np.sign(score).reindex(idx), cont)
    trn = {t: metrics(*cache[t], start=TRAIN[0], end=TRAIN[1])["sharpe"] for t in TAUS}; best = max(trn.values()); t_star = max(t for t, v in trn.items() if abs(v - best) < 1e-9)
    # walk-forward tau
    pos_wf = ecb.copy()
    for yr in range(2008, 2027):
        s_ = {t: metrics(*cache[t], start="2002-01-31", end=f"{yr-1}-12-31")["sharpe"] for t in TAUS}; b = max(s_.values()); tt = max(t for t, v in s_.items() if abs(v - b) < 1e-9)
        m = idx.year == yr; pos_wf[m] = anchored(tt)[m]
    wf = daily_pnl(pos_wf, cont)
    ss = score.loc["2002-01-31":]
    return dict(variant=label, comp_sharpe_2008_26=metrics(*comp, start=FULL[0], end=FULL[1])["sharpe"], comp_test=metrics(*comp, start=TEST[0], end=TEST[1])["sharpe"], tau_train=t_star,
                anchored_test=metrics(*cache[t_star], start=TEST[0], end=TEST[1])["sharpe"], anchored_wf_2008_26=metrics(*wf, start=FULL[0], end=FULL[1])["sharpe"], anchored_2008_26_at_tau=metrics(*cache[t_star], start=FULL[0], end=FULL[1])["sharpe"],
                override_months_2008_26=int(((score.abs() > t_star) & (np.sign(score) != ecb)).loc[FULL[0]:FULL[1]].sum()), autocorr=ss.autocorr(1), sd=ss.std(), flips_per_yr=(np.sign(ss) != np.sign(ss).shift()).sum() / (len(ss) / 12),
                **{"wf " + k[:7]: metrics(*wf, start=a, end=b)["sharpe"] for k, (a, b) in SUBS.items()})
rows = []; score0, G0 = composite_from(F[cols]); rows.append(evaluate(score0, "unfiltered (current)"))
Fk = pd.DataFrame(index=idx); qlog = {}
for c in cols: Fk[c], qlog[c] = kalman_causal(F[c])
score_k, Gk = composite_from(Fk); rows.append(evaluate(score_k, "Kalman, q by ML (causal, yearly)"))
for K in (0.5, 0.3, 0.2, 0.1):
    Ff = pd.DataFrame({c: fixed_gain(F[c], K) for c in cols}).reindex(idx); sc, _ = composite_from(Ff); rows.append(evaluate(sc, f"fixed gain K={K} (steady-state Kalman / EMA)"))
T = pd.DataFrame(rows).set_index("variant"); pd.set_option("display.width", 260); print(T.round(2).to_string()); T.to_csv(f"{R}/kalman_results.csv")
qs = pd.DataFrame(qlog).T; print("\nML noise ratio q (state var / obs var) chosen for 2026, by feature (small = heavy smoothing):"); print(qs[2026].sort_values().round(4).to_string())
print("\ncorrelation of Kalman composite with the unfiltered composite:", round(score_k.corr(score0), 3), "| lag-1 cross-corr (Kalman lags unfiltered):", round(score_k.corr(score0.shift(1)), 3))
ecb_rule = daily_pnl(ecb, cont); print("rule only, test 2014-26:", round(metrics(*ecb_rule, start=TEST[0], end=TEST[1])["sharpe"], 2), "| 2008-26:", round(metrics(*ecb_rule, start=FULL[0], end=FULL[1])["sharpe"], 2))
pd.DataFrame({"unfiltered": score0, "kalman": score_k}).to_csv(f"{R}/kalman_scores.csv")
