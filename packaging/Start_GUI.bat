@echo off
setlocal
cd /d "%~dp0.."
set "SAM_STUDIO_ENV=.venv"
if exist "samstudio\resources\offline_profile.json" set "SAM_STUDIO_ENV=.venv-offline"
if not exist "%SAM_STUDIO_ENV%\Scripts\python.exe" (
    echo Run Install_CPU.bat first.
    pause
    exit /b 1
)
"%SAM_STUDIO_ENV%\Scripts\python.exe" -m samstudio %*
if errorlevel 1 (
    echo The application reported an error. See the data folder log and docs/source/installation.md.
    pause
)
