# Rename built exe to display name: XTeink 抖音UID采集.exe (Unicode-safe).
param(
    [string]$SourceExe = ""
)

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

if (-not $SourceExe) {
    foreach ($candidate in @(
        (Join-Path $toolDir "dist\XTeinkDouyinUID.exe"),
        (Join-Path $toolDir "XTeinkDouyinUID.exe"),
        $displayExe
    )) {
        if (Test-Path -LiteralPath $candidate) {
            $SourceExe = $candidate
            break
        }
    }
}

if (-not $SourceExe -or -not (Test-Path -LiteralPath $SourceExe)) {
    Write-Error "Source exe not found. Run build_exe.ps1 first."
}

Get-ChildItem -LiteralPath $toolDir -Filter "*.exe" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.Name -match "^XTeink" -and $_.Name -ne $displayName -and $_.Name -ne "XTeinkDouyinUID.exe") {
        Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
        Write-Host "Removed old exe: $($_.Name)"
    }
}

$sourceFull = (Resolve-Path -LiteralPath $SourceExe).Path
$displayFull = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($displayExe)

if ($sourceFull -ieq $displayFull) {
    Write-Host "Program exe already named: $displayExe"
} else {
    if (Test-Path -LiteralPath $displayExe) {
        Remove-Item -LiteralPath $displayExe -Force
    }
    Copy-Item -LiteralPath $SourceExe -Destination $displayExe -Force
    Write-Host "Program exe: $displayExe"
}

# Optional alias for scripts that still reference the build name
$aliasExe = Join-Path $toolDir "XTeinkDouyinUID.exe"
if (Test-Path -LiteralPath $aliasExe) {
    Remove-Item -LiteralPath $aliasExe -Force
}
try {
    New-Item -ItemType HardLink -Path $aliasExe -Target $displayExe | Out-Null
} catch {
    Copy-Item -LiteralPath $displayExe -Destination $aliasExe -Force
}
