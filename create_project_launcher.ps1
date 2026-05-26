# Ensure display-name exe exists (calls finalize_exe_name.ps1).
$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "finalize_exe_name.ps1")
