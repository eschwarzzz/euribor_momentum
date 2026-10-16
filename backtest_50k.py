"""EUR 50,000 account backtest of the frozen specification (ECB anchor + R+I+S override above 0.5) on the 2nd Euribor contract.
Sizing: at each month-end, contracts = round(vol target x equity / (sigma x EUR 2,500)), sigma = 0.7 x trailing 60-day realised vol
+ 0.3 x its expanding long-run mean (annualised, price points). Positions resized monthly with the signal, whole contracts only.
Money: EUR 2,500 per price point (EUR 25 per bp), COST_BP per side (0.3 bp = EUR 7.50 per contract: half a tick plus fees), roll = two sides,
initial margin EUR 237 per contract (broker quote, Sep 2026). Cash earns nothing. Window Jan 2008 - Aug 2026 (224 months).
Then the same Monte Carlo set as montecarlo.py, in account terms: block bootstrap of Sharpe / final equity / drawdown,
circular-shift and block-permutation nulls on the direction, deflated Sharpe."""
import numpy as np, pandas as pd, os, sys, json, warnings
from scipy.stats import norm, skew, kurtosis
warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT); D = f"{ROOT}/data"; R = f"{ROOT}/results"
from backtest import daily_pnl, metrics, SUBS, COST
rng = np.random.default_rng(42)
CAPITAL = 50_000.0; PT = 2_500.0; MARGIN = 237.0; TARGET = 0.10; COST_BP = 0.3; COST50 = COST_BP / 100     # price points per contract per side
START = "2008-01-01"; END = "2026-08-31"

# ---------- inputs ----------
F = pd.read_csv(f"{D}/features_monthly.csv", index_col=0, parse_dates=True); idx = F.index
cont = pd.read_csv(f"{D}/euribor_futures_continuous.csv", index_col=0, parse_dates=True)
P = pd.read_csv(f"{R}/monthly_positions.csv", index_col=0, parse_dates=True); G = pd.read_csv(f"{R}/prior_group_scores.csv", index_col=0, parse_dates=True)
ecb = P["BM follow-the-ECB (-sign of DFR 3M change)"]; score = G[["R", "I", "S"]].mean(axis=1)
def anchored(tau): return pd.Series(np.where(score.abs() > tau, np.sign(score), ecb), index=idx)
def instrument(c):
    v60 = c["chg1"].rolling(60).std() * np.sqrt(252)              # price points per year
    return dict(chg=c["chg1"].fillna(0.0), roll=((c["exp1"] != c["exp1"].shift(1)) & (np.arange(len(c)) > 0)).astype(float), vol60=v60, vol=0.7 * v60 + 0.3 * v60.expanding(250).mean())
GOV = instrument(cont); OIS = instrument(pd.read_csv(f"{D}/euribor_futures_continuous_ois.csv", index_col=0, parse_dates=True))     # OIS file = OIS-based 2005-14 spliced into the govt-curve series
vol60 = GOV["vol60"]; vol_blend = GOV["vol"]

# walk-forward threshold: re-picked each December on unit-position Sharpe from 2002 to that date (same rule as threshold_test.py)
TAUS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.25, 1.5]; unit = {t: daily_pnl(anchored(t), cont) for t in TAUS}
def pick(b):
    s = pd.Series({t: metrics(*unit[t], start="2002-01-31", end=b)["sharpe"] for t in TAUS}); return max(t for t, v in s.items() if abs(v - s.max()) < 1e-9)
pos_wf = pd.Series(np.nan, index=idx); tau_path = {}
for yr in range(2007, 2027):
    tau_path[yr] = pick(f"{yr-1}-12-31"); m = idx.year == yr; pos_wf[m] = anchored(tau_path[yr])[m]

# ---------- account simulation ----------
def simulate(pos_m, target=TARGET, vol=None, fixed=None, cost=COST50, start=START, end=END, capital=CAPITAL, inst=GOV):
    """pos_m: direction decided at each month-end, held from the next trading day. Returns a daily frame and a monthly decision frame."""
    chg, roll, vol60 = inst["chg"], inst["roll"], inst["vol60"]; vol = inst["vol"] if vol is None else vol
    days = chg.loc[start:end].index; dec = [t for t in idx if pd.Timestamp(start) - pd.offsets.MonthEnd(1) <= t < pd.Timestamp(end)]
    eq = capital; prev = 0.0; rows = []; drows = []
    for t in dec:
        dd = days[(days > t) & (days <= t + pd.offsets.MonthEnd(1))]
        if len(dd) == 0: continue
        sig = vol.loc[:t].iloc[-1]; s = pos_m.get(t, 0.0); s = 0.0 if pd.isna(s) else float(s)
        n = float(fixed) if fixed is not None else np.round(target * eq / (sig * PT))
        n = n * abs(s) if abs(s) <= 1 else n; pos = np.sign(s) * n; eq0 = eq
        c = chg.loc[dd].values; r = roll.loc[dd].values
        fees = np.zeros(len(dd)); fees[0] = abs(pos - prev) * cost * PT; fees += r * abs(pos) * 2 * cost * PT
        pnl = pos * c * PT - fees
        for d, x, fe in zip(dd, pnl, fees):
            eq += x; rows.append((d, pos, x, fe, eq))
        drows.append(dict(date=t, signal=s, sigma_bp=sig * 100, contracts=pos, equity_start=eq0, traded=abs(pos - prev), pnl=eq - eq0, ret=(eq - eq0) / eq0, fees=fees.sum(),
                          risk_fcst=abs(pos) * sig * PT / eq0, chg_pts=c.sum(), rolls=r.sum()))
        prev = pos
    d = pd.DataFrame(rows, columns=["date", "contracts", "pnl", "fees", "equity"]).set_index("date")
    d["ret"] = d["pnl"] / d["equity"].shift(1).fillna(capital)
    d["margin"] = d["contracts"].abs() * MARGIN; d["margin_pct"] = d["margin"] / d["equity"]
    v = vol60.reindex(d.index); d["margin_stress"] = d["contracts"].abs() * MARGIN * np.maximum(1.0, v / v.iloc[-1]); d["margin_stress_pct"] = d["margin_stress"] / d["equity"]
    return d, pd.DataFrame(drows).set_index("date")

def stats(d, m, capital=CAPITAL):
    r = d["ret"]; n = len(r); eq = d["equity"]; dd = eq / eq.cummax() - 1; ddeur = (eq - eq.cummax()).min(); mr = m["ret"]
    return dict(final_equity=eq.iloc[-1], pnl_eur=eq.iloc[-1] - capital, cagr_pct=((eq.iloc[-1] / capital) ** (252 / n) - 1) * 100, vol_pct=r.std() * np.sqrt(252) * 100,
                sharpe=r.mean() / r.std() * np.sqrt(252), sharpe_monthly=mr.mean() / mr.std() * np.sqrt(12), maxdd_pct=dd.min() * 100, maxdd_eur=ddeur,
                worst_month_pct=mr.min() * 100, best_month_pct=mr.max() * 100, hit_pct=(mr > 0).mean() * 100, avg_contracts=d["contracts"].abs().mean(), max_contracts=d["contracts"].abs().max(),
                avg_margin_pct=d["margin_pct"].mean() * 100, peak_margin_pct=d["margin_pct"].max() * 100, peak_margin_stress_pct=d["margin_stress_pct"].max() * 100,
                fees_eur=d["fees"].sum(), contracts_traded=m["traded"].sum() + 2 * (m["rolls"] * m["contracts"].abs()).sum())

ones = pd.Series(1.0, index=idx); frozen = anchored(0.5)
variants = {
    "Frozen spec, 10% vol target": dict(pos_m=frozen),
    "Walk-forward threshold, 10% vol": dict(pos_m=pos_wf),
    "Follow-the-ECB only, 10% vol": dict(pos_m=ecb),
    "Long-only, 10% vol": dict(pos_m=ones),
    "12M trend, 10% vol": dict(pos_m=P["BM trend 12M"]),
    "Frozen, 5% vol target": dict(pos_m=frozen, target=0.05),
    "Frozen, 15% vol target": dict(pos_m=frozen, target=0.15),
    "Frozen, 20% vol target": dict(pos_m=frozen, target=0.20),
    "Frozen, 60-day vol only (no long-run blend)": dict(pos_m=frozen, vol=vol60),
    "Frozen, fixed 1 contract": dict(pos_m=frozen, fixed=1),
    "Frozen, fixed 3 contracts": dict(pos_m=frozen, fixed=3),
    "Frozen, cost 0.5 bp/side": dict(pos_m=frozen, cost=0.005),
    "Frozen, cost 1 bp/side": dict(pos_m=frozen, cost=0.01),
    "Frozen, cost 2 bp/side": dict(pos_m=frozen, cost=0.02),
    "Frozen, start Jan 2002": dict(pos_m=frozen, start="2002-01-01"),
    "Frozen, OIS-spliced prices 2005-14": dict(pos_m=frozen, inst=OIS),
    "Follow-the-ECB, OIS-spliced prices": dict(pos_m=ecb, inst=OIS),
}
runs = {k: simulate(**kw) for k, kw in variants.items()}; S = pd.DataFrame({k: stats(*v) for k, v in runs.items()}).T
pd.set_option("display.width", 260); pd.set_option("display.max_columns", 30)
print(f"walk-forward tau path: {tau_path}")
print(f"\n[0] Account results, EUR 50,000 start, Jan 2008 - Aug 2026, cost {COST_BP} bp per side:")
print(S[["final_equity", "pnl_eur", "cagr_pct", "vol_pct", "sharpe", "sharpe_monthly", "maxdd_pct", "maxdd_eur", "worst_month_pct", "hit_pct"]].round(2).to_string())
print(S[["avg_contracts", "max_contracts", "avg_margin_pct", "peak_margin_pct", "peak_margin_stress_pct", "fees_eur", "contracts_traded"]].round(2).to_string())
d, m = runs["Frozen spec, 10% vol target"]; u = metrics(*daily_pnl(frozen, cont, cost=COST50), start=START, end=END)
print(f"\nunit-position check on this window: Sharpe {u['sharpe']:+.2f}, {u['ann_ret_bp']:+.0f} bp/yr, vol {u['ann_vol_bp']:.0f} bp, max DD {u['maxdd_bp']:.0f} bp")
yr = pd.DataFrame({"pnl_eur": d["pnl"].groupby(d.index.year).sum(), "ret_pct": d["ret"].groupby(d.index.year).apply(lambda x: (1 + x).prod() - 1) * 100,
                   "equity_end": d["equity"].groupby(d.index.year).last(), "avg_contracts": d["contracts"].groupby(d.index.year).mean(), "sigma_bp": m["sigma_bp"].groupby(m.index.year + (m.index.month == 12)).mean(),
                   "peak_margin_pct": d["margin_pct"].groupby(d.index.year).max() * 100})
print("\n[0b] Frozen spec by calendar year (contracts signed, + long / - short):"); print(yr.round(1).to_string())
sub = {}
for k in list(variants)[:4]:
    dk = runs[k][0]
    for sname, (a, b) in SUBS.items():
        x = dk["ret"].loc[a:b]; sub.setdefault(k, {})[sname] = x.mean() / x.std() * np.sqrt(252)
SUBT = pd.DataFrame(sub).T; print("\n[0c] Sub-period Sharpe (account returns):"); print(SUBT.round(2).to_string())
eq = d["equity"]; ddser = eq / eq.cummax() - 1; trough = ddser.idxmin(); peak = eq.loc[:trough].idxmax(); rec = eq.loc[trough:][eq.loc[trough:] >= eq.loc[peak]].index
print(f"\nworst drawdown: {ddser.min()*100:.1f}% from {peak.date()} to {trough.date()}, recovered {rec[0].date() if len(rec) else 'not yet'}; longest time under water {int((ddser < 0).astype(int).groupby((ddser == 0).cumsum()).sum().max())} trading days")
tot = m["pnl"].sum(); lr = np.log1p(d["ret"])
print(f"concentration: best 5 months = {m['pnl'].nlargest(5).sum()/tot:.0%} of total P&L, best 10 = {m['pnl'].nlargest(10).sum()/tot:.0%}; share of log growth 2008-12 {lr.loc['2008':'2012'].sum()/lr.sum():.0%}, 2013-21 {lr.loc['2013':'2021'].sum()/lr.sum():.0%}, 2022-26 {lr.loc['2022':].sum()/lr.sum():.0%}")
print(f"direction flips {int((np.sign(m['contracts']).diff().abs() > 0).sum())}, months with a resize {int((m['traded'] > 0).sum())} of {len(m)}; margin EUR mean {d['margin'].mean():,.0f}, peak {d['margin'].max():,.0f} on {d['margin'].idxmax().date()}; last position {m['contracts'].iloc[-1]:+.0f} contracts on equity {m['equity_start'].iloc[-1]:,.0f}")
print(f"realised vs target: account vol {S.loc['Frozen spec, 10% vol target', 'vol_pct']:.1f}% vs 10%; forecast risk at entry mean {m['risk_fcst'].mean()*100:.1f}%, range {m['risk_fcst'].min()*100:.1f}-{m['risk_fcst'].max()*100:.1f}%; months flat (0 contracts) {(m['contracts'] == 0).sum()}")

# ---------- Monte Carlo ----------
def sharpe_m(x): return np.nan if x.std() == 0 else x.mean() / x.std() * np.sqrt(12)
keys = {"Frozen spec": "Frozen spec, 10% vol target", "Walk-forward threshold": "Walk-forward threshold, 10% vol", "Follow-the-ECB": "Follow-the-ECB only, 10% vol", "Long-only": "Long-only, 10% vol"}
M = pd.DataFrame({k: runs[v][1]["ret"] for k, v in keys.items()}); T = len(M); NB = 10000; L = 12
print(f"\nmonthly account returns: {T} months, monthly-based Sharpe:", M.apply(sharpe_m).round(2).to_dict())

# 1. block bootstrap: the same resampled months for every strategy, so paired comparisons are valid
def bootstrap(M, rng, L=L):
    T = len(M); nb = int(np.ceil(T / L)); starts = rng.integers(0, T, (NB, nb)); bidx = ((starts[:, :, None] + np.arange(L)[None, None, :]).reshape(NB, -1) % T)[:, :T]
    boot = {}; paths = {}
    for k in M.columns:
        x = M[k].values[bidx]; e = CAPITAL * np.cumprod(1 + x, axis=1); pk = np.maximum.accumulate(np.concatenate([np.full((NB, 1), CAPITAL), e], axis=1), axis=1)[:, 1:]
        boot[k] = pd.DataFrame({"sharpe": x.mean(1) / x.std(1) * np.sqrt(12), "final_equity": e[:, -1], "cagr_pct": ((e[:, -1] / CAPITAL) ** (12 / T) - 1) * 100, "maxdd_pct": (e / pk - 1).min(1) * 100,
                                "eq_1y": e[:, 11], "eq_5y": e[:, 59]})
        paths[k] = e
    return boot, paths
boot, paths = bootstrap(M, rng)
q = [5, 25, 50, 75, 95]
def summ(v): return dict(mean=v.mean(), **{f"p{p:02d}": np.percentile(v, p) for p in q})
B = pd.DataFrame({k: dict(**summ(boot[k]["sharpe"]), prob_gt0=(boot[k]["sharpe"] > 0).mean()) for k in boot}).T
B.loc["Frozen spec", "prob_beats_longonly"] = (boot["Frozen spec"]["sharpe"] > boot["Long-only"]["sharpe"]).mean(); B.loc["Frozen spec", "prob_beats_ecb"] = (boot["Frozen spec"]["sharpe"] > boot["Follow-the-ECB"]["sharpe"]).mean()
B.loc["Walk-forward threshold", "prob_beats_longonly"] = (boot["Walk-forward threshold"]["sharpe"] > boot["Long-only"]["sharpe"]).mean(); B.loc["Walk-forward threshold", "prob_beats_ecb"] = (boot["Walk-forward threshold"]["sharpe"] > boot["Follow-the-ECB"]["sharpe"]).mean()
print(f"\n[1] Block bootstrap ({L}-month blocks, {NB:,} paths of {T} months) of realised Sharpe:"); print(B.round(2).to_string())
def pnl_summary(boot):
    PL = {}
    for k in boot:
        b = boot[k]; PL[k] = dict(final_p05=np.percentile(b["final_equity"], 5), final_p25=np.percentile(b["final_equity"], 25), final_p50=np.percentile(b["final_equity"], 50), final_p75=np.percentile(b["final_equity"], 75), final_p95=np.percentile(b["final_equity"], 95),
                                  prob_end_below_start=(b["final_equity"] < CAPITAL).mean(), cagr_p05=np.percentile(b["cagr_pct"], 5), cagr_p50=np.percentile(b["cagr_pct"], 50), cagr_p95=np.percentile(b["cagr_pct"], 95),
                                  maxdd_p50=np.percentile(b["maxdd_pct"], 50), maxdd_p05=np.percentile(b["maxdd_pct"], 5), maxdd_p01=np.percentile(b["maxdd_pct"], 1), prob_dd_gt20=(b["maxdd_pct"] < -20).mean(), prob_dd_gt30=(b["maxdd_pct"] < -30).mean(),
                                  pnl1y_p05=np.percentile(b["eq_1y"], 5) - CAPITAL, pnl1y_p50=np.percentile(b["eq_1y"], 50) - CAPITAL, pnl1y_p95=np.percentile(b["eq_1y"], 95) - CAPITAL, prob_loss_1y=(b["eq_1y"] < CAPITAL).mean(),
                                  pnl5y_p05=np.percentile(b["eq_5y"], 5) - CAPITAL, pnl5y_p50=np.percentile(b["eq_5y"], 50) - CAPITAL, pnl5y_p95=np.percentile(b["eq_5y"], 95) - CAPITAL, prob_loss_5y=(b["eq_5y"] < CAPITAL).mean())
    return pd.DataFrame(PL).T
PLT = pnl_summary(boot); print("\n[1b] Bootstrap of the P&L path from EUR 50,000 (final equity after 224 months, drawdown, 1-year and 5-year P&L):"); print(PLT.round(3).T.to_string())

# 2. no-skill nulls: the direction path is shifted / block-shuffled in time, the size of the position (contracts per euro) stays with its date
def null_test(mm, block=12, n_perm=3000, rng=rng):
    sgn = np.sign(mm["contracts"]).values; w = (mm["contracts"].abs() / mm["equity_start"]).values; y = mm["chg_pts"].values; rl = mm["rolls"].values; Tn = len(mm)
    def ret(s):
        p = s * w; tr = np.abs(np.diff(p, prepend=0.0)); return p * y * PT - tr * COST50 * PT - rl * np.abs(p) * 2 * COST50 * PT
    obs = sharpe_m(ret(sgn)); shifts = np.array([sharpe_m(ret(np.roll(sgn, s))) for s in range(6, Tn - 6)])
    nbk = int(np.ceil(Tn / block)); perm = np.empty(n_perm)
    for i in range(n_perm):
        order = rng.permutation(nbk); ii = np.concatenate([np.arange(b * block, min((b + 1) * block, Tn)) for b in order]); perm[i] = sharpe_m(ret(sgn[ii]))
    return dict(observed=obs, shift_mean=shifts.mean(), shift_sd=shifts.std(), p_shift=(shifts >= obs).mean(), perm_mean=perm.mean(), perm_sd=perm.std(), perm_p95=np.percentile(perm, 95), p_perm=(perm >= obs).mean()), perm
nulls = {}; perms = {}
for name, key in list(keys.items())[:3]: nulls[name], perms[name] = null_test(runs[key][1])
N = pd.DataFrame(nulls).T; print("\n[2] No-skill nulls (direction shifted / block-permuted against the same returns and sizes), p = share of null Sharpes >= observed:"); print(N.round(3).to_string())

# 3. deflated Sharpe: trial dispersion from the 45 backtest variants on file; 70 trials in total per STATUS.md
C = pd.read_csv(f"{R}/daily_pnl_curves.csv", index_col=0, parse_dates=True); trial = (C.loc["2008-01-31":END].resample("ME").sum()).apply(lambda s: s.mean() / s.std()).dropna(); V = trial.var(); g = 0.5772156649
def dsr(x, nt):
    sr0 = np.sqrt(V) * ((1 - g) * norm.ppf(1 - 1 / nt) + g * norm.ppf(1 - 1 / (nt * np.e))); sr = x.mean() / x.std(); g3 = skew(x); g4 = kurtosis(x, fisher=False)
    return norm.cdf((sr - sr0) * np.sqrt(len(x) - 1) / np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2)), sr0 * np.sqrt(12)
DS = {k: dict(sharpe=sharpe_m(M[k]), skew=skew(M[k]), kurt=kurtosis(M[k], fisher=False), dsr_45=dsr(M[k], len(trial))[0], dsr_70=dsr(M[k], 70)[0]) for k in M.columns}
print(f"\n[3] Deflated Sharpe: expected max Sharpe under the null = {dsr(M['Frozen spec'], len(trial))[1]:.2f} ({len(trial)} trials) / {dsr(M['Frozen spec'], 70)[1]:.2f} (70 trials), annualised")
print(pd.DataFrame(DS).T.round(2).to_string())

# ---------- outputs ----------
d.to_csv(f"{R}/bt50k_daily.csv"); m.to_csv(f"{R}/bt50k_monthly.csv"); S.to_csv(f"{R}/bt50k_variants.csv"); yr.to_csv(f"{R}/bt50k_by_year.csv"); SUBT.to_csv(f"{R}/bt50k_subperiods.csv")
pd.DataFrame({k: runs[v][0]["equity"] for k, v in keys.items()}).to_csv(f"{R}/bt50k_equity_curves.csv")
pd.DataFrame({f"{k}|{c}": boot[k][c] for k in boot for c in ["sharpe", "final_equity", "maxdd_pct", "eq_1y", "eq_5y"]}).to_csv(f"{R}/bt50k_bootstrap.csv", index=False)
pd.DataFrame({f"p{p:02d}": np.percentile(paths["Frozen spec"], p, axis=0) for p in q}).to_csv(f"{R}/bt50k_bootstrap_fan.csv", index=False)
pd.DataFrame({"perm_sharpe": perms["Frozen spec"]}).to_csv(f"{R}/bt50k_null_perm.csv", index=False)
json.dump(dict(bootstrap_sharpe=B.to_dict("index"), bootstrap_pnl=PLT.to_dict("index"), nulls=nulls, deflated=DS, tau_path=tau_path, unit_check={k: float(v) for k, v in u.items()}, cost_bp=COST_BP), open(f"{R}/bt50k_mc.json", "w"), indent=1, default=float)

# ---------- last five years: a fresh EUR 50,000 account started 1 September 2021 ----------
START5 = "2021-09-01"; rng5 = np.random.default_rng(5)
assert (pos_wf.loc["2021-08-31":END] == frozen.loc["2021-08-31":END]).all()          # walk-forward threshold = 0.5 throughout, so it is the frozen spec here
variants5 = {k: variants[k] for k in ["Frozen spec, 10% vol target", "Follow-the-ECB only, 10% vol", "Long-only, 10% vol", "12M trend, 10% vol", "Frozen, 5% vol target", "Frozen, 15% vol target", "Frozen, 20% vol target",
                                      "Frozen, 60-day vol only (no long-run blend)", "Frozen, fixed 1 contract", "Frozen, fixed 3 contracts", "Frozen, cost 0.5 bp/side", "Frozen, cost 1 bp/side", "Frozen, cost 2 bp/side"]}
variants5["Follow-the-ECB, fixed 3 contracts"] = dict(pos_m=ecb, fixed=3)          # separates the override's own edge from the effect of volatility sizing
runs5 = {k: simulate(**{**kw, "start": START5}) for k, kw in variants5.items()}; S5 = pd.DataFrame({k: stats(*v) for k, v in runs5.items()}).T
print(f"\n\n===== LAST FIVE YEARS: fresh EUR 50,000 account, Sep 2021 - Aug 2026 (walk-forward threshold is 0.5 throughout = frozen spec) =====")
print(S5[["final_equity", "pnl_eur", "cagr_pct", "vol_pct", "sharpe", "sharpe_monthly", "maxdd_pct", "maxdd_eur", "worst_month_pct", "hit_pct"]].round(2).to_string())
print(S5[["avg_contracts", "max_contracts", "avg_margin_pct", "peak_margin_pct", "peak_margin_stress_pct", "fees_eur", "contracts_traded"]].round(2).to_string())
d5, m5 = runs5["Frozen spec, 10% vol target"]; u5 = metrics(*daily_pnl(frozen, cont, cost=COST50), start=START5, end=END); ue5 = metrics(*daily_pnl(ecb, cont, cost=COST50), start=START5, end=END)
print(f"\nunit-position check: frozen Sharpe {u5['sharpe']:+.2f}, {u5['ann_ret_bp']:+.0f} bp/yr, vol {u5['ann_vol_bp']:.0f} bp, max DD {u5['maxdd_bp']:.0f} bp | follow-the-ECB Sharpe {ue5['sharpe']:+.2f}, {ue5['ann_ret_bp']:+.0f} bp/yr")
x = d["ret"].loc[START5:]; print(f"same window inside the 2008-start account: Sharpe {x.mean()/x.std()*np.sqrt(252):+.2f}, return {((1+x).prod()-1)*100:+.1f}%")
yr5 = pd.DataFrame({"pnl_eur": d5["pnl"].groupby(d5.index.year).sum(), "ret_pct": d5["ret"].groupby(d5.index.year).apply(lambda x: (1 + x).prod() - 1) * 100, "equity_end": d5["equity"].groupby(d5.index.year).last(),
                    "avg_contracts": d5["contracts"].groupby(d5.index.year).mean(), "avg_margin_pct": d5["margin_pct"].groupby(d5.index.year).mean() * 100, "peak_margin_pct": d5["margin_pct"].groupby(d5.index.year).max() * 100})
print("\nby calendar year (2021 = Sep-Dec, 2026 = Jan-Aug):"); print(yr5.round(1).to_string())
eq5 = d5["equity"]; dd5 = eq5 / eq5.cummax() - 1; tr5 = dd5.idxmin(); pk5 = eq5.loc[:tr5].idxmax(); rec5 = eq5.loc[tr5:][eq5.loc[tr5:] >= eq5.loc[pk5]].index; tot5 = m5["pnl"].sum()
print(f"worst drawdown {dd5.min()*100:.1f}% from {pk5.date()} to {tr5.date()}, recovered {rec5[0].date() if len(rec5) else 'not yet'}; best 5 months = {m5['pnl'].nlargest(5).sum()/tot5:.0%} of P&L; direction flips {int((np.sign(m5['contracts']).diff().abs() > 0).sum())}; "
      f"override months {int(((score.abs() > 0.5) & (np.sign(score) != ecb)).loc['2021-08-31':'2026-07-31'].sum())}; margin EUR mean {d5['margin'].mean():,.0f}, peak {d5['margin'].max():,.0f}; fees {d5['fees'].sum():,.0f}")
print(m5[["signal", "sigma_bp", "contracts", "equity_start", "ret"]].round(3).to_string())
roll5 = M["Frozen spec"].rolling(60).apply(sharpe_m); print(f"rolling 60-month Sharpe of the 2008-start account: latest {roll5.iloc[-1]:+.2f}, min {roll5.min():+.2f}, median {roll5.median():+.2f}, max {roll5.max():+.2f}, share of windows below the latest {(roll5.dropna() < roll5.iloc[-1]).mean():.0%} of {roll5.notna().sum()}")
keys5 = {"Frozen spec": "Frozen spec, 10% vol target", "Follow-the-ECB": "Follow-the-ECB only, 10% vol", "Long-only": "Long-only, 10% vol"}
M5 = pd.DataFrame({k: runs5[v][1]["ret"] for k, v in keys5.items()}); print(f"\nmonthly account returns: {len(M5)} months, monthly-based Sharpe:", M5.apply(sharpe_m).round(2).to_dict())
sy5 = pd.DataFrame({k: runs5[v][0]["ret"].groupby(runs5[v][0].index.year).apply(lambda x: x.mean() / x.std() * np.sqrt(252)) for k, v in keys5.items()}); sy5.loc["all 60 months"] = [S5.loc[v, "sharpe"] for v in keys5.values()]
u1 = {k: daily_pnl(p, cont, cost=COST50)[0].loc[START5:END] for k, p in [("Frozen spec, 1 contract", frozen), ("Follow-the-ECB, 1 contract", ecb)]}
for k, x in u1.items(): sy5[k] = list(x.groupby(x.index.year).apply(lambda v: v.mean() / v.std() * np.sqrt(252))) + [x.mean() / x.std() * np.sqrt(252)]
print("Sharpe by calendar year (account returns at a 10% vol target; last two columns one fixed contract):"); print(sy5.round(2).to_string()); sy5.to_csv(f"{R}/bt50k_5y_sharpe_by_year.csv")
boot5, paths5 = bootstrap(M5, rng5)
B5 = pd.DataFrame({k: dict(**summ(boot5[k]["sharpe"]), prob_gt0=(boot5[k]["sharpe"] > 0).mean()) for k in boot5}).T
B5.loc["Frozen spec", "prob_beats_longonly"] = (boot5["Frozen spec"]["sharpe"] > boot5["Long-only"]["sharpe"]).mean(); B5.loc["Frozen spec", "prob_beats_ecb"] = (boot5["Frozen spec"]["sharpe"] > boot5["Follow-the-ECB"]["sharpe"]).mean()
print(f"[1] Block bootstrap ({L}-month blocks, {NB:,} paths of {len(M5)} months) of realised Sharpe:"); print(B5.round(2).to_string())
PLT5 = pnl_summary(boot5); print("[1b] Bootstrap of the P&L path (final equity after 60 months, drawdown, 1-year P&L):"); print(PLT5.round(3).T.to_string())
nulls5 = {}; perms5 = {}
for name, key in list(keys5.items())[:2]: nulls5[name], perms5[name] = null_test(runs5[key][1], block=6, rng=rng5)
print("[2] No-skill nulls, 6-month blocks:"); print(pd.DataFrame(nulls5).T.round(3).to_string())
DS5 = {k: dict(sharpe=sharpe_m(M5[k]), skew=skew(M5[k]), kurt=kurtosis(M5[k], fisher=False), dsr_45=dsr(M5[k], len(trial))[0], dsr_70=dsr(M5[k], 70)[0]) for k in M5.columns}
print("[3] Deflated Sharpe on 60 months:"); print(pd.DataFrame(DS5).T.round(2).to_string())
d5.to_csv(f"{R}/bt50k_5y_daily.csv"); m5.to_csv(f"{R}/bt50k_5y_monthly.csv"); S5.to_csv(f"{R}/bt50k_5y_variants.csv"); yr5.to_csv(f"{R}/bt50k_5y_by_year.csv")
pd.DataFrame({k: runs5[v][0]["equity"] for k, v in keys5.items()}).to_csv(f"{R}/bt50k_5y_equity_curves.csv")
pd.DataFrame({f"{k}|{c}": boot5[k][c] for k in boot5 for c in ["sharpe", "final_equity", "maxdd_pct", "eq_1y", "eq_5y"]}).to_csv(f"{R}/bt50k_5y_bootstrap.csv", index=False)
pd.DataFrame({f"p{p:02d}": np.percentile(paths5["Frozen spec"], p, axis=0) for p in q}).to_csv(f"{R}/bt50k_5y_bootstrap_fan.csv", index=False)
pd.DataFrame({"perm_sharpe": perms5["Frozen spec"]}).to_csv(f"{R}/bt50k_5y_null_perm.csv", index=False)
json.dump(dict(bootstrap_sharpe=B5.to_dict("index"), bootstrap_pnl=PLT5.to_dict("index"), nulls=nulls5, deflated=DS5, unit_check={k: float(v) for k, v in u5.items()}, unit_check_ecb={k: float(v) for k, v in ue5.items()}, cost_bp=COST_BP), open(f"{R}/bt50k_5y_mc.json", "w"), indent=1, default=float)
