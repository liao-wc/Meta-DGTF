@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
python agent_daemon.py --interval 60 --knowledge-every 10
