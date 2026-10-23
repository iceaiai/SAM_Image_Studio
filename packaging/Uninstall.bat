@echo off
setlocal
cd /d "%~dp0.."
rem Use an external Python so Windows can remove the local environment cleanly.
py -3.12 -c "pass" >nul 2>&1
if not errorlevel 1 (
    py -3.12 scripts\uninstall_environment.py
    goto done
)
py -3.11 -c "pass" >nul 2>&1
if not errorlevel 1 (
    py -3.11 scripts\uninstall_environment.py
    goto done
)
python scripts\uninstall_environment.py
:done
echo The application source folder can be deleted manually after you move out any images or projects.
pause
