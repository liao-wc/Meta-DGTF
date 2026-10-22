@echo off
setlocal
cd /d "%~dp0.."
rem Call the PowerShell launcher via -Command. Using -File against the .ps1 has
rem failed in this environment, so keep the -Command form (desktop shortcut
rem compatibility depends on this entrypoint).
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "& '%~dp0start_app.ps1' %*"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo [start_app] launcher failed with exit code %RC%
  echo [start_app] see _app_out_*.log / _app_err_*.log for details
  pause
)
exit /b %RC%
