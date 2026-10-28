@echo off
setlocal
if not exist "%~dp0app\VERSION" (
  echo Extract the complete ZIP first. Keep START.cmd next to the app folder.
  pause
  exit /b 1
)
if not exist "%~dp0app\.venv\Scripts\python.exe" goto setup
if not exist "%~dp0app\frontend\dist\index.html" goto setup
goto launch
:setup
echo First run: installing locked dependencies. Python 3.12 and Node.js 24 are required.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\setup.ps1"
if errorlevel 1 goto failed
:launch
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\start.ps1"
if errorlevel 1 goto failed
start "" http://127.0.0.1:8765
exit /b 0
:failed
echo Setup or startup failed. See the message above. To retry setup, run app\setup.cmd.
pause
exit /b 1
