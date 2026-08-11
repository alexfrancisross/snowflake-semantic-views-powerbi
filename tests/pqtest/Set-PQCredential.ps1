# Registers a PQTest credential for SnowflakeSemanticViews, built from the PAT
# in ~/.snowflake/connections.toml. The PAT is never written to the console -
# it is piped directly into PQTest.exe's stdin as a credential JSON payload,
# since `set-credential -cpf <file>` rejects a full credential JSON (that flag
# expects key=value property lines, not the {AuthenticationKind,...} shape
# that `credential-template` emits) - stdin is the only input path that
# accepts the template shape verbatim.
#
# Usage:
#   pwsh tests/pqtest/Set-PQCredential.ps1
#   pwsh tests/pqtest/Set-PQCredential.ps1 -ConnectionsTomlPath <path> -ConnectionName default

param(
    [string]$PQTestPath,
    [string]$MezPath = (Join-Path $PSScriptRoot "..\..\connector\SnowflakeSemanticViews.mez"),
    [string]$ProbeQueryFile = (Join-Path $PSScriptRoot "queries\03-data\SV-Edge-CountRows.query.pq"),
    [string]$ConnectionsTomlPath = (Join-Path $env:USERPROFILE ".snowflake\connections.toml"),
    [string]$ConnectionName = "default"
)

$ErrorActionPreference = "Stop"

if (-not $PQTestPath) {
    $PQTestPath = & (Join-Path $PSScriptRoot "Install-PQTools.ps1")
}
$MezPath = (Resolve-Path $MezPath).Path
$ProbeQueryFile = (Resolve-Path $ProbeQueryFile).Path

if (-not (Test-Path $ConnectionsTomlPath)) {
    throw "connections.toml not found at $ConnectionsTomlPath"
}

# Build the credential JSON with Python (avoids a hand-rolled TOML parser),
# and write it straight to a variable in this process - never to disk, never
# to Write-Host/echo.
$credentialJson = & python -c @"
import tomllib, json
with open(r'$ConnectionsTomlPath', 'rb') as f:
    cfg = tomllib.load(f)
conn = cfg['$ConnectionName']
payload = {
    'AuthenticationKind': 'UsernamePassword',
    'AuthenticationProperties': {'Username': conn['user'], 'Password': conn['password']},
    'PrivacySetting': 'None',
    'Permissions': [],
}
print(json.dumps(payload))
"@

if ($LASTEXITCODE -ne 0 -or -not $credentialJson) {
    throw "Failed to build credential JSON from $ConnectionsTomlPath (connection '$ConnectionName')."
}

Write-Host "Clearing any existing PQTest credentials for this connector..." -ForegroundColor Cyan
& $PQTestPath delete-credential -e $MezPath --ALL | Out-Null

Write-Host "Registering credential (username/password shown never includes the PAT value)..." -ForegroundColor Cyan
$result = $credentialJson | & $PQTestPath set-credential -e $MezPath -q $ProbeQueryFile | ConvertFrom-Json

if ($result.Status -ne "Success") {
    throw "set-credential did not report Success: $($result | ConvertTo-Json -Compress)"
}

Write-Host "Credential registered for data source: $($result.Details.NormalizedPath)" -ForegroundColor Green

Write-Host "Verifying credential against a live probe query..." -ForegroundColor Cyan
$probeOutput = & $PQTestPath run-test -e $MezPath -q $ProbeQueryFile
$probeResult = $probeOutput | ConvertFrom-Json
$status = $probeResult[0].Status

if ($status -ne "Passed") {
    throw "Probe query did not pass after registering credential. Status: $status`n$probeOutput"
}

Write-Host "Live probe query passed - credential is working." -ForegroundColor Green
