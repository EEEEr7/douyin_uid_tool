# Build exe and pack a zip for colleagues (Windows, no Python required).
# Run: powershell -ExecutionPolicy Bypass -File .\package_release.ps1

param(
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not $SkipBuild) {
    Write-Host "=== Step 1: Build XTeinkDouyinUID.exe ===" -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "build_exe.ps1")
} else {
    Write-Host "=== Step 1: Skipped build (-SkipBuild) ===" -ForegroundColor Yellow
}

$displayName = [string]::Concat(
    "XTeink ",
    [char]0x6296,
    [char]0x97f3,
    "UID",
    [char]0x91c7,
    [char]0x96c6,
    ".exe"
)
$displayExe = Join-Path $PSScriptRoot $displayName
if (-not (Test-Path -LiteralPath $displayExe)) {
    & (Join-Path $PSScriptRoot "finalize_exe_name.ps1")
}
if (-not (Test-Path -LiteralPath $displayExe)) {
    throw "Build failed: $displayName not found"
}

$version = Get-Date -Format "yyyyMMdd"
$outDir = Join-Path $PSScriptRoot "release\XTeink-DouyinUID"
$zipPath = Join-Path $PSScriptRoot "release\XTeink-DouyinUID-Windows-$version.zip"

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

Write-Host ""
Write-Host "=== Step 2: Assemble release folder ===" -ForegroundColor Cyan

Copy-Item -LiteralPath $displayExe -Destination (Join-Path $outDir $displayName) -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "launch_exe.bat") -Destination $outDir -Force

$usageSrc = Join-Path $PSScriptRoot "USAGE.txt"
if (-not (Test-Path -LiteralPath $usageSrc)) {
    throw "Missing USAGE.txt in project root"
}
Copy-Item -LiteralPath $usageSrc -Destination (Join-Path $outDir "USAGE.txt") -Force
$usageZh = Join-Path $outDir "使用说明.txt"
[System.IO.File]::WriteAllText(
    $usageZh,
    [System.IO.File]::ReadAllText($usageSrc, [System.Text.Encoding]::UTF8),
    (New-Object System.Text.UTF8Encoding $false)
)

Write-Host ""
Write-Host "=== Step 3: Create zip ===" -ForegroundColor Cyan
$releaseParent = Split-Path $outDir -Parent
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -LiteralPath $outDir -DestinationPath $zipPath -Force

$sizeMb = [math]::Round((Get-Item -LiteralPath $zipPath).Length / 1MB, 1)
Write-Host ""
Write-Host "Done. Send this file to colleagues:" -ForegroundColor Green
Write-Host "  $zipPath"
Write-Host "  ($sizeMb MB)"
Write-Host ""
Write-Host "Colleague steps: unzip -> double-click $displayName or launch_exe.bat"
