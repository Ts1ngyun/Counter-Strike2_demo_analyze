@echo off
setlocal
if not exist "%~dp0app\stop.ps1" (
  echo Keep STOP.cmd next to the app folder.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\stop.ps1"
if errorlevel 1 (
  pause
  exit /b 1
)
exit /b 0
