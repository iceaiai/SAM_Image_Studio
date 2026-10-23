@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run Install_CPU.bat before building.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m samstudio.selftest
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install "pyinstaller>=6.11,<7"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean packaging\windows.spec
if errorlevel 1 goto failed
echo SAM Image Studio build folder>build\.samstudio-owned
echo SAM Image Studio portable output>dist\.samstudio-owned
copy /y INSTALL_UNINSTALL.md dist\SAM_Image_Studio\INSTALL_UNINSTALL.md >nul
echo Built dist\SAM_Image_Studio\SAM_Image_Studio.exe
echo Copy the entire dist\SAM_Image_Studio folder to the target Windows computer.
echo Model checkpoints are downloaded separately on first use.
echo Run the Windows acceptance checklist before distribution.
pause
exit /b 0
:failed
echo Build failed. No validated Windows executable was produced.
pause
exit /b 1
