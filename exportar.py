"""Exporta las tablas limpias de DuckDB a CSV en la carpeta export/."""
import pathlib
import duckdb

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "export"
OUT.mkdir(exist_ok=True)

TABLAS = [
    "fct_bookings", "mart_revenue_cube", "mart_revenue_bridge", "mart_budget_vs_actual",
    "dq_log", "dim_customer", "dim_market", "dim_segment", "dim_supplier_tier", "dim_date",
]

con = duckdb.connect(str(ROOT / "data" / "bedbank.duckdb"), read_only=True)
for t in TABLAS:
    ruta = (OUT / f"{t}.csv").as_posix()
    con.execute(f"copy marts.{t} to '{ruta}' (header, delimiter ',')")
    n = con.execute(f"select count(*) from marts.{t}").fetchone()[0]
    print(f"exportada marts.{t:<24} {n:>9,} filas -> export/{t}.csv")
con.close()
