@echo off
setlocal EnableDelayedExpansion
title uZephyr - Setup Wizard
color 0B

:: ============================================================================
::  uZephyr (Zephyr Micro) - Interactive Setup Wizard
:: ============================================================================

echo.
echo  ===============================================================
echo    _  _ ____           _                 __  __ _
echo   ^| ^|^| ^|/ ___^| ___ _ __ ^| ^|__  _   _ _ __ ^|  \/  (_) ___ _ _ ___
echo   ^| ^| ^| \___ \/ _ \ '_ \^| '_ \^| ^| ^| ^| '__^|^| ^|\/^| ^| ^|/ __^| '__/ _ \
echo   ^| ^|_^| ^|___) ^|  __/ ^|_) ^| ^| ^| ^| ^|_^| ^| ^|  ^| ^|  ^| ^| ^| (__^| ^| ^| (_) ^|
echo    \___/^|____/ \___^| .__/^|_^| ^|_^|\__, ^|_^|  ^|_^|  ^|_^|_^|\___^|_^|  \___/
echo                    ^|_^|          ^|___/
echo.
echo   Local-first AI sidekick  -  Setup Wizard
echo  ===============================================================
echo.
echo  This wizard will guide you through the installation step by step.
echo  Press Ctrl+C at any time to cancel.
echo.
pause

:: ────────────────────────────────────────────────────────────────────────────
::  STEP 1: Check Python
:: ────────────────────────────────────────────────────────────────────────────
echo.
echo  ---------------------------------------------------------------
echo   STEP 1/5 : Checking Python Installation
echo  ---------------------------------------------------------------
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python was not found on your system.
    echo.
    echo  Please install Python 3.11 or later from:
    echo    https://www.python.org/downloads/
    echo.
    echo  Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo  [OK] Found: %PYVER%

:: Check minimum version (3.11+)
for /f "tokens=2 delims= " %%a in ("%PYVER%") do set PYVERNUM=%%a
for /f "tokens=1,2 delims=." %%a in ("%PYVERNUM%") do (
    set PYMAJOR=%%a
    set PYMINOR=%%b
)

if %PYMAJOR% lss 3 (
    echo  [WARNING] Python 3.11+ is required. You have %PYVER%.
    echo  Please upgrade Python.
    pause
    exit /b 1
)
if %PYMAJOR% equ 3 if %PYMINOR% lss 11 (
    echo  [WARNING] Python 3.11+ is recommended. You have %PYVER%.
    echo  Some features may not work correctly.
    echo.
    set /p CONT="  Continue anyway? (Y/N): "
    if /i "!CONT!" neq "Y" exit /b 1
)

echo.
echo  [OK] Python version check passed.
echo.
pause

:: ────────────────────────────────────────────────────────────────────────────
::  STEP 2: Create Virtual Environment
:: ────────────────────────────────────────────────────────────────────────────
echo.
echo  ---------------------------------------------------------------
echo   STEP 2/5 : Setting Up Virtual Environment
echo  ---------------------------------------------------------------
echo.

if exist "venv\Scripts\activate.bat" (
    echo  [OK] Virtual environment already exists (venv)
    echo  Activating existing environment...
    call  venv\Scripts\activate.bat
) else (
    echo  Creating virtual environment in venv ...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo  [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo  [OK] Virtual environment created.
    call  venv\Scripts\activate.bat
)

echo  [OK] Virtual environment activated.
echo.
pause

:: ────────────────────────────────────────────────────────────────────────────
::  STEP 3: Install Dependencies
:: ────────────────────────────────────────────────────────────────────────────
echo.
echo  ---------------------------------------------------------------
echo   STEP 3/5 : Installing Dependencies
echo  ---------------------------------------------------------------
echo.
echo  This may take a few minutes depending on your internet speed.
echo  (sentence-transformers and chromadb are the largest packages)
echo.

python -m pip install --upgrade pip >nul 2>&1
echo  [OK] pip upgraded.

pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Some packages failed to install.
    echo  Check the output above for details.
    echo  You can re-run this setup after fixing the issue.
    pause
    exit /b 1
)

echo.
echo  [OK] All dependencies installed successfully.
echo.

where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo  [WARNING] Node.js/npm was not found.
    echo  The primary React interface ^(run.bat^) will stay unavailable until Node.js 18+ is installed.
    echo  The CLI fallback surface will still work.
) else (
    echo  [OK] npm found.
    echo  Installing frontend dependencies for the primary React interface...
    call npm run install:frontend
    if %errorlevel% neq 0 (
        echo.
        echo  [ERROR] Frontend dependencies failed to install.
        echo  Check the output above for details, then rerun setup.bat.
        pause
        exit /b 1
    )
    echo.
    echo  [OK] Frontend dependencies installed successfully.
)
echo.
pause

:: ────────────────────────────────────────────────────────────────────────────
::  STEP 4: Configure .env
:: ────────────────────────────────────────────────────────────────────────────
echo.
echo  ---------------------------------------------------------------
echo   STEP 4/5 : Configuration (.env file)
echo  ---------------------------------------------------------------
echo.

if exist ".env" (
    echo  [OK] .env file already exists. Skipping configuration.
    echo  Edit .env manually if you need to change settings.
) else (
    echo  No .env file found. Let's create one!
    echo.
    echo  Which LLM provider do you want to use?
    echo    1. Ollama  (local, free, requires Ollama installed)
    echo    2. OpenRouter  (cloud, requires API key)
    echo.
    set /p PROVIDER_CHOICE="  Enter choice [1]: "
    if "!PROVIDER_CHOICE!"=="" set PROVIDER_CHOICE=1

    if "!PROVIDER_CHOICE!"=="1" (
        echo.
        echo  --- Ollama Configuration ---
        set /p OLLAMA_URL="  Ollama base URL [http://localhost:11434]: "
        if "!OLLAMA_URL!"=="" set OLLAMA_URL=http://localhost:11434
        set /p OLLAMA_MDL="  Ollama model name [llama3.1:8b]: "
        if "!OLLAMA_MDL!"=="" set OLLAMA_MDL=llama3.1:8b

        (
            echo # uZephyr Configuration
            echo LLM_PROVIDER=ollama
            echo OLLAMA_BASE_URL=!OLLAMA_URL!
            echo OLLAMA_MODEL=!OLLAMA_MDL!
            echo.
            echo # Uncomment to switch to OpenRouter:
            echo # LLM_PROVIDER=openrouter
            echo # OPENROUTER_API_KEY=sk-or-your-key-here
            echo # OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct
        ) > .env
        echo.
        echo  [OK] .env created with Ollama configuration.
    ) else if "!PROVIDER_CHOICE!"=="2" (
        echo.
        echo  --- OpenRouter Configuration ---
        set /p OR_KEY="  OpenRouter API key: "
        set /p OR_MODEL="  OpenRouter model [meta-llama/llama-3.1-8b-instruct]: "
        if "!OR_MODEL!"=="" set OR_MODEL=meta-llama/llama-3.1-8b-instruct

        (
            echo # uZephyr Configuration
            echo LLM_PROVIDER=openrouter
            echo OPENROUTER_API_KEY=!OR_KEY!
            echo OPENROUTER_MODEL=!OR_MODEL!
            echo.
            echo # Uncomment to switch to Ollama:
            echo # LLM_PROVIDER=ollama
            echo # OLLAMA_BASE_URL=http://localhost:11434
            echo # OLLAMA_MODEL=llama3.1:8b
        ) > .env
        echo.
        echo  [OK] .env created with OpenRouter configuration.
    ) else (
        echo  [WARNING] Invalid choice. Creating default .env with Ollama.
        (
            echo # uZephyr Configuration
            echo LLM_PROVIDER=ollama
            echo OLLAMA_BASE_URL=http://localhost:11434
            echo OLLAMA_MODEL=llama3.1:8b
        ) > .env
    )
)

echo.
pause

:: ────────────────────────────────────────────────────────────────────────────
::  STEP 5: Create Required Directories
:: ────────────────────────────────────────────────────────────────────────────
echo.
echo  ---------------------------------------------------------------
echo   STEP 5/5 : Creating Project Directories
echo  ---------------------------------------------------------------
echo.

if not exist "data" mkdir data
echo  [OK] data/
if not exist "logs" mkdir logs
echo  [OK] logs/
if not exist "knowledge" mkdir knowledge
echo  [OK] knowledge/
if not exist "knowledge\memories.md" (
    echo # uZephyr - Durable Memories> knowledge\memories.md
    echo  [OK] knowledge/memories.md (created)
) else (
    echo  [OK] knowledge/memories.md (already exists)
)

echo.
echo  [OK] All directories ready.
echo.
echo  ---------------------------------------------------------------
echo   NEXT: Runtime Preparation Tips
echo  ---------------------------------------------------------------
echo.
echo  uZephyr can now bootstrap missing local runtime assets from inside the CLI.
echo.
echo    - If the Docker sandbox image is missing, use Prepare runtime in React or run /prepare in CLI
echo    - If the embedding model cache is missing, use Prepare runtime in React or run /prepare in CLI
echo    - If you later switch to LlamaCPP and the GGUF model is missing, use Prepare runtime in React or run /prepare in CLI
echo    - If you use Ollama, make sure Ollama is running and your selected model is pulled
echo.
echo  Recommended first trust check after setup:
echo    1. Start the React interface with run.bat
echo    2. Use Prepare runtime if startup guidance prompts for local assets
echo    3. Use Verify runtime in the command center or /verify in the CLI fallback
echo.
pause

:: ────────────────────────────────────────────────────────────────────────────
::  DONE
:: ────────────────────────────────────────────────────────────────────────────
echo.
echo  ===============================================================
echo   Setup Complete!
echo  ===============================================================
echo.
echo   To run uZephyr:
echo.
echo     Primary React interface :  run.bat
echo     Explicit hybrid alias   :  run-hybrid.bat
echo     CLI fallback            :  run-cli.bat
echo.
echo   Or manually:
echo     venv\Scripts\activate
echo     npm run dev:hybrid      (Primary React interface)
echo     python main.py          (CLI fallback)
echo.
echo   After first launch, use Prepare runtime in React or /prepare in CLI
echo   to fetch missing sandbox or local-model assets before verification.
echo.
echo  ===============================================================
echo.
pause
endlocal
