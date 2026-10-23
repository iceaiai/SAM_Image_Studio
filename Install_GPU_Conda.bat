@echo off
setlocal
cd /d "%~dp0"
where conda >nul 2>&1
if errorlevel 1 (
    echo Install Miniforge or Conda, then open its prompt and run this file again.
    echo See GPU_CONDA_GUIDE.md for the complete steps.
    pause
    exit /b 1
)
call conda run -n base python scripts\install_conda_gpu.py %*
set "SAM_STUDIO_GPU_STATUS=%errorlevel%"
pause
exit /b %SAM_STUDIO_GPU_STATUS%
