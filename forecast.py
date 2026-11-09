#!/usr/bin/env python3
"""
Forecast + backtest + scenario inputs, computed from the dbt mart (marts.mart_revenue_cube).

Candidates (monthly total net revenue, 34 months of history):
  SN   seasonal naive              : same month last year
  SND  seasonal naive with drift   : same month last year x (last 12 months / previous 12 months)
  HW   Holt-Winters                : damped additive trend, multiplicative seasonality (statsmodels)

Evaluation: rolling origin. Train on the first `o` months (o = 24..31), forecast the next 3 months,
compare with what happened. Headline metric = MAPE of the 3-months-ahead forecast (8 forecasts,
targets Mar-Oct 2026); all horizons (24 forecasts) are reported too. Nothing is tuned on the holdout
except the choice between three candidate models, and that choice is shown, not hidden.
"""
from __future__ import annotations

import json
import pathlib
import warnings

import duckdb
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

ROOT = pathlib.Path(__file__).resolve().parent
DB = ROOT / "data" / "bedbank.duckdb"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

con = duckdb.connect(str(DB), read_only=True)
m = con.execute("""
    select month_start,
           sum(net_revenue_eur) as rev, sum(net_ttv_eur) as ttv,
           sum(net_bookings) as nb, sum(gross_bookings) as gb
    from marts.mart_revenue_cube group by 1 order by 1
""").fetchdf()
m["month_start"] = pd.to_datetime(m["month_start"])
y = m["rev"].to_numpy(float)
labels = [d.strftime("%Y-%m") for d in m["month_start"]]
N = len(y)
assert N == 34

H = 3
FIRST_ORIGIN = 24
budget = con.execute("select month_start, sum(budget_revenue_eur) b from marts.mart_budget_vs_actual group by 1 order by 1").fetchdf()
budget["month_start"] = pd.to_datetime(budget["month_start"])


# ---- models ---------------------------------------------------------------------------
def f_sn(train: np.ndarray, h: int) -> np.ndarray:
    n = len(train)
    return np.array([train[n - 12 + (i % 12)] if i < 12 else train[n - 12 + (i % 12)] for i in range(h)])


def f_snd(train: np.ndarray, h: int) -> np.ndarray:
    n = len(train)
    g = train[n - 12:].sum() / train[n - 24:n - 12].sum()
    return f_sn(train, h) * g


def fit_hw(train: np.ndarray):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mod = ExponentialSmoothing(train, trend="add", damped_trend=True, seasonal="mul",
                                   seasonal_periods=12, initialization_method="heuristic")
        return mod.fit(optimized=True)


def f_hw(train: np.ndarray, h: int) -> np.ndarray:
    return np.asarray(fit_hw(train).forecast(h))


MODELS = {"SN": f_sn, "SND": f_snd, "HW": f_hw}

# ---- rolling-origin backtest ----------------------------------------------------------
rows = []
for o in range(FIRST_ORIGIN, N - H + 1):
    train = y[:o]
    for name, fn in MODELS.items():
        fc = fn(train, H)
        for h in range(1, H + 1):
            t = o + h - 1
            rows.append(dict(origin=o, h=h, target=t, model=name, actual=y[t], fc=fc[h - 1]))
bt = pd.DataFrame(rows)
bt["ape"] = (bt["fc"] - bt["actual"]).abs() / bt["actual"]
bt["err_pct"] = (bt["fc"] - bt["actual"]) / bt["actual"]

metrics = {}
for name in MODELS:
    a = bt[bt.model == name]
    a3 = a[a.h == 3]
    metrics[name] = dict(
        mape_h3=float(a3["ape"].mean()),
        mape_all=float(a["ape"].mean()),
        bias_h3=float(a3["err_pct"].mean()),
        n_h3=int(len(a3)),
        n_all=int(len(a)),
    )
# Model choice (written down, not hidden): lowest MAPE at 3 months ahead. Models within 0.25 pp of the
# best are treated as tied and the tie is broken by the smaller absolute bias (a model that is
# systematically high or low is worse for budgeting than one that is merely noisy). The seasonal naive
# baseline is only there as the benchmark to beat.
TIE_PP = 0.0025
lowest = min(metrics, key=lambda k: metrics[k]["mape_h3"])
tied = [k for k in metrics
        if k != "SN" and metrics[k]["mape_h3"] - metrics[lowest]["mape_h3"] <= TIE_PP]
best = min(tied, key=lambda k: abs(metrics[k]["bias_h3"]))
selection = dict(lowest_mape=lowest, tied=tied, chosen=best, tie_pp=TIE_PP * 100,
                 rule="lowest 3-month-ahead MAPE; models within 0.25 pp are tied and the smaller absolute bias wins")

print("Backtest (rolling origin, 3 months ahead):")
for k, v in metrics.items():
    print(f"  {k:4s} MAPE h=3 {v['mape_h3']*100:5.2f}%   all horizons {v['mape_all']*100:5.2f}%   bias h=3 {v['bias_h3']*100:+5.2f}%  (n={v['n_h3']}/{v['n_all']})")
print("  lowest MAPE:", lowest, "| tied within 0.25pp:", tied, "| chosen:", best)

h3 = bt[bt.h == 3].pivot(index="target", columns="model", values="fc")
h3["actual"] = [y[t] for t in h3.index]
backtest_chart = dict(
    months=[labels[t] for t in h3.index],
    actual=[round(float(v)) for v in h3["actual"]],
    **{k.lower(): [round(float(v)) for v in h3[k]] for k in MODELS},
)

# ---- final forecast: 6 months ahead, 80% interval -----------------------------------
HF = 6
fut_months = pd.period_range("2026-11", periods=HF, freq="M")
fut_labels = [str(p) for p in fut_months]

# Interval method: simulate the fitted Holt-Winters model (multiplicative errors) 4,000 times.
hw_res = fit_hw(y)
sims = hw_res.simulate(nsimulations=HF, repetitions=4000, error="mul", rng=np.random.default_rng(20261106))
sims = np.asarray(sims)  # (HF, reps)
hw_point = np.asarray(hw_res.forecast(HF))
hw_lo = np.quantile(sims, 0.10, axis=1)
hw_hi = np.quantile(sims, 0.90, axis=1)

# Backtest calibration of the 80% interval: simulate at each origin, count coverage of the actual.
cov_hits, cov_n = 0, 0
for o in range(FIRST_ORIGIN, N - H + 1):
    r = fit_hw(y[:o])
    s = np.asarray(r.simulate(nsimulations=H, repetitions=2000, error="mul", rng=np.random.default_rng(o)))
    lo, hi = np.quantile(s, 0.10, axis=1), np.quantile(s, 0.90, axis=1)
    for h in range(H):
        t = o + h
        cov_n += 1
        cov_hits += int(lo[h] <= y[t] <= hi[h])
print(f"80% interval coverage in backtest: {cov_hits}/{cov_n}")

snd_point = f_snd(y, HF)
sn_point = f_sn(y, HF)
print("HW forecast :", [round(v / 1e3) for v in hw_point])
print("SND forecast:", [round(v / 1e3) for v in snd_point])
print("SN  forecast:", [round(v / 1e3) for v in sn_point])

point = {"HW": hw_point, "SND": snd_point, "SN": sn_point}[best]

# if the best model has no native simulation, centre the HW interval's relative width on it
rel_lo = hw_lo / hw_point
rel_hi = hw_hi / hw_point
lo80 = point * rel_lo
hi80 = point * rel_hi

# ---- FY2026 landing vs budget ----------------------------------------------------------
ytd = float(y[24:].sum())                                    # Jan-Oct 2026
fy_budget = float(budget["b"].sum())
bud_ytd = float(budget[budget["month_start"] <= "2026-10-01"]["b"].sum())
bud_rest = fy_budget - bud_ytd
nd_point = float(point[:2].sum())
if best == "HW":
    nd_sims = sims[:2].sum(axis=0)
    nd_lo, nd_hi = float(np.quantile(nd_sims, 0.10)), float(np.quantile(nd_sims, 0.90))
else:
    nd_lo, nd_hi = float(lo80[:2].sum()), float(hi80[:2].sum())
landing = ytd + nd_point
landing_lo, landing_hi = ytd + nd_lo, ytd + nd_hi
uplift_needed = (fy_budget - ytd) / nd_point - 1  # on Nov-Dec baseline, to land exactly on budget

# ---- scenario baseline (LTM drivers) ----------------------------------------------------
ltm = m.iloc[-12:]
ltm_gb, ltm_nb = float(ltm["gb"].sum()), float(ltm["nb"].sum())
ltm_ttv, ltm_rev = float(ltm["ttv"].sum()), float(ltm["rev"].sum())
drivers = dict(
    abv=ltm_ttv / ltm_nb,
    take_rate=ltm_rev / ltm_ttv,
    cancellation_rate=1 - ltm_nb / ltm_gb,
)
ly_same = y[22:28]  # Nov-2025 .. Apr-2026 (indices 22..27)
print("LTM drivers:", {k: round(v, 4) for k, v in drivers.items()})

out = dict(
    history=dict(months=labels, revenue=[round(float(v)) for v in y]),
    backtest=dict(chart=backtest_chart, metrics=metrics, best=best, selection=selection,
                  coverage=dict(hits=cov_hits, n=cov_n),
                  first_origin=labels[FIRST_ORIGIN], horizon=H),
    forecast=dict(months=fut_labels, point=[round(float(v)) for v in point],
                  lo80=[round(float(v)) for v in lo80], hi80=[round(float(v)) for v in hi80],
                  model=best, hw=[round(float(v)) for v in hw_point],
                  snd=[round(float(v)) for v in snd_point], sn=[round(float(v)) for v in sn_point]),
    landing=dict(ytd=round(ytd), nov_dec=round(nd_point), nov_dec_lo=round(nd_lo), nov_dec_hi=round(nd_hi),
                 landing=round(landing), landing_lo=round(landing_lo), landing_hi=round(landing_hi),
                 budget_fy=round(fy_budget), budget_ytd=round(bud_ytd), budget_rest=round(bud_rest),
                 gap=round(landing - fy_budget), gap_pct=float(landing / fy_budget - 1),
                 ytd_gap=round(ytd - bud_ytd), ytd_gap_pct=float(ytd / bud_ytd - 1),
                 uplift_needed=float(uplift_needed)),
    scenario=dict(months=fut_labels, baseline=[round(float(v)) for v in point],
                  ly=[round(float(v)) for v in ly_same], drivers=drivers),
)
(OUT / "forecast.json").write_text(json.dumps(out, indent=1))
print("\nFY26: YTD", round(ytd / 1e6, 3), "M | Nov-Dec fc", round(nd_point / 1e6, 3), "M | landing", round(landing / 1e6, 3),
      "M [", round(landing_lo / 1e6, 3), "-", round(landing_hi / 1e6, 3), "] | budget", round(fy_budget / 1e6, 3),
      "M | gap", f"{(landing / fy_budget - 1) * 100:+.1f}%", "| uplift needed on Nov-Dec:", f"{uplift_needed * 100:+.0f}%")
