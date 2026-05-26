$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

$venvDir = Join-Path $PSScriptRoot ".venv"
$py = Get-Command py.exe -ErrorAction SilentlyContinue
if (-not $py) {
  throw "py.exe not found. Please install Python 3 and enable the Python Launcher."
}

if (-not (Test-Path -LiteralPath $venvDir)) {
  & py -3 -m venv $venvDir
}

$venvPython = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
  throw "Venv python not found at $venvPython"
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r "requirements.txt"
& $venvPython -m pip install -r "requirements-dev.txt"

$iconPng = Join-Path $PSScriptRoot "app_icon.png"
$iconIco = Join-Path $PSScriptRoot "app_icon.ico"
if (Test-Path -LiteralPath $iconPng) {
  & $venvPython (Join-Path $PSScriptRoot "generate_app_icon.py")
}

if (Test-Path -LiteralPath "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path -LiteralPath "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path -LiteralPath "XTeinkDouyinUID.spec") { Remove-Item -Force "XTeinkDouyinUID.spec" }

$iconArg = @()
if (Test-Path -LiteralPath $iconIco) {
  $iconArg = @("--icon", $iconIco, "--add-data", "$iconIco;.")
}
$logoPng = Join-Path $PSScriptRoot "xteink_logo.png"
if (Test-Path -LiteralPath $logoPng) {
  $iconArg += @("--add-data", "$logoPng;.")
}

& $venvPython -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --noconsole `
  --hidden-import browser_cookie3 `
  --hidden-import Cryptodome `
  --hidden-import lz4 `
  --collect-submodules browser_cookie3 `
  --name "XTeinkDouyinUID" `
  @iconArg `
  "main.py"

Write-Host ""
Write-Host "Build complete."
$exeDist = Join-Path $PSScriptRoot "dist\XTeinkDouyinUID.exe"
Write-Host ("EXE: " + $exeDist)

$exeRoot = Join-Path $PSScriptRoot "XTeinkDouyinUID.exe"
if (Test-Path -LiteralPath $exeDist) {
  Copy-Item -LiteralPath $exeDist -Destination $exeRoot -Force
  Write-Host ("Copied next to scripts for double-click: " + $exeRoot)
}

$finalizeScript = Join-Path $PSScriptRoot "finalize_exe_name.ps1"
if (Test-Path -LiteralPath $finalizeScript) {
  & $finalizeScript -SourceExe $exeRoot
}

$shortcutScript = Join-Path $PSScriptRoot "create_desktop_shortcut.ps1"
if (Test-Path -LiteralPath $shortcutScript) {
  Write-Host ""
  Write-Host "Updating desktop shortcut..." -ForegroundColor Cyan
  & $shortcutScript
}

