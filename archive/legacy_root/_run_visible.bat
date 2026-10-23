@echo off
chcp 65001 >nul
title DGTF v1.21.60 - real-run acceptance batch
cd /d "D:\元DGTF-多模并行架构"
set PYTHONIOENCODING=utf-8
set V60_STREAM=1

echo ============================================================
echo  DGTF v1.21.60  real-run acceptance   (5 runs, ~2-2.5h)
echo    [2] classification distribution : serial, 12 rounds
echo    [3] modes C / E / G / H         : 4 rounds each
echo  live output is also appended to  v60_batch.log
echo ============================================================
echo.

"C:\Users\18432\.workbuddy\binaries\PortableGit\versions\1.2.0\usr\bin\bash.exe" -lc "cd '/c/Users/18432/Desktop/元DGTF-多模并行架构' && V60_STREAM=1 bash _run_batch_v60.sh 2>&1 | tee v60_batch.log"

echo.
echo ============================================================
echo  batch finished.  press any key to close this window.
echo ============================================================
pause >nul
