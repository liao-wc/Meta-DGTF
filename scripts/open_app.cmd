@echo off
setlocal
cd /d "%~dp0.."
rem Primary launcher: starts or reuses the app, then opens the token URL.
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_app.ps1" %*
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" exit /b 0
rem Fallback: even if the health gate failed, open the local access URL directly.
set "URL="
for /f "usebackq delims=" %%U in (`powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0show_access_url.ps1"`) do set "URL=%%U"
if defined URL (
  start "" "%URL%"
  exit /b 0
)
exit /b %RC%