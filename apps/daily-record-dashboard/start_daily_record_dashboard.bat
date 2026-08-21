@echo off
setlocal

set "DASHBOARD_DATA_ROOT=%DAILY_DRAFT_DATA_ROOT%"
if not defined DASHBOARD_DATA_ROOT set "DASHBOARD_DATA_ROOT=%USERPROFILE%\Documents\DailyRecordDashboard"

python "%~dp0server.py" --data-root "%DASHBOARD_DATA_ROOT%" --open-browser --share-tailscale
if errorlevel 1 pause
