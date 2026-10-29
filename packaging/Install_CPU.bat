@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap_python.ps1" -Action InstallCPU
set "SAM_STUDIO_INSTALL_STATUS=%errorlevel%"
if not "%SAM_STUDIO_INSTALL_STATUS%"=="0" echo Installation failed. Read the error above; do not remove your projects.
pause
exit /b %SAM_STUDIO_INSTALL_STATUS%
