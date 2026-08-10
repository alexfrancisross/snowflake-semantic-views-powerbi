# Build script for the Snowflake Semantic Views Power BI custom connector.
#
# Packages connector/src/*.pq, *.pqm, *.resx, *.png into
# connector/SnowflakeSemanticViews.mez (a .mez file is just a ZIP archive
# with these files at the archive root - Power Query loads it directly).
#
# Usage:
#   pwsh connector/build.ps1
#   pwsh connector/build.ps1 -Deploy   # also copy into the local
#                                       # "Power BI Desktop\Custom Connectors" folder

param(
    [switch]$Deploy
)

$ErrorActionPreference = "Stop"

$ConnectorDir = $PSScriptRoot
$SrcDir = Join-Path $ConnectorDir "src"
$OutputFile = Join-Path $ConnectorDir "SnowflakeSemanticViews.mez"

if (-not (Test-Path $SrcDir)) {
    throw "Source directory not found: $SrcDir"
}

$mainSource = Join-Path $SrcDir "SnowflakeSemanticViews.pq"
if (-not (Test-Path $mainSource)) {
    throw "Main connector source not found: $mainSource"
}

Write-Host "Building $OutputFile from $SrcDir ..." -ForegroundColor Cyan

$filesToZip = Get-ChildItem -Path $SrcDir -File | Where-Object {
    $_.Name -eq "SnowflakeSemanticViews.pq" -or
    $_.Extension -in @(".pqm", ".resx", ".png")
}

if ($filesToZip.Count -eq 0) {
    throw "No connector source files found in $SrcDir"
}

Add-Type -AssemblyName System.IO.Compression.FileSystem

if (Test-Path $OutputFile) {
    Remove-Item $OutputFile -Force
}

$zip = [System.IO.Compression.ZipFile]::Open($OutputFile, "Create")
try {
    foreach ($file in $filesToZip) {
        Write-Host "  + $($file.Name)" -ForegroundColor Gray
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $file.FullName, $file.Name) | Out-Null
    }
} finally {
    $zip.Dispose()
}

Write-Host "Built $OutputFile ($($filesToZip.Count) files)" -ForegroundColor Green

if ($Deploy) {
    # Use the shell's resolved Documents folder, not $env:USERPROFILE\Documents literally -
    # when Documents is redirected (e.g. by OneDrive Known Folder Move), Power BI Desktop
    # loads connectors from the redirected path, and a literal-path copy silently misses it.
    $destDir = Join-Path ([Environment]::GetFolderPath("MyDocuments")) "Power BI Desktop\Custom Connectors"
    if (-not (Test-Path $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }
    Copy-Item $OutputFile $destDir -Force
    Write-Host "Deployed to $destDir" -ForegroundColor Green

    # Also cover the literal (non-redirected) path if it differs and already exists, so a
    # stale copy there doesn't shadow the fresh build if Power BI ever falls back to it.
    $literalDir = Join-Path $env:USERPROFILE "Documents\Power BI Desktop\Custom Connectors"
    if ($literalDir -ne $destDir -and (Test-Path $literalDir)) {
        Copy-Item $OutputFile $literalDir -Force
        Write-Host "Also deployed to $literalDir (literal Documents path)" -ForegroundColor Green
    }
}
