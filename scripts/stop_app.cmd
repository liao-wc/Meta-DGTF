@echo off
setlocal
cd /d "%~dp0.."
rem Stop the DGTF app listening on the requested port (default 8765).
rem Extra arguments are forwarded, e.g.  stop_app.cmd -Port 8766
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "& '%~dp0start_app.ps1' -Stop %*"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo [stop_app] launcher failed with exit code %RC%
  pause
)
exit /b %RC%
