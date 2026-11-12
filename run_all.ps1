# Reproduce todo el proyecto y exporta las tablas limpias a CSV (carpeta export/).
# Uso, desde esta carpeta:   powershell -ExecutionPolicy Bypass -File .\run_all.ps1
# Para al primer error. Necesita Python 3.11+ (probado con 3.13).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Run([string]$desc, [scriptblock]$cmd) {
    Write-Host "==> $desc" -ForegroundColor Cyan
    & $cmd
    if ($LASTEXITCODE -ne 0) { throw "Fallo en el paso: $desc (codigo $LASTEXITCODE)" }
}

if (-not (Test-Path ".venv")) {
    Run "Crear entorno virtual" { python -m venv .venv }
}
. .\.venv\Scripts\Activate.ps1
$env:DBT_SEND_ANONYMOUS_USAGE_STATS = "False"

Run "Instalar librerias"          { pip install --quiet -r requirements.txt }
Run "1/6 Generar datos sinteticos" { python gen_data.py }
Run "2/6 Cargar en DuckDB (raw)"   { python load_raw.py }
Run "3/6 dbt build (modelos + tests)" {
    Push-Location dbt_project
    dbt build --profiles-dir .
    $code = $LASTEXITCODE
    Pop-Location
    $global:LASTEXITCODE = $code
}
Run "4/6 Forecast y backtest"      { python forecast.py }
Run "5/6 Exportar JSON (out/)"     { python export_site_data.py }
Run "6/6 Exportar tablas a CSV"    { python exportar.py }

Write-Host "`nListo. CSV en .\export\  |  JSON en .\out\  |  Base en .\data\bedbank.duckdb" -ForegroundColor Green
