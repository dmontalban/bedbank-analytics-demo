#!/usr/bin/env bash
# Reproduces everything, in order. Needs Python 3.11+ and internet only to install the packages.
set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv
source .venv/bin/activate
pip install --quiet -r requirements.txt
export DBT_SEND_ANONYMOUS_USAGE_STATS=False

python gen_data.py                                   # data/raw/*.csv   (synthetic, seeded, ~48 MB)
python load_raw.py                                   # data/bedbank.duckdb  (schema raw, every column text)
(cd dbt_project && dbt build --profiles-dir .)       # staging -> marts, with tests
python forecast.py                                   # out/forecast.json
python export_site_data.py                           # out/cube.json, facts.json, dbt_summary.json, reference_cases.json
python exportar.py                                   # export/*.csv  (clean marts as CSV)
