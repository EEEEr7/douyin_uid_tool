# Creates a Desktop shortcut that runs launch_gui.bat (exe / venv / Python fallback).
# Run: powershell -ExecutionPolicy Bypass -File .\create_desktop_shortcut.ps1

$ErrorActionPreference = "Stop"
$toolDir = $PSScriptRoot
$batPath = Join-Path $toolDir "launch_gui.bat"

if (-not (Test-Path -LiteralPath $batPath)) {
    Write-Error "launch_gui.bat not found. Run this script from the douyin_uid_tool folder."
}

$desktop = [Environment]::GetFolderPath("Desktop")
$lnkName =
    [string]::Concat(
        [char]0x6296,
        [char]0x97f3,
        "UID",
        [char]0x63d0,
        [char]0x53d6,
        [char]0x5de5,
        [char]0x5177,
        ".lnk"
    )
$lnkPath = Join-Path $desktop $lnkName

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnkPath)
$shortcut.TargetPath = $batPath
$shortcut.WorkingDirectory = $toolDir
$shortcut.WindowStyle = 1
$shortcut.Description = "Douyin profile URL to numeric UID"

$iconDll = Join-Path $env:SystemRoot "System32\imageres.dll"
$shortcut.IconLocation = "$iconDll,100"
$shortcut.Save()

Write-Host "Desktop shortcut created:"
Write-Host "  $lnkPath"
