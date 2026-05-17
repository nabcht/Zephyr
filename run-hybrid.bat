@echo off
title uZephyr - Primary React Interface
cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo  [ERROR] Virtual environment not found.
    echo  Please run setup.bat first.
    pause
    exit /b 1
)

where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Node.js/npm not found.
    echo  The primary React interface requires npm to start the hybrid stack.
    echo  Install Node.js, then rerun setup.bat or use run-cli.bat as the CLI fallback.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
echo  Starting the primary React interface.
echo  FastAPI: http://127.0.0.1:8000
echo  React:   http://127.0.0.1:5173
echo  Press Ctrl+C to stop both processes.
echo.
npm run dev:hybrid