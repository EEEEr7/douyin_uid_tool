# Creates a Desktop shortcut with a full-size custom icon.
# Run: powershell -ExecutionPolicy Bypass -File .\create_desktop_shortcut.ps1

$ErrorActionPreference = "Stop"
$toolDir = $PSScriptRoot
$mainPy = Join-Path $toolDir "main.py"
$iconIco = Join-Path $toolDir "app_icon.ico"

if (-not (Test-Path -LiteralPath $mainPy)) {
    Write-Error "main.py not found. Run this script from the douyin_uid_tool folder."
}

$launcher = $null
$arguments = "`"$mainPy`""
foreach ($candidate in @(
    (Join-Path $toolDir ".venv\Scripts\pythonw.exe"),
    (Join-Path $toolDir "DouyinUIDExtractor.exe"),
    (Join-Path $toolDir "dist\DouyinUIDExtractor.exe")
)) {
    if (Test-Path -LiteralPath $candidate) {
        $launcher = $candidate
        if ($candidate -like "*DouyinUIDExtractor.exe") {
            $arguments = ""
        }
        break
    }
}

if (-not $launcher) {
    $launcher = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
}
if (-not $launcher) {
    Write-Error "No pythonw.exe or DouyinUIDExtractor.exe found. Create .venv or run build_exe.ps1 first."
}

if (Test-Path -LiteralPath (Join-Path $toolDir "app_icon.png")) {
    $gen = Join-Path $toolDir "generate_app_icon.py"
    if (Test-Path -LiteralPath $gen) {
        $venvPy = Join-Path $toolDir ".venv\Scripts\python.exe"
        if (Test-Path -LiteralPath $venvPy) {
            & $venvPy $gen
        } else {
            & python $gen
        }
    }
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

if (Test-Path -LiteralPath $lnkPath) {
    Remove-Item -LiteralPath $lnkPath -Force
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnkPath)
$shortcut.TargetPath = $launcher
$shortcut.Arguments = $arguments
$shortcut.WorkingDirectory = $toolDir
$shortcut.WindowStyle = 1
$shortcut.Description = "Douyin profile URL to numeric UID"

if (Test-Path -LiteralPath $iconIco) {
    $shortcut.IconLocation = "$iconIco,0"
} else {
    $iconDll = Join-Path $env:SystemRoot "System32\imageres.dll"
    $shortcut.IconLocation = "$iconDll,100"
}
$shortcut.Save()

. (Join-Path $toolDir "Set-ShortcutAppUserModelId.ps1")
Set-ShortcutAppUserModelId -ShortcutPath $lnkPath -AppUserModelId $script:AppUserModelId

Write-Host "Desktop shortcut created:"
Write-Host "  $lnkPath"
Write-Host "Launcher: $launcher"
if ($arguments) { Write-Host "Arguments: $arguments" }
Write-Host "Icon: $($shortcut.IconLocation)"
