@echo off
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"

if exist "%ROOT%DouyinUIDExtractor.exe" (
  start "" "%ROOT%DouyinUIDExtractor.exe"
  exit /b 0
)

if exist "%ROOT%dist\DouyinUIDExtractor.exe" (
  start "" "%ROOT%dist\DouyinUIDExtractor.exe"
  exit /b 0
)

echo 未找到 DouyinUIDExtractor.exe，请先运行 build_exe.ps1
pause
exit /b 1
