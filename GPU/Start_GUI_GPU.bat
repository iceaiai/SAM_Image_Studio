@echo off
setlocal
cd /d "%~dp0.."
where conda >nul 2>&1
if errorlevel 1 (
    echo Open a Conda prompt and follow GPU/README.md first.
    pause
    exit /b 1
)
call conda run --no-capture-output -n sam-image-studio-gpu python -m samstudio %*
if errorlevel 1 pause
