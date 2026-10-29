@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\packaging\bootstrap_python.ps1" -Action PrepareOffline
set "SAM_STUDIO_PREP_STATUS=%errorlevel%"
pause
exit /b %SAM_STUDIO_PREP_STATUS%
