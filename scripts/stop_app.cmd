@echo off
cd /d "%~dp0.."
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "& '%~dp0start_app.ps1' -Stop %*"
if errorlevel 1 pause
