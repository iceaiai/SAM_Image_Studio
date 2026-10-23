@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run Install_CPU.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m samstudio %*
if errorlevel 1 (
    echo The application reported an error. See the data folder log and INSTALL_UNINSTALL.md.
    pause
)
