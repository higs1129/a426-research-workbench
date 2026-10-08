@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_viewer.ps1" %*
set "viewerExit=%errorlevel%"
if not "%viewerExit%"=="0" pause
exit /b %viewerExit%
