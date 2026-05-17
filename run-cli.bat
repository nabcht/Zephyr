@echo off
title uZephyr - CLI Fallback Mode
cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo  [ERROR] Virtual environment not found.
    echo  Please run setup.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
echo  Starting the CLI fallback/operator surface...
echo  The primary interface is the React hybrid app via run.bat.
echo.
python main.py %*