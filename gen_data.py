#!/usr/bin/env python3
"""
Synthetic dataset for a FICTIONAL B2B bedbank (accommodation wholesaler).

Nothing here comes from any employer or real company. Everything is drawn from a
seeded random generator, so the output is deterministic and reproducible.

Grain written to data/raw/bookings.csv : one row per booking record as a booking
feed would deliver it - including the defects a real feed has (duplicates from a
replayed batch, inconsistent market codes, zero-value test bookings). The dbt
project is what cleans, tests and models it.

Planted stories (so the analysis has something to find; all are parameters below):
  1. Take-rate compression in the OTA segment (Mar-2025; extra in UK & DE from Jan-2026)
  2. Supplier-mix drift from Direct contracts towards Connected (XML) suppliers
  3. UK demand slowdown from Apr-2026
  4. OTA cancellations creeping up from Feb-2026
  5. Fast-growing Nordics and US markets
"""
from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

SEED = 20261106
rng = np.random.default_rng(SEED)

MONTHS = pd.period_range("2024-01", "2026-10", freq="M")  # 34 months
NM = len(MONTHS)

# ---- dimensions -------------------------------------------------------------------
# code, name, region, booking weight, ABV multiplier, annual growth, take-rate adj
MK = [
    ("UK", "United Kingdom", "Europe", 0.24, 1.10, 0.02, 1.02),
    ("DE", "Germany", "Europe", 0.16, 1.00, 0.04, 1.00),
    ("ES", "Spain", "Europe", 0.14, 0.80, 0.07, 0.98),
    ("FR", "France", "Europe", 0.12, 0.95, 0.05, 1.01),
    ("IT", "Italy", "Europe", 0.10, 0.90, 0.06, 0.99),
    ("NL", "Netherlands", "Europe", 0.09, 1.02, 0.06, 1.00),
    ("NORD", "Nordics", "Europe", 0.08, 1.20, 0.14, 1.03),
    ("US", "United States", "Americas", 0.07, 1.25, 0.12, 0.94),
]
# code, name, weight, ABV mult, base take rate, annual growth, cancel rate, lead-time median (days), nights lambda
SG = [
    ("TO", "Tour operators", 0.30, 1.35, 0.105, 0.02, 0.07, 90, 4.5),
    ("OTA", "Online travel agencies", 0.38, 0.95, 0.125, 0.09, 0.14, 35, 2.2),
    ("RET", "Retail agencies", 0.22, 1.05, 0.140, -0.04, 0.10, 60, 3.2),
    ("CORP", "Corporate & MICE", 0.10, 1.10, 0.150, 0.06, 0.06, 20, 1.0),
]
# code, name, take-rate multiplier, share at start, share at end, ABV mult
TI = [
    ("DIR", "Direct contracts", 1.20, 0.40, 0.34, 1.03),
    ("CHN", "Chains & aggregators", 1.00, 0.30, 0.30, 1.05),
    ("XML", "Connected (XML) suppliers", 0.78, 0.30, 0.36, 0.94),
]
K, S, T = len(MK), len(SG), len(TI)

SEAS = np.array([1.20, 1.15, 1.12, 0.95, 0.95, 1.02, 1.00, 0.90, 0.92, 0.95, 0.88, 0.82])
ABV_SEAS = np.array([1.04, 1.03, 1.02, 1.00, 1.00, 1.00, 0.99, 0.98, 0.99, 1.00, 0.97, 0.96])
B0 = 11_600        # bookings per month at index 1.0
ABV0 = 540.0       # EUR, base average booking value
INFL = 0.035       # annual ABV inflation

# FY2026 budget: FY2025 actual net revenue x (1 + plan growth). Plan assumed a stable take rate.
PLAN_GROWTH = {"UK": 0.06, "DE": 0.06, "ES": 0.08, "FR": 0.06, "IT": 0.07, "NL": 0.07, "NORD": 0.14, "US": 0.15}


def ramp(t: int, start: int, n: int) -> float:
    """0 before `start`, linear to 1 over n months."""
    return float(np.clip((t - start + 1) / n, 0.0, 1.0))


def midx(ym: str) -> int:
    return int(MONTHS.get_loc(pd.Period(ym, "M")))


# ---- expected values per month x market x segment x tier ----------------------------
lam = np.zeros((NM, K, S, T))
abv = np.zeros((NM, K, S, T))
tr = np.zeros((NM, K, S, T))
canc = np.zeros((NM, K, S, T))

w_k = np.array([m[3] for m in MK]); abv_k = np.array([m[4] for m in MK])
g_k = np.array([m[5] for m in MK]); tradj_k = np.array([m[6] for m in MK])
w_s = np.array([s[2] for s in SG]); abv_s = np.array([s[3] for s in SG])
tr_s = np.array([s[4] for s in SG]); g_s = np.array([s[5] for s in SG])
canc_s = np.array([s[6] for s in SG])
trm_t = np.array([t[2] for t in TI]); w0_t = np.array([t[3] for t in TI])
w1_t = np.array([t[4] for t in TI]); abv_t = np.array([t[5] for t in TI])

i_2025_03, i_2026_01, i_2026_02, i_2026_04, i_2025_01 = (
    midx("2025-03"), midx("2026-01"), midx("2026-02"), midx("2026-04"), midx("2025-01"))

for t in range(NM):
    cal = MONTHS[t].month - 1
    y = t / 12.0
    mk = w_k * (1 + g_k) ** y
    mk = mk.copy()
    mk[0] *= 1 - 0.06 * ramp(t, i_2026_04, 2)                      # story 3: UK slowdown
    sg = w_s * (1 + g_s) ** y
    sg = sg / sg.sum()
    tw = w0_t + (w1_t - w0_t) * t / (NM - 1)                       # story 2: supplier-mix drift
    noise = rng.lognormal(0.0, 0.04, size=(K, S, T))
    lam[t] = B0 * SEAS[cal] * mk[:, None, None] * sg[None, :, None] * tw[None, None, :] * noise

    abv[t] = (ABV0 * abv_k[:, None, None] * abv_s[None, :, None] * abv_t[None, None, :]
              * (1 + INFL) ** y * ABV_SEAS[cal])

    base_tr = tr_s[None, :, None] * trm_t[None, None, :] * tradj_k[:, None, None]
    base_tr = base_tr * np.ones((K, S, T))
    base_tr[:, 1, :] -= 0.008 * ramp(t, i_2025_03, 2)              # story 1: OTA compression
    base_tr[[0, 1], 1, :] -= 0.009 * ramp(t, i_2026_01, 3)         #          extra in UK & DE
    base_tr[:, 0, :] += 0.002 * ramp(t, i_2025_01, 12)             # small TO renegotiation gain
    tr[t] = base_tr

    c = canc_s[None, :, None] * np.ones((K, S, T))
    c[:, 1, :] += 0.025 * ramp(t, i_2026_02, 3)                    # story 4: OTA cancellations
    canc[t] = c

N = rng.poisson(lam)
assert N.min() >= 3, f"a cell-month is too thin: {N.min()}"

# ---- expand to booking rows ---------------------------------------------------------
flat_N = N.reshape(-1)
cell = np.repeat(np.arange(flat_N.size), flat_N)
t_i, k_i, s_i, ti_i = np.unravel_index(cell, (NM, K, S, T))
n = cell.size

abv_row = abv[t_i, k_i, s_i, ti_i]
tr_row = tr[t_i, k_i, s_i, ti_i]
canc_row = canc[t_i, k_i, s_i, ti_i]

# booking date inside the month (mild weekday pattern)
WD = np.array([1.15, 1.15, 1.10, 1.05, 0.95, 0.80, 0.80])  # Mon..Sun
dates = np.empty(n, dtype="datetime64[D]")
for t in range(NM):
    rows = np.where(t_i == t)[0]
    p0 = MONTHS[t].to_timestamp()
    ndays = MONTHS[t].days_in_month
    days = pd.date_range(p0, periods=ndays)
    p = WD[days.day_of_week.values]
    p = p / p.sum()
    pick = rng.choice(ndays, size=rows.size, p=p)
    dates[rows] = np.datetime64(p0.date(), "D") + pick.astype("timedelta64[D]")

secs = rng.integers(0, 86_400, n)
booking_ts = dates.astype("datetime64[s]") + secs.astype("timedelta64[s]")

lead_med = np.array([s[7] for s in SG], dtype=float)
lead = np.clip(np.round(lead_med[s_i] * np.exp(0.7 * rng.standard_normal(n))), 1, 400).astype(int)
checkin = dates + lead.astype("timedelta64[D]")
nl = np.array([s[8] for s in SG])
nights = np.clip(1 + rng.poisson(nl[s_i]), 1, 21)

z = rng.standard_normal(n)
ttv = np.round(abv_row * np.exp(0.40 * z - 0.08), 2)
rev = np.round(ttv * tr_row * np.clip(rng.normal(1.0, 0.10, n), 0.7, 1.3), 2)

is_canc = rng.random(n) < canc_row
canc_secs = (np.minimum(lead, 30) * 86_400 * rng.random(n)).astype(int) + 60
cancelled_at = np.where(is_canc, booking_ts + canc_secs.astype("timedelta64[s]"), np.datetime64("NaT", "s"))
loaded_at = booking_ts + rng.integers(300, 6 * 3600, n).astype("timedelta64[s]")

# ---- customers ----------------------------------------------------------------------
cust_rows = []
cust_pool: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {}
cid = 0
for k in range(K):
    for s in range(S):
        n_c = max(4, int(round(480 * w_k[k] * w_s[s])))
        ids = []
        for _ in range(n_c):
            cid += 1
            ids.append(f"C{cid:04d}")
            onboard = pd.Timestamp("2019-01-01") + pd.Timedelta(days=int(rng.integers(0, 365 * 5)))
            cust_rows.append((f"C{cid:04d}", f"Customer {cid:04d}", MK[k][0], SG[s][0], onboard.date().isoformat()))
        wts = rng.lognormal(0.0, 1.1, n_c)
        cust_pool[(k, s)] = (np.array(ids), wts / wts.sum())
customers = pd.DataFrame(cust_rows, columns=["customer_id", "customer_name", "market_code", "segment_code", "onboarded_date"])

cust_id = np.empty(n, dtype=object)
for (k, s), (ids, p) in cust_pool.items():
    rows = np.where((k_i == k) & (s_i == s))[0]
    cust_id[rows] = rng.choice(ids, size=rows.size, p=p)

mk_code = np.array([m[0] for m in MK], dtype=object)[k_i]
sg_code = np.array([s[0] for s in SG], dtype=object)[s_i]
ti_code = np.array([t[0] for t in TI], dtype=object)[ti_i]

df = pd.DataFrame({
    "booking_ts": booking_ts,
    "checkin_date": checkin,
    "nights": nights,
    "market_code": mk_code,
    "segment_code": sg_code,
    "supplier_tier_code": ti_code,
    "customer_id": cust_id,
    "ttv_eur": ttv,
    "revenue_eur": rev,
    "status": np.where(is_canc, "cancelled", "confirmed"),
    "cancelled_at": cancelled_at,
    "loaded_at": loaded_at,
    "feed_batch": "daily",
})
df = df.sort_values("booking_ts", kind="stable").reset_index(drop=True)
df.insert(0, "booking_id", [f"BK{i:08d}" for i in range(1, len(df) + 1)])

# the clean copy (before defects) is used for the budget
clean = df.copy()

# ---- planted data defects (what a real feed looks like) -----------------------------
# (a) zero-value test bookings
zero_idx = rng.choice(len(df), size=int(0.0025 * len(df)), replace=False)
df.loc[zero_idx, ["ttv_eur", "revenue_eur"]] = 0.0
df.loc[zero_idx, ["status", "cancelled_at"]] = ["confirmed", pd.NaT]

# (b) inconsistent market codes
uk = np.where(df["market_code"] == "UK")[0]
df.loc[rng.choice(uk, size=int(0.07 * uk.size), replace=False), "market_code"] = "GB"
low = rng.choice(len(df), size=int(0.008 * len(df)), replace=False)
df.loc[low, "market_code"] = df.loc[low, "market_code"].str.lower()
pad = rng.choice(len(df), size=int(0.005 * len(df)), replace=False)
df.loc[pad, "market_code"] = df.loc[pad, "market_code"] + " "

# (c) a replayed feed batch: duplicates of one week of bookings, loaded again
wk = df[(df["booking_ts"] >= "2025-06-17") & (df["booking_ts"] < "2025-06-24")]
dup = wk.loc[rng.choice(wk.index.values, size=1_900, replace=False)].copy()
dup["loaded_at"] = pd.Timestamp("2025-06-24 03:05:00") + pd.to_timedelta(np.arange(len(dup)), unit="s")
dup["feed_batch"] = "replay_2025-06-24"
df = pd.concat([df, dup], ignore_index=True)

# ---- budget FY2026 --------------------------------------------------------------------
c = clean.copy()
c["m"] = c["booking_ts"].dt.to_period("M")
c = c[(c["status"] == "confirmed")]
act25 = c[c["m"].dt.year == 2025].groupby([c["m"].dt.month, "market_code"])["revenue_eur"].sum()
bud = []
for (mm, code), v in act25.items():
    b = round(v * (1 + PLAN_GROWTH[code]) / 100.0) * 100
    bud.append((2026, f"2026-{mm:02d}-01", code, int(b)))
budget = pd.DataFrame(bud, columns=["fiscal_year", "month_start", "market_code", "budget_revenue_eur"])

# ---- write ------------------------------------------------------------------------------
fmt = "%Y-%m-%d %H:%M:%S"
out = df.copy()
for col in ("booking_ts", "cancelled_at", "loaded_at"):
    out[col] = out[col].dt.strftime(fmt)
out["checkin_date"] = pd.to_datetime(out["checkin_date"]).dt.strftime("%Y-%m-%d")
out.to_csv(RAW / "bookings.csv", index=False)
customers.to_csv(RAW / "customers.csv", index=False)
pd.DataFrame([(m[0], m[1], m[2]) for m in MK], columns=["market_code", "market_name", "region"]).to_csv(RAW / "markets.csv", index=False)
pd.DataFrame([(s[0], s[1]) for s in SG], columns=["segment_code", "segment_name"]).to_csv(RAW / "segments.csv", index=False)
pd.DataFrame([(t[0], t[1]) for t in TI], columns=["supplier_tier_code", "supplier_tier_name"]).to_csv(RAW / "supplier_tiers.csv", index=False)
budget.to_csv(RAW / "budget.csv", index=False)

# ---- quick report ----------------------------------------------------------------------
print(f"raw rows written: {len(out):,}  (clean bookings {len(clean):,}; duplicates {len(dup):,}; zero-value {len(zero_idx):,})")
print(f"customers: {len(customers)}, budget rows: {len(budget)}")
cc = clean[clean["status"] == "confirmed"].copy()
cc["y"] = cc["booking_ts"].dt.year
g = cc.groupby("y").agg(net_bookings=("booking_id", "count"), ttv=("ttv_eur", "sum"), rev=("revenue_eur", "sum"))
g["take_rate"] = g["rev"] / g["ttv"]
g["abv"] = g["ttv"] / g["net_bookings"]
print(g.round(4).to_string())
