#!/usr/bin/env python3
"""Land the raw CSV exports in DuckDB (schema `raw`) exactly as delivered: every column VARCHAR.
Typing, cleaning and deduplication are the job of the dbt staging layer, not of the loader."""
import pathlib
import duckdb

ROOT = pathlib.Path(__file__).resolve().parent
DB = ROOT / "data" / "bedbank.duckdb"
if DB.exists():
    DB.unlink()
con = duckdb.connect(str(DB))
con.execute("create schema raw")
for name in ["bookings", "customers", "markets", "segments", "supplier_tiers", "budget"]:
    con.execute(
        f"create table raw.{name} as select * from read_csv('{(ROOT / 'data' / 'raw' / (name + '.csv')).as_posix()}', header=true, all_varchar=true)"
    )
    n = con.execute(f"select count(*) from raw.{name}").fetchone()[0]
    print(f"raw.{name:<15} {n:>9,} rows")
con.close()
