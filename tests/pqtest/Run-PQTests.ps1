# Rebuilds the connector .mez and runs the full PQTest suite category by
# category, comparing each query's live output against the committed
# .query.pqout golden snapshot (via PQTest `compare`), writing TRX +
# per-test JSON results into tests/pqtest/results/. Assumes
# Set-PQCredential.ps1 has already been run against this .mez path
# (PQTest credentials key off the connector extension file + data source).
#
# Usage:
#   pwsh tests/pqtest/Run-PQTests.ps1
#   pwsh tests/pqtest/Run-PQTests.ps1 -SkipBuild
#
# To regenerate golden .pqout snapshots after an intentional SQL-generation
# change, re-run with -UpdateSnapshots (writes new .pqout files in place of
# the old ones instead of comparing against them).

param(
    [string]$PQTestPath,
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [switch]$SkipBuild,
    [switch]$UpdateSnapshots
)

$ErrorActionPreference = "Stop"

if (-not $PQTestPath) {
    $PQTestPath = & (Join-Path $PSScriptRoot "Install-PQTools.ps1")
}

$MezPath = Join-Path $RepoRoot "connector\SnowflakeSemanticViews.mez"

if (-not $SkipBuild) {
    Write-Host "Rebuilding connector.mez..." -ForegroundColor Cyan
    & (Join-Path $RepoRoot "connector\build.ps1")
    if (-not $?) {
        throw "connector/build.ps1 failed"
    }
}

$MezPath = (Resolve-Path $MezPath).Path
$ResultsRoot = Join-Path $PSScriptRoot "results"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$RunResultsDir = Join-Path $ResultsRoot $Timestamp
New-Item -ItemType Directory -Path $RunResultsDir -Force | Out-Null

$categories = @(
    @{ Name = "01-unit";     FoldingCheck = $false },
    @{ Name = "02-metadata"; FoldingCheck = $false },
    @{ Name = "03-data";     FoldingCheck = $false },
    @{ Name = "04-folding";  FoldingCheck = $true },
    @{ Name = "05-negative"; FoldingCheck = $false }
)

$overallFailures = @()

foreach ($category in $categories) {
    $categoryDir = Join-Path $PSScriptRoot "queries\$($category.Name)"
    if (-not (Test-Path $categoryDir)) {
        Write-Host "Skipping $($category.Name) (no queries directory found)." -ForegroundColor Yellow
        continue
    }

    $trxPath = Join-Path $RunResultsDir "$($category.Name).trx"
    Write-Host ""
    Write-Host "=== Running category: $($category.Name) ===" -ForegroundColor Cyan

    if ($UpdateSnapshots) {
        $args = @("compare", "-e", $MezPath, "-q", $categoryDir, "-ofp", $categoryDir, "-trx", $trxPath)
    } else {
        $args = @("compare", "-e", $MezPath, "-q", $categoryDir, "-fomof", "-trx", $trxPath)
    }
    if ($category.FoldingCheck) {
        $args += "-foff"
    }

    $rawOutput = & $PQTestPath @args
    $exitCode = $LASTEXITCODE

    $rawOutput | Out-File -FilePath (Join-Path $RunResultsDir "$($category.Name).json") -Encoding utf8

    try {
        $parsed = $rawOutput | ConvertFrom-Json
    } catch {
        Write-Host "Could not parse output for $($category.Name) as JSON - treating as failure." -ForegroundColor Red
        $overallFailures += $category.Name
        continue
    }

    $passed = @($parsed | Where-Object { $_.Status -eq "Passed" })
    $failed = @($parsed | Where-Object { $_.Status -ne "Passed" })

    Write-Host "$($category.Name): $($passed.Count) passed, $($failed.Count) failed (exit code $exitCode)" -ForegroundColor $(if ($failed.Count -eq 0) { "Green" } else { "Red" })

    foreach ($f in $failed) {
        Write-Host "  FAILED: $($f.Name) - $($f.Status)" -ForegroundColor Red
    }

    if ($failed.Count -gt 0) {
        $overallFailures += $category.Name
    }
}

Write-Host ""
if ($overallFailures.Count -gt 0) {
    Write-Host "PQTest suite FAILED in categories: $($overallFailures -join ', ')" -ForegroundColor Red
    Write-Host "Results written to $RunResultsDir" -ForegroundColor White
    exit 1
}

Write-Host "PQTest suite passed across all categories." -ForegroundColor Green
Write-Host "Results written to $RunResultsDir" -ForegroundColor White
