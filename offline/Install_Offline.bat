@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\packaging\bootstrap_python.ps1" -Action InstallOffline
set "SAM_STUDIO_OFFLINE_STATUS=%errorlevel%"
pause
exit /b %SAM_STUDIO_OFFLINE_STATUS%
