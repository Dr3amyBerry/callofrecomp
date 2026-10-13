$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$analyzer = Join-Path $projectRoot '.local/toolchains/android-performance-analyzer/apa-windows/bin/apa64.exe'
if (-not (Test-Path -LiteralPath $analyzer)) { throw 'Android Performance Analyzer is not installed; see docs/WORKSPACE.md.' }
if (-not $env:ANDROID_HOME) {
    $env:ANDROID_HOME = Join-Path $env:LOCALAPPDATA 'Android/Sdk'
}
if (-not (Test-Path -LiteralPath (Join-Path $env:ANDROID_HOME 'platform-tools/adb.exe'))) {
    throw 'Set ANDROID_HOME to an Android SDK with platform-tools installed.'
}
# Explicit launcher requested by the user; it does not record or inspect the screen.
& $analyzer
