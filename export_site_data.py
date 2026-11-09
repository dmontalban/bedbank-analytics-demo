#!/usr/bin/env python3
"""
Exports everything the portfolio website needs, straight from the dbt marts and the dbt artifacts:

  out/cube.json             the analytical cube (month x market x segment x tier), columnar, cents precision
  out/dbt_summary.json      models, sources, lineage edges, row counts, test results, data-quality log
  out/facts.json            headline numbers for the narrative text (so no number on the site is typed by hand)
  out/reference_cases.json  "golden" cases: expected KPI + bridge values for period x filter combinations,
                            computed here in Python from the SAME cube. The JavaScript cockpit must match them.

Also asserts the price-volume-mix-rate identity on every case and cross-checks the Python bridge
against the SQL bridge (marts.mart_revenue_bridge).
"""
from __future__ import annotations

import json
import pathlib

import duckdb
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)
DBT = ROOT / "dbt_project"

con = duckdb.connect(str(ROOT / "data" / "bedbank.duckdb"), read_only=True)

# ------------------------------------------------------------------------------------------------
# 1. cube.json
# ------------------------------------------------------------------------------------------------
MARKETS = ["UK", "DE", "ES", "FR", "IT", "NL", "NORD", "US"]
SEGMENTS = ["OTA", "TO", "RET", "CORP"]          # fixed order = categorical colour slots 1..4
TIERS = ["DIR", "CHN", "XML"]

cube = con.execute("""
    select strftime(month_start, '%Y-%m') as ym, market_code, segment_code, supplier_tier_code,
           gross_bookings, net_bookings, gross_ttv_eur, net_ttv_eur, gross_revenue_eur, net_revenue_eur
    from marts.mart_revenue_cube
""").fetchdf()
months = sorted(cube["ym"].unique())
MI = {m: i for i, m in enumerate(months)}
KI = {c: i for i, c in enumerate(MARKETS)}
SI = {c: i for i, c in enumerate(SEGMENTS)}
TI = {c: i for i, c in enumerate(TIERS)}
assert len(months) == 34 and len(cube) == 34 * 8 * 4 * 3

df = pd.DataFrame({
    "m": cube["ym"].map(MI), "k": cube["market_code"].map(KI), "s": cube["segment_code"].map(SI),
    "t": cube["supplier_tier_code"].map(TI),
    "gb": cube["gross_bookings"].astype(int), "nb": cube["net_bookings"].astype(int),
    "gttv": cube["gross_ttv_eur"].round(2), "nttv": cube["net_ttv_eur"].round(2),
    "grev": cube["gross_revenue_eur"].round(2), "nrev": cube["net_revenue_eur"].round(2),
}).sort_values(["m", "k", "s", "t"]).reset_index(drop=True)

dims = {
    "markets": con.execute("select market_code c, market_name n, region r from marts.dim_market").fetchdf().set_index("c").loc[MARKETS].reset_index().to_dict("records"),
    "segments": con.execute("select segment_code c, segment_name n from marts.dim_segment").fetchdf().set_index("c").loc[SEGMENTS].reset_index().to_dict("records"),
    "tiers": con.execute("select supplier_tier_code c, supplier_tier_name n from marts.dim_supplier_tier").fetchdf().set_index("c").loc[TIERS].reset_index().to_dict("records"),
}
cube_json = {
    "meta": {
        "synthetic": True,
        "source": "marts.mart_revenue_cube (dbt, DuckDB)",
        "currency": "EUR",
        "time_axis": "booking month",
        "data_through": months[-1],
        "cells_per_month": 96,
        "note": "Fictional B2B bedbank. All values are synthetic.",
    },
    "months": months,
    "markets": dims["markets"],
    "segments": dims["segments"],
    "tiers": dims["tiers"],
    "cols": ["m", "k", "s", "t", "gb", "nb", "gttv", "nttv", "grev", "nrev"],
    "rows": [[int(r.m), int(r.k), int(r.s), int(r.t), int(r.gb), int(r.nb), float(r.gttv), float(r.nttv), float(r.grev), float(r.nrev)]
             for r in df.itertuples(index=False)],
}
(OUT / "cube.json").write_text(json.dumps(cube_json, separators=(",", ":")))


# ------------------------------------------------------------------------------------------------
# 2. KPI + bridge implementation (reference for the JavaScript)
# ------------------------------------------------------------------------------------------------
PERIODS = {
    "ltm": dict(label="Last 12 months", cur=("2025-11", "2026-10"), base=("2024-11", "2025-10")),
    "ytd": dict(label="YTD 2026", cur=("2026-01", "2026-10"), base=("2025-01", "2025-10")),
    "q":   dict(label="Last quarter", cur=("2026-08", "2026-10"), base=("2025-08", "2025-10")),
    "m":   dict(label="Last month", cur=("2026-10", "2026-10"), base=("2025-10", "2025-10")),
    "fy25": dict(label="FY2025", cur=("2025-01", "2025-12"), base=("2024-01", "2024-12")),
}


def pick(frame: pd.DataFrame, a: str, b: str, mk: str | None = None, sg: str | None = None) -> pd.DataFrame:
    mask = (frame.m >= MI[a]) & (frame.m <= MI[b])
    if mk:
        mask &= frame.k == KI[mk]
    if sg:
        mask &= frame.s == SI[sg]
    return frame[mask]


def totals(d: pd.DataFrame) -> dict:
    gb, nb = float(d.gb.sum()), float(d.nb.sum())
    nttv, nrev, grev = float(d.nttv.sum()), float(d.nrev.sum()), float(d.grev.sum())
    return dict(gross_bookings=int(gb), net_bookings=int(nb), net_ttv=nttv, net_revenue=nrev, gross_revenue=grev,
                abv=nttv / nb, take_rate=nrev / nttv, cancellation_rate=1 - nb / gb, leakage=grev - nrev)


def bridge(cur: pd.DataFrame, base: pd.DataFrame) -> dict:
    key = ["k", "s", "t"]
    A = cur.groupby(key)[["nb", "nttv", "nrev"]].sum().add_suffix("_a")
    B = base.groupby(key)[["nb", "nttv", "nrev"]].sum().add_suffix("_b")
    J = A.join(B, how="outer")
    assert not J.isna().any().any(), "an item is missing in one of the periods"
    Ba, Bb, Ra, Rb = J.nb_a.sum(), J.nb_b.sum(), J.nrev_a.sum(), J.nrev_b.sum()
    rbar = Rb / Bb
    rb = J.nrev_b / J.nb_b
    abv_a, abv_b = J.nttv_a / J.nb_a, J.nttv_b / J.nb_b
    tr_a, tr_b = J.nrev_a / J.nttv_a, J.nrev_b / J.nttv_b
    vol = (Ba - Bb) * rbar
    mix = (J.nb_a * rb).sum() - Ba * rbar
    price = (J.nb_a * (abv_a - abv_b) * tr_b).sum()
    rate = (J.nttv_a * (tr_a - tr_b)).sum()
    resid = (Ra - Rb) - (vol + mix + price + rate)
    assert abs(resid) < 1e-6 * max(1.0, abs(Ra)), f"bridge identity broken: {resid}"
    return dict(base=float(Rb), volume=float(vol), mix=float(mix), price=float(price), rate=float(rate),
                current=float(Ra), residual=float(resid))


def view(period: str, mk: str | None = None, sg: str | None = None) -> dict:
    p = PERIODS[period]
    cur = pick(df, *p["cur"], mk, sg)
    base = pick(df, *p["base"], mk, sg)
    c, b = totals(cur), totals(base)
    return dict(
        period=period, market=mk, segment=sg, cur=c, base=b,
        yoy=dict(
            net_revenue_pct=c["net_revenue"] / b["net_revenue"] - 1,
            net_bookings_pct=c["net_bookings"] / b["net_bookings"] - 1,
            abv_pct=c["abv"] / b["abv"] - 1,
            take_rate_pp=(c["take_rate"] - b["take_rate"]) * 100,
            cancellation_rate_pp=(c["cancellation_rate"] - b["cancellation_rate"]) * 100,
        ),
        bridge=bridge(cur, base),
    )


# golden cases ------------------------------------------------------------------------------------
FILTERS = [(None, None), ("UK", None), (None, "OTA"), ("NORD", "RET"), ("US", "CORP")]
cases = [view(p, mk, sg) for p in PERIODS for (mk, sg) in FILTERS]
(OUT / "reference_cases.json").write_text(json.dumps(
    {"note": "Expected values for the cockpit. periods: see PERIODS in export_site_data.py. "
             "Tolerance for a JavaScript implementation: 1e-6 relative.",
     "periods": {k: {"label": v["label"], "cur": v["cur"], "base": v["base"]} for k, v in PERIODS.items()},
     "cases": cases}, indent=1))

# cross-check Python bridge vs the SQL bridge in dbt (marts.mart_revenue_bridge) ----------------------
sql_b = con.execute("select * from marts.mart_revenue_bridge").fetchdf().set_index("period")
for sql_name, key in (("LTM", "ltm"), ("YTD26", "ytd"), ("FY25", "fy25")):
    py = view(key)["bridge"]
    row = sql_b.loc[sql_name]
    for a, b in ((py["volume"], row.volume_effect), (py["mix"], row.mix_effect), (py["price"], row.price_effect),
                 (py["rate"], row.rate_effect), (py["current"], row.revenue_current), (py["base"], row.revenue_base)):
        # the cube.json is rounded to cents, the SQL is exact: allow a tiny relative gap
        assert abs(a - b) <= max(5.0, 1e-5 * abs(b)), (sql_name, a, b)
print("Python bridge == SQL bridge (LTM, YTD26, FY25)  OK")

# ------------------------------------------------------------------------------------------------
# 3. facts.json - numbers for the narrative
# ------------------------------------------------------------------------------------------------
fc = json.loads((OUT / "forecast.json").read_text())
ltm = view("ltm")
ytd = view("ytd")

by_market = []
for mk in MARKETS:
    v = view("ltm", mk)
    by_market.append(dict(code=mk, revenue=v["cur"]["net_revenue"], yoy=v["yoy"]["net_revenue_pct"],
                          take_rate_pp=v["yoy"]["take_rate_pp"]))
by_segment = []
for sg in SEGMENTS:
    v = view("ltm", None, sg)
    by_segment.append(dict(code=sg, revenue=v["cur"]["net_revenue"], yoy=v["yoy"]["net_revenue_pct"],
                           take_rate=v["cur"]["take_rate"], take_rate_pp=v["yoy"]["take_rate_pp"],
                           cancellation_rate=v["cur"]["cancellation_rate"],
                           cancellation_pp=v["yoy"]["cancellation_rate_pp"]))

# quarterly take rate and cancellation by segment (calendar quarters)
qlab = [f"{m[:4]}Q{(int(m[5:7]) - 1) // 3 + 1}" for m in months]
df["q"] = df.m.map(lambda i: qlab[i])
quarters = sorted(set(qlab))
tr_q, canc_q = {}, {}
for sg in SEGMENTS:
    d = df[df.s == SI[sg]].groupby("q").agg(nrev=("nrev", "sum"), nttv=("nttv", "sum"), nb=("nb", "sum"), gb=("gb", "sum"))
    tr_q[sg] = [float(d.loc[q, "nrev"] / d.loc[q, "nttv"]) for q in quarters]
    canc_q[sg] = [float(1 - d.loc[q, "nb"] / d.loc[q, "gb"]) for q in quarters]
last_full_q = "2026Q3"
qi_last = quarters.index(last_full_q)

# supplier-tier mix (share of net bookings): 2024 vs last 12 months
def tier_share(a: str, b: str) -> dict:
    d = pick(df, a, b)
    s = d.groupby("t").nb.sum()
    return {TIERS[i]: float(s.loc[i] / s.sum()) for i in range(3)}
tier_first = tier_share("2024-01", "2024-12")
tier_last = tier_share("2025-11", "2026-10")

# customer concentration (LTM, net revenue)
conc = con.execute("""
    with ltm as (
        select customer_id, sum(net_revenue_eur) as rev
        from marts.fct_bookings
        where booking_month between date '2025-11-01' and date '2026-10-01'
        group by 1
    )
    select count(*) as n_customers,
           sum(rev) filter (where rn <= 10) / sum(rev) as top10_share
    from (select *, row_number() over (order by rev desc) as rn from ltm)
""").fetchone()

bva = con.execute("""
    select strftime(month_start, '%Y-%m') as month, sum(budget_revenue_eur) as budget, sum(actual_revenue_eur) as actual
    from marts.mart_budget_vs_actual group by 1 order by 1
""").fetchdf()
budget_monthly = [dict(month=r.month, budget=float(r.budget), actual=(None if pd.isna(r.actual) else float(r.actual)))
                  for r in bva.itertuples(index=False)]

facts = dict(
    budget_monthly=budget_monthly,
    default_view=dict(period="ltm", market=None, segment=None, **{k: v for k, v in ltm.items() if k not in ("period", "market", "segment")}),
    ytd=dict(cur=ytd["cur"], base=ytd["base"], yoy=ytd["yoy"], bridge=ytd["bridge"]),
    by_market_ltm=sorted(by_market, key=lambda r: -r["yoy"]),
    by_segment_ltm=by_segment,
    quarters=quarters,
    take_rate_by_quarter=tr_q,
    cancellation_by_quarter=canc_q,
    ota_take_rate=dict(first_q=quarters[0], first=tr_q["OTA"][0], last_q=last_full_q, last=tr_q["OTA"][qi_last]),
    ota_cancellation=dict(first=canc_q["OTA"][0], last_q=last_full_q, last=canc_q["OTA"][qi_last]),
    tier_mix=dict(y2024=tier_first, ltm=tier_last),
    concentration=dict(customers_ltm=int(conc[0]), top10_share=float(conc[1])),
    budget=fc["landing"],
    backtest=dict(metrics=fc["backtest"]["metrics"], chosen=fc["backtest"]["best"],
                  selection=fc["backtest"]["selection"], coverage=fc["backtest"]["coverage"]),
    scenario_drivers=fc["scenario"]["drivers"],
    counts=dict(
        raw_rows=int(con.execute("select count(*) from raw.bookings").fetchone()[0]),
        fct_rows=int(con.execute("select count(*) from marts.fct_bookings").fetchone()[0]),
        customers=int(con.execute("select count(*) from marts.dim_customer").fetchone()[0]),
        cube_cells=len(df), months=len(months),
        net_bookings_total=int(df.nb.sum()), net_revenue_total=float(df.nrev.sum()),
    ),
)
(OUT / "facts.json").write_text(json.dumps(facts, indent=1))

# ------------------------------------------------------------------------------------------------
# 4. dbt_summary.json (from the artifacts of the real `dbt build`)
# ------------------------------------------------------------------------------------------------
manifest = json.loads((DBT / "target" / "manifest.json").read_text())
run = json.loads((DBT / "target" / "run_results.json").read_text())
status = {r["unique_id"]: r for r in run["results"]}

def short_source(uid: str) -> str:
    return "raw." + uid.split(".")[-1]

models = {uid: n for uid, n in manifest["nodes"].items() if n["resource_type"] == "model"}
sources = manifest["sources"]
tests = {uid: n for uid, n in manifest["nodes"].items() if n["resource_type"] == "test"}

nodes, edges = [], []
for uid, n in models.items():
    schema, name = n["schema"], n.get("alias") or n["name"]
    rows = int(con.execute(f'select count(*) from "{schema}"."{name}"').fetchone()[0])
    parents = [p for p in n["depends_on"]["nodes"] if p in models or p in sources]
    nodes.append(dict(id=n["name"], layer=n["fqn"][1], materialized=n["config"]["materialized"], rows=rows,
                      description=(n.get("description") or "").strip(),
                      status=status[uid]["status"] if uid in status else None))
    for p in parents:
        edges.append([models[p]["name"] if p in models else short_source(p), n["name"]])
src_nodes = []
for uid, s in sources.items():
    rows = int(con.execute(f'select count(*) from raw."{s["name"]}"').fetchone()[0])
    src_nodes.append(dict(id=short_source(uid), layer="source", rows=rows))

by_type: dict[str, dict[str, int]] = {}
test_rows: list[dict] = []
per_node: dict[str, dict[str, int]] = {}
for uid, t in tests.items():
    meta = t.get("test_metadata")
    ttype = meta["name"] if meta else "singular"
    st = status[uid]["status"]
    by_type.setdefault(ttype, {}).setdefault(st, 0)
    by_type[ttype][st] += 1
    attached = t.get("attached_node")
    if attached and attached in models:
        owner = models[attached]["name"]
    elif attached and attached in sources:
        owner = short_source(attached)
    else:
        owner = "cross-model"
    per_node.setdefault(owner, {}).setdefault(st, 0)
    per_node[owner][st] += 1
    test_rows.append(dict(name=t["name"], type=ttype, owner=owner, status=st,
                          failures=status[uid].get("failures"), message=status[uid].get("message")))

counts = {}
for r in run["results"]:
    counts[r["status"]] = counts.get(r["status"], 0) + 1
n_models, n_tests = len(models), len(tests)
dq = con.execute("select check_id, check_name, rule_applied, rows_affected, raw_rows from marts.dq_log order by 1").fetchdf()

summary = dict(
    versions=dict(dbt_core=run["metadata"]["dbt_version"], adapter=manifest["metadata"].get("adapter_type"),
                  duckdb=duckdb.__version__),
    run=dict(models=n_models, tests=n_tests, nodes=len(run["results"]),
             success=counts.get("success", 0) + counts.get("pass", 0), passed=counts.get("pass", 0),
             models_ok=counts.get("success", 0), warn=counts.get("warn", 0),
             error=counts.get("error", 0) + counts.get("fail", 0), skipped=counts.get("skipped", 0),
             elapsed_seconds=round(float(run["elapsed_time"]), 2)),
    nodes=src_nodes + nodes,
    edges=edges,
    tests_by_type=by_type,
    tests_by_node=per_node,
    tests=sorted(test_rows, key=lambda r: (r["status"] != "warn", r["type"], r["name"])),
    warnings=[r for r in test_rows if r["status"] == "warn"],
    dq_log=[{k: (int(v) if isinstance(v, (np.integer,)) else v) for k, v in rec.items()} for rec in dq.to_dict("records")],
)
(OUT / "dbt_summary.json").write_text(json.dumps(summary, indent=1))

print(f"cube.json {(OUT/'cube.json').stat().st_size/1024:.0f} KB | dbt_summary.json | facts.json | reference_cases.json ({len(cases)} cases)")
print("dbt run:", summary["run"])
print("tests by type:", {k: dict(v) for k, v in by_type.items()})
print("LTM revenue", round(ltm["cur"]["net_revenue"]), "vs", round(ltm["base"]["net_revenue"]),
      f'({ltm["yoy"]["net_revenue_pct"]*100:+.1f}%)', {k: round(v) for k, v in ltm["bridge"].items()})
