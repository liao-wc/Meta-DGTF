@echo off
setlocal
cd /d "%~dp0.."
rem No PowerShell: launch the pythonw background launcher directly.
start "" /b pythonw "dgtf_app\launcher.py" --open
exit /b 0
