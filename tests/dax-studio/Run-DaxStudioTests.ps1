# Runs the .dax query pack against a running Power BI Desktop session that
# has SnowflakeConnectorFixture.pbip open (dscmd.exe attaches to an already-
# open Desktop session for a given .pbip/.pbix - it does not open files
# itself). This is a smoke check: "does the query execute and produce
# output", not a golden-value diff.
#
# One-time manual setup (see tests/dax-studio/README section in tests/README.md):
#   1. Open tests/dax-studio/SnowflakeConnectorFixture.pbip in Power BI Desktop.
#   2. Complete the connector's auth prompt (Username/Password; password = the PAT
#      from ~/.snowflake/connections.toml). Let the 3 tables load, save.
#   3. Leave Desktop open, then run this script.
#
# Usage:
#   pwsh tests/dax-studio/Run-DaxStudioTests.ps1

param(
    [string]$PbipPath = (Join-Path $PSScriptRoot "SnowflakeConnectorFixture.pbip"),
    [string]$DscmdPath = "C:\Program Files\DAX Studio\dscmd.exe",
    [string]$QueriesDir = (Join-Path $PSScriptRoot "queries"),
    [string]$OutputDir = (Join-Path $PSScriptRoot "output")
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $DscmdPath)) {
    throw "dscmd.exe not found at $DscmdPath. Install DAX Studio, or pass -DscmdPath explicitly."
}
if (-not (Test-Path $PbipPath)) {
    throw "$PbipPath not found."
}

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$queryFiles = Get-ChildItem -Path $QueriesDir -Filter "*.dax" | Sort-Object Name
if (-not $queryFiles) {
    throw "No .dax files found under $QueriesDir"
}

$summary = @()

# Queries known to fail against a live DirectQuery session for reasons outside
# the connector's control (see README.md "Known Limitations") - these are run
# and reported, but a failure here doesn't fail the suite.
$KnownLimitations = @("11-large-limit")

# dscmd.exe -s only matches an open Desktop instance by the .pbip's bare
# filename, not its full path - and -d must be omitted so dscmd resolves
# the AS database itself (the Desktop-visible name isn't a valid catalog name).
$PbipName = Split-Path $PbipPath -Leaf

foreach ($queryFile in $queryFiles) {
    $outputFile = Join-Path $OutputDir "$($queryFile.BaseName).csv"
    $isKnownLimitation = $KnownLimitations -contains $queryFile.BaseName
    Write-Host "Running $($queryFile.Name)..." -ForegroundColor Cyan

    & $DscmdPath csv $outputFile -s $PbipName -f $queryFile.FullName 2>&1 | Tee-Object -Variable dscmdOutput | Out-Null
    $exitCode = $LASTEXITCODE

    $passed = ($exitCode -eq 0) -and (Test-Path $outputFile)
    $summary += [PSCustomObject]@{
        Query             = $queryFile.Name
        Passed            = $passed
        ExitCode          = $exitCode
        Output            = $outputFile
        KnownLimitation   = $isKnownLimitation
    }

    if ($passed) {
        Write-Host "  OK -> $outputFile" -ForegroundColor Green
    } elseif ($isKnownLimitation) {
        Write-Host "  FAILED (exit code $exitCode) - known limitation, not counted against the suite" -ForegroundColor Yellow
        $dscmdOutput | ForEach-Object { Write-Host "    $_" -ForegroundColor Yellow }
    } else {
        Write-Host "  FAILED (exit code $exitCode)" -ForegroundColor Red
        $dscmdOutput | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    }
}

$resultsDir = Join-Path $PSScriptRoot "results"
New-Item -ItemType Directory -Path $resultsDir -Force | Out-Null
$summaryPath = Join-Path $resultsDir "summary.json"
$summary | ConvertTo-Json | Out-File -FilePath $summaryPath -Encoding utf8

$failedCount = @($summary | Where-Object { -not $_.Passed -and -not $_.KnownLimitation }).Count
$knownLimitationFailedCount = @($summary | Where-Object { -not $_.Passed -and $_.KnownLimitation }).Count
Write-Host ""
Write-Host "$($summary.Count - $failedCount - $knownLimitationFailedCount)/$($summary.Count - $knownLimitationFailedCount) queries passed ($knownLimitationFailedCount known limitation(s) excluded). Summary written to $summaryPath" -ForegroundColor $(if ($failedCount -eq 0) { "Green" } else { "Red" })

if ($failedCount -gt 0) {
    exit 1
}
