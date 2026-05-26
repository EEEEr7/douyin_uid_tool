# Creates a Desktop shortcut: XTeink 抖音UID采集
# Run: powershell -ExecutionPolicy Bypass -File .\create_desktop_shortcut.ps1

$ErrorActionPreference = "Stop"
$toolDir = $PSScriptRoot
$iconIco = Join-Path $toolDir "app_icon.ico"
$displayName = [string]::Concat(
    "XTeink ",
    [char]0x6296,
    [char]0x97f3,
    "UID",
    [char]0x91c7,
    [char]0x96c6,
    ".exe"
)
$displayExe = Join-Path $toolDir $displayName

& (Join-Path $toolDir "finalize_exe_name.ps1") 2>$null

$launcher = $null
$arguments = ""
foreach ($candidate in @(
    $displayExe,
    (Join-Path $toolDir "XTeinkDouyinUID.exe"),
    (Join-Path $toolDir "dist\XTeinkDouyinUID.exe")
)) {
    if (Test-Path -LiteralPath $candidate) {
        $launcher = $candidate
        break
    }
}

if (-not $launcher) {
    $mainPy = Join-Path $toolDir "main.py"
    if (-not (Test-Path -LiteralPath $mainPy)) {
        Write-Error "No program exe found. Run build_exe.ps1 first."
    }
    $pyw = Join-Path $toolDir ".venv\Scripts\pythonw.exe"
    if (Test-Path -LiteralPath $pyw) {
        $launcher = $pyw
        $arguments = "`"$mainPy`""
    } else {
        Write-Error "No exe or .venv pythonw found. Run build_exe.ps1 first."
    }
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
$lnkName = [System.IO.Path]::ChangeExtension($displayName, ".lnk")
$lnkPath = Join-Path $desktop $lnkName

Get-ChildItem -LiteralPath $desktop -Filter "*.lnk" -ErrorAction SilentlyContinue | ForEach-Object {
    $s = (New-Object -ComObject WScript.Shell).CreateShortcut($_.FullName)
    if ($s.TargetPath -like "*douyin_uid_tool*") {
        if ($_.Name -match "UID|XTeink|Douyin|抖音") {
            Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
        }
    }
}

if (Test-Path -LiteralPath $lnkPath) {
    Remove-Item -LiteralPath $lnkPath -Force
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($lnkPath)
$shortcut.TargetPath = $launcher
$shortcut.Arguments = $arguments
$shortcut.WorkingDirectory = $toolDir
$shortcut.WindowStyle = 1
$shortcut.Description = [string]::Concat(
    [System.IO.Path]::GetFileNameWithoutExtension($displayName),
    " v1.2.0"
)

if (Test-Path -LiteralPath $iconIco) {
    $shortcut.IconLocation = "$iconIco,0"
} elseif (Test-Path -LiteralPath $launcher) {
    $shortcut.IconLocation = "$launcher,0"
}
$shortcut.Save()

. (Join-Path $toolDir "Set-ShortcutAppUserModelId.ps1")
Set-ShortcutAppUserModelId -ShortcutPath $lnkPath -AppUserModelId $script:AppUserModelId

Write-Host ""
Write-Host "Desktop shortcut:" -ForegroundColor Green
Write-Host "  $lnkPath"
Write-Host "  Target: $launcher"
