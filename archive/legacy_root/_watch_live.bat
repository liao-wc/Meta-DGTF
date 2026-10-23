@echo off
rem  DGTF v1.21.60 - live view of the running batch.
rem  Double-click this file to watch v60_batch.log grow in real time.
rem  (Kept ASCII-only on purpose: cmd parses .bat in the OEM codepage,
rem   and the project folder name is non-ASCII.)
chcp 65001 >nul
title DGTF v1.21.60 - live run log
cd /d "%~dp0"

echo ============================================================
echo  Watching v60_batch.log   (Ctrl+C to stop watching)
echo  The batch itself keeps running even if you close this window.
echo ============================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$ErrorActionPreference='Continue';" ^
 "if(-not (Test-Path 'v60_batch.log')){Write-Host 'v60_batch.log not found in ' (Get-Location) -ForegroundColor Red; exit 1};" ^
 "Get-Content -LiteralPath 'v60_batch.log' -Wait -Tail 60 -Encoding UTF8"

echo.
echo ============================================================
echo  watcher stopped.  press any key to close.
echo ============================================================
pause >nul
