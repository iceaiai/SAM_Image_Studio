@echo off
setlocal
cd /d "%~dp0.."
where conda >nul 2>&1
if errorlevel 1 (
    echo Open an Anaconda or Miniforge prompt first. See GPU/README.md.
    pause
    exit /b 1
)
call conda run -n base python GPU\install.py %*
set "SAM_STUDIO_GPU_STATUS=%errorlevel%"
pause
exit /b %SAM_STUDIO_GPU_STATUS%
