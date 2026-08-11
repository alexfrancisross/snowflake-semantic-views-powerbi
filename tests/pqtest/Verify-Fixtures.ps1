# Confirms the live TPCH_RICH_DB.TPCH_RICH_SVS fixtures this test suite
# depends on actually exist, before spending time debugging PQTest/DAX
# failures that are really just "the test data isn't loaded".
#
# Usage:
#   pwsh tests/pqtest/Verify-Fixtures.ps1

param(
    [string]$ConnectionsTomlPath = (Join-Path $env:USERPROFILE ".snowflake\connections.toml"),
    [string]$ConnectionName = "default",
    [string]$Database = "TPCH_RICH_DB",
    [string]$Schema = "TPCH_RICH_SVS"
)

$ErrorActionPreference = "Stop"

$expectedViews = @(
    "SV_CUSTOMER_ORDERS", "SV_CUSTOMER_VALUE", "SV_DAILY_SALES",
    "SV_EDGE_INLINE_TABLE", "SV_EDGE_LOGICAL_MISMATCH", "SV_EDGE_METRIC_FILTER", "SV_EDGE_QUOTED_MIXED_CASE",
    "SV_LINEITEM_DETAIL", "SV_MONTHLY_TRENDS", "SV_PRODUCT_PERFORMANCE", "SV_PRODUCT_SUPPLY",
    "SV_REGIONAL_SALES", "SV_SALES_ANALYSIS", "SV_SHIPPING_ANALYSIS",
    "SV_SUPPLIER_ANALYSIS", "SV_SUPPLIER_INVENTORY", "SV_SUPPLY_CHAIN"
)

if (-not (Test-Path $ConnectionsTomlPath)) {
    throw "connections.toml not found at $ConnectionsTomlPath"
}

$pythonScript = @"
import json, sys, tomllib
import snowflake.connector as sc

with open(r'$ConnectionsTomlPath', 'rb') as f:
    cfg = tomllib.load(f)
conn_cfg = cfg['$ConnectionName']

conn = sc.connect(
    account=conn_cfg['account'],
    user=conn_cfg['user'],
    password=conn_cfg['password'],
    warehouse=conn_cfg.get('warehouse', 'XSMALL'),
)
cur = conn.cursor()

cur.execute('SHOW SEMANTIC VIEWS IN SCHEMA $Database.$Schema')
rows = cur.fetchall()
cols = [c[0] for c in cur.description]
name_idx = cols.index('name')
views = sorted(r[name_idx] for r in rows)

cur.execute('SELECT COUNT(*) FROM $Database.TPCH_RICH_TABLES.LINEITEM')
lineitem_count = cur.fetchone()[0]

print(json.dumps({'views': views, 'lineitem_count': lineitem_count}))
"@

Write-Host "Querying live Snowflake account for TPCH_RICH_DB fixtures..." -ForegroundColor Cyan
$rawOutput = & python -c $pythonScript
if ($LASTEXITCODE -ne 0) {
    throw "Python fixture check failed:`n$rawOutput"
}
$result = $rawOutput | ConvertFrom-Json

$missing = $expectedViews | Where-Object { $result.views -notcontains $_ }
$unexpected = $result.views | Where-Object { $expectedViews -notcontains $_ }

Write-Host "Found $($result.views.Count) semantic views in $Database.$Schema (expected $($expectedViews.Count))." -ForegroundColor White
Write-Host "LINEITEM base table row count: $($result.lineitem_count)" -ForegroundColor White

if ($missing) {
    Write-Host "Missing semantic views:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
}
if ($unexpected) {
    Write-Host "Unexpected extra semantic views (not in the expected list, informational only):" -ForegroundColor Yellow
    $unexpected | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
}

if ($missing -or $result.lineitem_count -eq 0) {
    Write-Host ""
    Write-Host "Fixtures incomplete. Run: snow sql -f tpch_sample_data/01_tpch_rich_setup.sql (and the other 0N_*.sql scripts in that folder) to (re)load the TPCH_RICH_DB dataset." -ForegroundColor Red
    exit 1
}

Write-Host "All expected fixtures present." -ForegroundColor Green
