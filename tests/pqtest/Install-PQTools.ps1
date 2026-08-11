# Discovers PQTest.exe from the Power Query SDK VS Code extension's bundled
# nuget cache, and prints its path. Other scripts in this folder dot-source
# this to get a $PQTestPath variable, or you can run it standalone to check
# what would be discovered.
#
# Usage:
#   pwsh tests/pqtest/Install-PQTools.ps1
#   pwsh tests/pqtest/Install-PQTools.ps1 -PQTestPath "C:\custom\path\PQTest.exe"

param(
    [string]$PQTestPath
)

function Find-PQTestExe {
    param([string]$OverridePath)

    if ($OverridePath) {
        if (-not (Test-Path $OverridePath)) {
            throw "PQTest.exe override path not found: $OverridePath"
        }
        return (Resolve-Path $OverridePath).Path
    }

    $extensionRoot = Join-Path $env:USERPROFILE ".vscode\extensions"
    $sdkExtensions = Get-ChildItem -Path $extensionRoot -Directory -Filter "powerquery.vscode-powerquery-sdk-*" -ErrorAction SilentlyContinue

    if (-not $sdkExtensions) {
        throw "Power Query SDK VS Code extension not found under $extensionRoot. Install it from the VS Code marketplace (ms-powerquery.vscode-powerquery-sdk), or pass -PQTestPath explicitly."
    }

    $candidates = foreach ($ext in $sdkExtensions) {
        $nugetDir = Join-Path $ext.FullName ".nuget"
        if (Test-Path $nugetDir) {
            Get-ChildItem -Path $nugetDir -Directory -Filter "Microsoft.PowerQuery.SdkTools.*" -ErrorAction SilentlyContinue | ForEach-Object {
                $exe = Join-Path $_.FullName "tools\PQTest.exe"
                if (Test-Path $exe) {
                    [PSCustomObject]@{
                        Version = [version]($_.Name -replace "^Microsoft\.PowerQuery\.SdkTools\.", "")
                        Path    = $exe
                    }
                }
            }
        }
    }

    if (-not $candidates) {
        throw "No PQTest.exe found under any Microsoft.PowerQuery.SdkTools.* nuget package in $extensionRoot\powerquery.vscode-powerquery-sdk-*\.nuget\. Open the Power Query SDK extension once in VS Code to trigger tool download, or pass -PQTestPath explicitly."
    }

    return ($candidates | Sort-Object Version -Descending | Select-Object -First 1).Path
}

$resolvedPath = Find-PQTestExe -OverridePath $PQTestPath
Write-Host "PQTest.exe: $resolvedPath" -ForegroundColor Green
return $resolvedPath
