@echo off
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"

REM 优先用源码 + 虚拟环境启动：始终是最新界面与逻辑。
REM （若先启动根目录下的 DouyinUIDExtractor.exe，会是「上次打包时的旧界面」。）
if exist "%ROOT%.venv\Scripts\pythonw.exe" (
  start "" "%ROOT%.venv\Scripts\pythonw.exe" "%ROOT%main.py"
  exit /b 0
)

REM 无 venv 时再尝试打包后的 exe（拷贝给别人用时）
if exist "%ROOT%DouyinUIDExtractor.exe" (
  start "" "%ROOT%DouyinUIDExtractor.exe"
  exit /b 0
)

if exist "%ROOT%dist\DouyinUIDExtractor.exe" (
  start "" "%ROOT%dist\DouyinUIDExtractor.exe"
  exit /b 0
)

where py >nul 2>&1 && (
  start "" py -3w "%ROOT%main.py"
  exit /b 0
)
where pythonw >nul 2>&1 && (
  start "" pythonw "%ROOT%main.py"
  exit /b 0
)
where python >nul 2>&1 && (
  start "" python "%ROOT%main.py"
  exit /b 0
)

msg %USERNAME% 未找到可用的启动方式。请在项目目录运行 build_exe.ps1（生成 exe），或创建 .venv 并安装依赖。
exit /b 1
