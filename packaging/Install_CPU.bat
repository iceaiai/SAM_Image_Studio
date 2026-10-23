@echo off
setlocal
cd /d "%~dp0.."
echo SAM Image Studio CPU installation
echo An isolated environment will be created in this folder.
py -3.12 -c "import sys; assert sys.maxsize > 2**32" >nul 2>&1
if not errorlevel 1 (
    py -3.12 scripts\install_environment.py --backend cpu
    goto done
)
python -c "import sys; assert sys.version_info[:2] == (3,12) and sys.maxsize > 2**32" >nul 2>&1
if not errorlevel 1 (
    python scripts\install_environment.py --backend cpu
    goto done
)
echo Python 3.12 64-bit was not found. Other installed Python versions can stay.
echo.
echo 1. Press the Windows key to open Start.
echo 2. Click the search box at the top and type PowerShell.
echo 3. Click Windows PowerShell. Administrator mode is not required.
echo 4. Copy and run this command:
echo.
echo winget install --exact --id Python.Python.3.12 --architecture x64 --scope user --source winget
echo.
echo 5. Close PowerShell and open it again, then run: py -3.12 --version
echo 6. Run Install_CPU.bat again, then Start_GUI.bat.
echo.
echo You can also run the included Install_Python_3_12.bat helper.
echo Or activate a Python 3.12 Conda environment and follow docs/source/installation.md.
echo Official download: https://www.python.org/downloads/
pause
exit /b 1
:done
set "SAM_STUDIO_INSTALL_STATUS=%errorlevel%"
if not "%SAM_STUDIO_INSTALL_STATUS%"=="0" echo Installation failed. See the error above.
if "%SAM_STUDIO_INSTALL_STATUS%"=="0" echo Success. Double-click Start_GUI.bat.
pause
exit /b %SAM_STUDIO_INSTALL_STATUS%
