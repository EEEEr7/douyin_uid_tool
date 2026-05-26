# Start XTeink 抖音UID采集.exe from project folder.
$ErrorActionPreference = "Stop"
$toolDir = $PSScriptRoot
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

foreach ($candidate in @(
    $displayExe,
    (Join-Path $toolDir "XTeinkDouyinUID.exe"),
    (Join-Path $toolDir "dist\XTeinkDouyinUID.exe")
)) {
    if (Test-Path -LiteralPath $candidate) {
        Start-Process -FilePath $candidate -WorkingDirectory $toolDir
        exit 0
    }
}

$mainPy = Join-Path $toolDir "main.py"
$pyw = Join-Path $toolDir ".venv\Scripts\pythonw.exe"
if ((Test-Path $mainPy) -and (Test-Path $pyw)) {
    Start-Process -FilePath $pyw -ArgumentList "`"$mainPy`"" -WorkingDirectory $toolDir
    exit 0
}

Write-Error "No XTeink 抖音UID采集.exe found. Run build_exe.ps1 first."
