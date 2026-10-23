@echo off
setlocal
echo Install Python 3.12 64-bit for the current Windows user.
echo Existing Python versions will be kept.
where winget >nul 2>&1
if errorlevel 1 (
    echo WinGet is unavailable. See docs/source/installation.md for the official installer option.
    pause
    exit /b 1
)
winget install --exact --id Python.Python.3.12 --architecture x64 --scope user --source winget
set "SAM_STUDIO_PYTHON_STATUS=%errorlevel%"
echo.
echo Close this window, then run Install_CPU.bat again.
echo If Python is still not detected, open a new PowerShell and run: py -3.12 --version
pause
exit /b %SAM_STUDIO_PYTHON_STATUS%
