@echo off
REM Start latest UI from source or display-name exe
set "ROOT=%~dp0"
cd /d "%ROOT%"

if exist "%ROOT%.venv\Scripts\pythonw.exe" (
  start "" "%ROOT%.venv\Scripts\pythonw.exe" "%ROOT%main.py"
  exit /b 0
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%start_app.ps1"
