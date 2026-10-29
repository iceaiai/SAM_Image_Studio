@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap_python.ps1" -Action PreparePython
set "SAM_STUDIO_PYTHON_STATUS=%errorlevel%"
pause
exit /b %SAM_STUDIO_PYTHON_STATUS%
