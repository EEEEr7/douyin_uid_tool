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

if (Test-Path -LiteralPath "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path -LiteralPath "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path -LiteralPath "DouyinUIDExtractor.spec") { Remove-Item -Force "DouyinUIDExtractor.spec" }

& $venvPython -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --noconsole `
  --hidden-import browser_cookie3 `
  --hidden-import Cryptodome `
  --hidden-import lz4 `
  --collect-submodules browser_cookie3 `
  --name "DouyinUIDExtractor" `
  "main.py"

Write-Host ""
Write-Host "Build complete."
$exeDist = Join-Path $PSScriptRoot "dist\DouyinUIDExtractor.exe"
Write-Host ("EXE: " + $exeDist)

$exeRoot = Join-Path $PSScriptRoot "DouyinUIDExtractor.exe"
if (Test-Path -LiteralPath $exeDist) {
  Copy-Item -LiteralPath $exeDist -Destination $exeRoot -Force
  Write-Host ("Copied next to scripts for double-click: " + $exeRoot)
}

