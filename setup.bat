@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Zephyr - Setup Wizard
color 0B

pushd "%~dp0" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERROR] Could not switch into the project directory.
    pause
    exit /b 1
)

set "PROJECT_ROOT=%CD%"
set "ENV_FILE=%PROJECT_ROOT%\.env"
set "ENV_TMP=%PROJECT_ROOT%\.env.setup.tmp"

set "NPM_AVAILABLE=N"
set "NPX_AVAILABLE=N"
set "UVX_AVAILABLE=N"
set "OLLAMA_AVAILABLE=N"
set "NVIDIA_AVAILABLE=N"

set "NODE_VERSION=not installed"
set "NPM_VERSION=not installed"
set "OLLAMA_VERSION=not installed"
set "GPU_NAME=not detected"

set "PYTHON_DEPS_STATUS=SKIPPED"
set "FRONTEND_DEPS_STATUS=SKIPPED"
set "CUDA_TORCH_STATUS=SKIPPED"
set "CONFIG_STATUS=SKIPPED"
set "CONFIG_IMPORT_STATUS=SKIPPED"
set "EMBEDDING_PREFETCH_STATUS=SKIPPED"
set "OLLAMA_PREFETCH_STATUS=SKIPPED"
set "LLAMACPP_PREFETCH_STATUS=SKIPPED"

set "CONFIG_WRITTEN=N"
set "CUSTOM_PATHS=N"
set "SELECTED_PROVIDER="
set "MCP_ENABLED=false"
set "EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED=false"

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
echo  This wizard now covers prerequisites, backend/frontend installs,
echo  provider selection, MCP options, sandbox defaults, and optional
echo  local acceleration and runtime asset preparation.
echo.
echo  Press Ctrl+C at any time to cancel.
echo.
pause

:: --------------------------------------------------------------------------
:: STEP 1/6 - System checks
:: --------------------------------------------------------------------------
echo.
echo  ---------------------------------------------------------------
echo   STEP 1/6 : Checking System Prerequisites
echo  ---------------------------------------------------------------
echo.

where python >nul 2>&1
if errorlevel 1 call :AbortSetup "Python was not found. Install Python 3.11+ and add it to PATH first."

for /f "tokens=*" %%I in ('python --version 2^>^&1') do set "PYVER=%%I"
for /f "tokens=2 delims= " %%A in ("%PYVER%") do set "PYVERNUM=%%A"
for /f "tokens=1,2 delims=." %%A in ("%PYVERNUM%") do (
    set "PYMAJOR=%%A"
    set "PYMINOR=%%B"
)

if %PYMAJOR% lss 3 call :AbortSetup "Python 3.11+ is required. Found %PYVER%."
if %PYMAJOR% equ 3 if %PYMINOR% lss 11 (
    echo  [WARNING] Python 3.11+ is recommended. Found %PYVER%.
    call :PromptYesNo CONTINUE_PYTHON "  Continue anyway? (Y/N) [N]: " "N"
    if /I "%CONTINUE_PYTHON%" neq "Y" call :AbortSetup "Setup cancelled because the Python version is below 3.11."
)

where npm >nul 2>&1
if not errorlevel 1 (
    set "NPM_AVAILABLE=Y"
    for /f "tokens=*" %%I in ('node --version 2^>nul') do set "NODE_VERSION=%%I"
    for /f "tokens=*" %%I in ('npm --version 2^>nul') do set "NPM_VERSION=%%I"
)

where npx >nul 2>&1
if not errorlevel 1 set "NPX_AVAILABLE=Y"

where uvx >nul 2>&1
if not errorlevel 1 set "UVX_AVAILABLE=Y"

where ollama >nul 2>&1
if not errorlevel 1 (
    set "OLLAMA_AVAILABLE=Y"
    for /f "tokens=*" %%I in ('ollama --version 2^>nul') do set "OLLAMA_VERSION=%%I"
)

where nvidia-smi >nul 2>&1
if not errorlevel 1 (
    set "NVIDIA_AVAILABLE=Y"
    for /f "usebackq delims=" %%I in (`nvidia-smi --query-gpu=name --format=csv^,noheader 2^>nul`) do (
        if /I "!GPU_NAME!"=="not detected" set "GPU_NAME=%%I"
    )
)

echo  [OK] Python : %PYVER%
if /I "%NPM_AVAILABLE%"=="Y" (
    echo  [OK] Node   : %NODE_VERSION%
    echo  [OK] npm    : %NPM_VERSION%
) else (
    echo  [WARN] Node/npm not detected. The React interface will stay unavailable until Node.js 18+ is installed.
)

if /I "%NPX_AVAILABLE%"=="Y" (
    echo  [OK] npx    : available
) else (
    echo  [INFO] npx   : not found ^(only needed for some remote MCP bridge setups^)
)

if /I "%UVX_AVAILABLE%"=="Y" (
    echo  [OK] uvx    : available
) else (
    echo  [INFO] uvx   : not found ^(optional for remote MCP bridge setups^)
)

if /I "%OLLAMA_AVAILABLE%"=="Y" (
    echo  [OK] Ollama : %OLLAMA_VERSION%
) else (
    echo  [INFO] Ollama: not found ^(only needed if you plan to use the Ollama provider^)
)

if /I "%NVIDIA_AVAILABLE%"=="Y" (
    echo  [OK] NVIDIA : %GPU_NAME%
) else (
    echo  [INFO] CUDA  : no NVIDIA GPU detected via nvidia-smi
)

echo.
pause

:: --------------------------------------------------------------------------
:: STEP 2/6 - Virtual environment
:: --------------------------------------------------------------------------
echo.
echo  ---------------------------------------------------------------
echo   STEP 2/6 : Virtual Environment
echo  ---------------------------------------------------------------
echo.

if exist "venv\Scripts\activate.bat" (
    echo  [INFO] Existing virtual environment detected at .\venv
    call :PromptYesNo RECREATE_VENV "  Recreate it from scratch? (Y/N) [N]: " "N"
    if /I "%RECREATE_VENV%"=="Y" (
        echo  Removing old virtual environment...
        rmdir /s /q "venv"
    )
)

if not exist "venv\Scripts\activate.bat" (
    echo  Creating virtual environment...
    python -m venv venv
    if errorlevel 1 call :AbortSetup "Failed to create the virtual environment."
    echo  [OK] Virtual environment created.
) else (
    echo  [OK] Reusing the existing virtual environment.
)

call "venv\Scripts\activate.bat"
if errorlevel 1 call :AbortSetup "Failed to activate the virtual environment."

echo  [OK] Virtual environment activated.
echo.
pause

:: --------------------------------------------------------------------------
:: STEP 3/6 - Dependencies and acceleration options
:: --------------------------------------------------------------------------
echo.
echo  ---------------------------------------------------------------
echo   STEP 3/6 : Dependencies And Acceleration Options
echo  ---------------------------------------------------------------
echo.

call :PromptYesNo INSTALL_PYTHON_DEPS "  Install or refresh Python dependencies now? (Y/N) [Y]: " "Y"
if /I "%INSTALL_PYTHON_DEPS%"=="Y" (
    echo  Upgrading pip...
    python -m pip install --upgrade pip
    if errorlevel 1 call :AbortSetup "pip upgrade failed."

    echo.
    echo  Installing shared and hybrid-backend Python dependencies...
    echo  ^(backend\requirements.txt includes the root requirements plus FastAPI/Uvicorn^)
    pip install -r backend\requirements.txt
    if errorlevel 1 call :AbortSetup "Python dependency installation failed. Review the output above and rerun setup.bat."
    set "PYTHON_DEPS_STATUS=INSTALLED"

    if /I "%NVIDIA_AVAILABLE%"=="Y" (
        echo.
        echo  Optional CUDA path for embeddings/search:
        echo    - This reinstalls torch from the official CUDA 12.4 wheel index.
        echo    - Use it when you specifically want SentenceTransformer embeddings on GPU.
        echo    - LlamaCPP GPU usage is configured separately in the .env step.
        echo.
        call :PromptYesNo INSTALL_CUDA_TORCH "  Install CUDA-enabled torch now? (Y/N) [N]: " "N"
        if /I "%INSTALL_CUDA_TORCH%"=="Y" (
            pip install --upgrade torch --index-url https://download.pytorch.org/whl/cu126
            if errorlevel 1 (
                set "CUDA_TORCH_STATUS=FAILED"
                echo  [WARNING] CUDA torch installation failed. Setup will continue with the currently installed wheel.
            ) else (
                set "CUDA_TORCH_STATUS=INSTALLED"
                echo  [OK] CUDA-enabled torch installed.
            )
        )
    )

    echo.
    echo  Running pip dependency check...
    python -m pip check
    if errorlevel 1 (
        echo  [WARNING] pip check reported dependency issues. Review the lines above if runtime problems appear later.
    ) else (
        echo  [OK] pip dependency check passed.
    )
) else (
    set "PYTHON_DEPS_STATUS=SKIPPED_BY_USER"
    echo  [INFO] Skipping Python dependency installation. The app may not start until dependencies are installed.
)

if /I "%NPM_AVAILABLE%"=="Y" (
    echo.
    call :PromptYesNo INSTALL_FRONTEND_DEPS "  Install or refresh frontend dependencies now? (Y/N) [Y]: " "Y"
    if /I "%INSTALL_FRONTEND_DEPS%"=="Y" (
        call npm run install:frontend
        if errorlevel 1 call :AbortSetup "Frontend dependency installation failed."
        set "FRONTEND_DEPS_STATUS=INSTALLED"
        echo  [OK] Frontend dependencies installed.
    ) else (
        set "FRONTEND_DEPS_STATUS=SKIPPED_BY_USER"
        echo  [INFO] Skipping frontend dependency installation.
    )
) else (
    set "FRONTEND_DEPS_STATUS=UNAVAILABLE_NO_NODE"
)

echo.
pause

:: --------------------------------------------------------------------------
:: STEP 4/6 - Guided .env configuration
:: --------------------------------------------------------------------------
echo.
echo  ---------------------------------------------------------------
echo   STEP 4/6 : Guided Runtime Configuration
echo  ---------------------------------------------------------------
echo.

set "ENV_ACTION=2"
set "HAD_EXISTING_ENV=N"
if exist "%ENV_FILE%" (
    set "HAD_EXISTING_ENV=Y"
    echo  [INFO] An existing .env file was found.
    echo    1. Keep the current .env and skip the wizard
    echo    2. Back it up and rebuild it with guided prompts
    echo.
    call :PromptChoice ENV_ACTION "  Enter choice [1]: " "1" "1 2"
)

if "!ENV_ACTION!"=="1" (
    set "CONFIG_STATUS=KEPT_EXISTING"
    echo  [OK] Keeping the existing .env file untouched.
) else (
    call :RebuildEnv
)

echo.
pause

:: --------------------------------------------------------------------------
:: STEP 5/6 - Directories, config sanity, optional asset prep
:: --------------------------------------------------------------------------
echo.
echo  ---------------------------------------------------------------
echo   STEP 5/6 : Directories, Config Sanity, And Asset Prep
echo  ---------------------------------------------------------------
echo.

call :EnsureDirectory "data"
call :EnsureDirectory "data\vector_store"
call :EnsureDirectory "data\keyword_index"
call :EnsureDirectory "logs"
call :EnsureDirectory "knowledge"
call :EnsureDirectory "knowledge\brain"
call :EnsureDirectory "knowledge\brain\personas"
call :EnsureDirectory "knowledge\brain\entities"
call :EnsureDirectory "LLM"
call :EnsureDirectory "LLM\gemma-4"
call :EnsureDirectory "LLM\vector-models"

if /I "%CUSTOM_PATHS%"=="Y" (
    call :EnsureDirectoryFromVar "SEARCH_DIR"
    call :EnsureParentFromVar "DB_PATH"
    call :EnsureDirectoryFromVar "VECTOR_STORE_DIR"
    call :EnsureDirectoryFromVar "EMBEDDING_MODEL_DIR"
)

if /I "%SELECTED_PROVIDER%"=="llamacpp" call :EnsureParentFromVar "LLAMACPP_MODEL_PATH"

if not exist "knowledge\memories.md" (
    > "knowledge\memories.md" echo # Zephyr - Durable Memories
    echo  [OK] Created knowledge\memories.md
) else (
    echo  [OK] knowledge\memories.md already exists
)

if exist "%ENV_FILE%" (
    echo.
    echo  Running a quick config import sanity check...
    python -c "import config; print('  Provider=' + config.LLM_PROVIDER); print('  Sandbox=' + config.SANDBOX_BACKEND); print('  MCP Enabled=' + str(config.MCP_ENABLED).lower()); print('  MCP Servers=' + str(len(config.get_mcp_server_configs())))"
    if errorlevel 1 (
        set "CONFIG_IMPORT_STATUS=FAILED"
        echo  [WARNING] Config import failed. Review the traceback above before launching the app.
    ) else (
        set "CONFIG_IMPORT_STATUS=PASSED"
        echo  [OK] Config import passed.
    )
) else (
    set "CONFIG_IMPORT_STATUS=NO_ENV"
)

if /I "%CONFIG_WRITTEN%"=="Y" (
    echo.
    call :PromptYesNo PREFETCH_EMBEDDINGS "  Cache the embedding model now? (Y/N) [N]: " "N"
    if /I "%PREFETCH_EMBEDDINGS%"=="Y" (
        python download_vector_model.py
        if errorlevel 1 (
            set "EMBEDDING_PREFETCH_STATUS=FAILED"
            echo  [WARNING] Embedding model prefetch failed.
        ) else (
            set "EMBEDDING_PREFETCH_STATUS=DONE"
            echo  [OK] Embedding model cached.
        )
    )

    if /I "%SELECTED_PROVIDER%"=="ollama" if /I "%OLLAMA_AVAILABLE%"=="Y" (
        echo.
        call :PromptYesNo PREFETCH_OLLAMA "  Pull the selected Ollama model now? (Y/N) [N]: " "N"
        if /I "%PREFETCH_OLLAMA%"=="Y" (
            call ollama pull "%OLLAMA_MODEL%"
            if errorlevel 1 (
                set "OLLAMA_PREFETCH_STATUS=FAILED"
                echo  [WARNING] Ollama model pull failed.
            ) else (
                set "OLLAMA_PREFETCH_STATUS=DONE"
                echo  [OK] Ollama model pulled.
            )
        )
    )

    if /I "%SELECTED_PROVIDER%"=="llamacpp" (
        echo.
        call :PromptYesNo PREFETCH_LLAMACPP "  Fetch the default LlamaCPP assets now? (Y/N) [N]: " "N"
        if /I "%PREFETCH_LLAMACPP%"=="Y" (
            python -c "from core.llm import ensure_models; ensure_models(); print('LlamaCPP assets ready.')"
            if errorlevel 1 (
                set "LLAMACPP_PREFETCH_STATUS=FAILED"
                echo  [WARNING] LlamaCPP asset preparation failed.
            ) else (
                set "LLAMACPP_PREFETCH_STATUS=DONE"
                echo  [OK] LlamaCPP assets prepared.
            )
        )
    )
)

echo.
pause

:: --------------------------------------------------------------------------
:: STEP 6/6 - Summary
:: --------------------------------------------------------------------------
echo.
echo  ---------------------------------------------------------------
echo   STEP 6/6 : Summary And Next Steps
echo  ---------------------------------------------------------------
echo.
echo  Setup status summary:
echo    Python deps          : %PYTHON_DEPS_STATUS%
echo    Frontend deps        : %FRONTEND_DEPS_STATUS%
echo    CUDA torch           : %CUDA_TORCH_STATUS%
echo    .env                 : %CONFIG_STATUS%
echo    Config import        : %CONFIG_IMPORT_STATUS%
echo    Embedding prefetch   : %EMBEDDING_PREFETCH_STATUS%
echo    Ollama prefetch      : %OLLAMA_PREFETCH_STATUS%
echo    LlamaCPP prefetch    : %LLAMACPP_PREFETCH_STATUS%
if defined SELECTED_PROVIDER echo    Selected provider     : %SELECTED_PROVIDER%

echo.
echo  To run Zephyr:
echo.
echo    Primary React interface : run.bat
echo    Explicit hybrid alias   : run-hybrid.bat
echo    CLI fallback            : run-cli.bat
echo.
echo  Or manually:
echo    venv\Scripts\activate
echo    npm run dev:hybrid      ^(Primary React interface^)
echo    python main.py          ^(CLI fallback^)
echo.
echo  Recommended first checks after setup:
echo    1. Start the React interface with run.bat
echo    2. Use Prepare runtime in React or /prepare in the CLI when local assets are missing
echo    3. Use Verify runtime in the command center or /verify in the CLI fallback
echo.
if /I "%CUDA_TORCH_STATUS%"=="FAILED" (
    echo  CUDA note:
    echo    python -m pip install --upgrade torch --index-url https://download.pytorch.org/whl/cu126
    echo.
)
if /I "%MCP_ENABLED%"=="true" if not defined MCP_SERVER_COMMAND (
    echo  MCP note:
    echo    MCP was enabled without a server command. You can finish that later in the web Command Center.
    echo.
)

pause
goto :script_end

:Prompt
setlocal DisableDelayedExpansion
set "INPUT="
set /p "INPUT=%~2"
if not defined INPUT set "INPUT=%~3"
endlocal & set "%~1=%INPUT%"
exit /b

:PromptYesNo
setlocal EnableDelayedExpansion
set "PROMPT=%~2"
set "DEFAULT=%~3"
:PromptYesNoLoop
call :Prompt "_YN_VALUE" "!PROMPT!" "!DEFAULT!"
if /I "!_YN_VALUE!"=="Y" endlocal & set "%~1=Y" & exit /b 0
if /I "!_YN_VALUE!"=="YES" endlocal & set "%~1=Y" & exit /b 0
if /I "!_YN_VALUE!"=="N" endlocal & set "%~1=N" & exit /b 0
if /I "!_YN_VALUE!"=="NO" endlocal & set "%~1=N" & exit /b 0
echo  [WARNING] Please answer Y or N.
goto :PromptYesNoLoop

:PromptChoice
setlocal EnableDelayedExpansion
set "PROMPT=%~2"
set "DEFAULT=%~3"
set "ALLOWED=%~4"
:PromptChoiceLoop
call :Prompt "_CHOICE_VALUE" "!PROMPT!" "!DEFAULT!"
set "CHOICE_OK="
for %%A in (!ALLOWED!) do (
    if /I "%%~A"=="!_CHOICE_VALUE!" set "CHOICE_OK=1"
)
if defined CHOICE_OK (
    for /f "delims=" %%A in ("!_CHOICE_VALUE!") do (
        endlocal
        set "%~1=%%~A"
        exit /b 0
    )
)
echo  [WARNING] Invalid choice. Allowed values: !ALLOWED!
goto :PromptChoiceLoop

:RebuildEnv
if exist "%ENV_FILE%" (
    for /f %%I in ('powershell -NoProfile -Command "(Get-Date).ToString('yyyyMMdd-HHmmss')" 2^>nul') do set "ENV_STAMP=%%I"
    if not defined ENV_STAMP set "ENV_STAMP=backup"
    set "ENV_BACKUP=%ENV_FILE%.backup-!ENV_STAMP!"
    copy /y "%ENV_FILE%" "!ENV_BACKUP!" >nul
    echo  [OK] Backed up the existing .env to:
    echo       !ENV_BACKUP!
)

set "SELECTED_PROVIDER=ollama"
set "OLLAMA_BASE_URL=http://localhost:11434"
set "OLLAMA_MODEL=llama3.1:8b"
set "OPENROUTER_API_KEY="
set "OPENROUTER_MODEL=openai/gpt-oss-120b:free"
set "LLAMACPP_MODEL_PATH=LLM/gemma-4/gemma-4-E4B-it-UD-Q8_K_XL.gguf"
set "LLAMACPP_N_CTX=32768"
set "LLAMACPP_N_GPU_LAYERS=0"
set "EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2"
set "REQUIRE_CONFIRMATION=false"
set "SANDBOX_BACKEND=auto"
set "SANDBOX_DOCKER_IMAGE=python:3.11-slim"
set "SEARCH_DIR=."
set "DB_PATH=data/zephyr.db"
set "VECTOR_STORE_DIR=data/vector_store"
set "EMBEDDING_MODEL_DIR=LLM/vector-models"
set "MCP_ENABLED=false"
set "EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED=false"
set "MCP_SERVER_NAME=archive"
set "MCP_SERVER_COMMAND="
set "MCP_SERVER_ARGS="
set "MCP_SERVER_ENV="
set "MCP_SERVER_CWD="
set "MCP_TOOL_PREFIX=mcp"
set "MCP_SERVER_CONNECT_TIMEOUT_SECONDS="
set "MCP_SERVER_DISCOVERY_TIMEOUT_SECONDS="
set "MCP_SERVER_TOOL_TIMEOUT_SECONDS="
set "MCP_SERVER_MAX_RETRIES="
set "MCP_SERVER_RETRY_BACKOFF_SECONDS="

echo  Choose the primary inference provider:
echo    1. Ollama     ^(local runtime, requires Ollama^)
echo    2. OpenRouter ^(cloud runtime, requires API key^)
echo    3. LlamaCPP   ^(local GGUF runtime^)
echo.
call :PromptChoice PROVIDER_CHOICE "  Enter choice [1]: " "1" "1 2 3"

if "%PROVIDER_CHOICE%"=="1" call :ConfigureOllama
if "%PROVIDER_CHOICE%"=="2" call :ConfigureOpenRouter
if "%PROVIDER_CHOICE%"=="3" call :ConfigureLlamaCpp

echo.
call :Prompt EMBEDDING_MODEL_NAME "  Embedding model [sentence-transformers/all-MiniLM-L6-v2]: " "sentence-transformers/all-MiniLM-L6-v2"
call :PromptYesNo REQUIRE_CONFIRMATION_CHOICE "  Require confirmation before sensitive tools run? (Y/N) [N]: " "N"
if /I "%REQUIRE_CONFIRMATION_CHOICE%"=="Y" (
    set "REQUIRE_CONFIRMATION=true"
) else (
    set "REQUIRE_CONFIRMATION=false"
)

echo.
echo  Sandbox backend:
echo    1. auto   ^(recommended^)
echo    2. docker
echo    3. venv
echo    4. wasm
echo.
call :PromptChoice SANDBOX_CHOICE "  Enter choice [1]: " "1" "1 2 3 4"
if "%SANDBOX_CHOICE%"=="1" set "SANDBOX_BACKEND=auto"
if "%SANDBOX_CHOICE%"=="2" set "SANDBOX_BACKEND=docker"
if "%SANDBOX_CHOICE%"=="3" set "SANDBOX_BACKEND=venv"
if "%SANDBOX_CHOICE%"=="4" set "SANDBOX_BACKEND=wasm"
call :Prompt SANDBOX_DOCKER_IMAGE "  Docker image for auto/docker sandbox [python:3.11-slim]: " "python:3.11-slim"

echo.
call :PromptYesNo CUSTOM_PATHS "  Customize local data/search paths? (Y/N) [N]: " "N"
if /I "%CUSTOM_PATHS%"=="Y" call :ConfigureCustomPaths

echo.
call :PromptYesNo CONFIGURE_MCP "  Configure MCP integration now? (Y/N) [N]: " "N"
if /I "%CONFIGURE_MCP%"=="Y" call :ConfigureMcp

call :WriteEnvFile

set "CONFIG_STATUS=CREATED"
if /I "%HAD_EXISTING_ENV%"=="Y" set "CONFIG_STATUS=REBUILT"
set "CONFIG_WRITTEN=Y"
echo.
echo  [OK] Wrote a fresh .env file.
exit /b

:ConfigureOllama
set "SELECTED_PROVIDER=ollama"
call :Prompt OLLAMA_BASE_URL "  Ollama base URL [http://localhost:11434]: " "http://localhost:11434"
call :Prompt OLLAMA_MODEL "  Ollama model name [llama3.1:8b]: " "llama3.1:8b"
if /I "%OLLAMA_AVAILABLE%"=="N" echo  [INFO] Ollama is not installed yet. The saved config will still work once Ollama is installed and running.
exit /b

:ConfigureOpenRouter
set "SELECTED_PROVIDER=openrouter"
call :Prompt OPENROUTER_API_KEY "  OpenRouter API key [leave blank to fill in later]: " ""
call :Prompt OPENROUTER_MODEL "  OpenRouter model [openai/gpt-oss-120b:free]: " "openai/gpt-oss-120b:free"
if not defined OPENROUTER_API_KEY echo  [WARNING] OPENROUTER_API_KEY is blank. Cloud inference will stay unavailable until you edit .env.
exit /b

:ConfigureLlamaCpp
set "SELECTED_PROVIDER=llamacpp"
call :Prompt LLAMACPP_MODEL_PATH "  GGUF model path [LLM/gemma-4/gemma-4-E4B-it-UD-Q8_K_XL.gguf]: " "LLM/gemma-4/gemma-4-E4B-it-UD-Q8_K_XL.gguf"
call :Prompt LLAMACPP_N_CTX "  Context window [32768]: " "32768"
echo.
echo  LlamaCPP GPU layer profile:
echo    1. Auto / all supported layers ^(-1^)
echo    2. CPU only ^(0^)
echo    3. Custom layer count
echo.
if /I "%NVIDIA_AVAILABLE%"=="Y" (
    call :PromptChoice LLAMACPP_GPU_MODE "  Enter choice [1]: " "1" "1 2 3"
) else (
    call :PromptChoice LLAMACPP_GPU_MODE "  Enter choice [2]: " "2" "1 2 3"
)
if "%LLAMACPP_GPU_MODE%"=="1" set "LLAMACPP_N_GPU_LAYERS=-1"
if "%LLAMACPP_GPU_MODE%"=="2" set "LLAMACPP_N_GPU_LAYERS=0"
if "%LLAMACPP_GPU_MODE%"=="3" call :Prompt LLAMACPP_N_GPU_LAYERS "  Custom GPU layer count [20]: " "20"
echo  [INFO] If llama-cpp-python was installed without GPU support, edit the package install later even if GPU layers are enabled here.
exit /b

:ConfigureCustomPaths
call :Prompt SEARCH_DIR "  Search root [.]: " "."
call :Prompt DB_PATH "  SQLite DB path [data/zephyr.db]: " "data/zephyr.db"
call :Prompt VECTOR_STORE_DIR "  Vector store directory [data/vector_store]: " "data/vector_store"
call :Prompt EMBEDDING_MODEL_DIR "  Embedding model cache directory [LLM/vector-models]: " "LLM/vector-models"
exit /b

:ConfigureMcp
set "MCP_ENABLED=true"
set "EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED=true"
echo.
echo  MCP setup mode:
echo    1. Enable MCP only ^(add servers later^)
echo    2. One remote server via npx mcp-remote
echo    3. One remote server via uvx mcp-remote
echo    4. One custom stdio server
echo.
call :PromptChoice MCP_MODE "  Enter choice [1]: " "1" "1 2 3 4"
if "%MCP_MODE%"=="2" call :ConfigureMcpRemoteNpx
if "%MCP_MODE%"=="3" call :ConfigureMcpRemoteUvx
if "%MCP_MODE%"=="4" call :ConfigureMcpCustom
if not "%MCP_MODE%"=="1" call :ConfigureMcpAdvanced
exit /b

:ConfigureMcpRemoteNpx
if /I "%NPX_AVAILABLE%"=="N" echo  [WARNING] npx is not installed yet. The config will be saved, but the MCP bridge will not launch until Node.js is available.
call :Prompt MCP_SERVER_NAME "  MCP server name [archive]: " "archive"
call :Prompt MCP_TOOL_PREFIX "  Tool prefix [mcp]: " "mcp"
call :Prompt MCP_REMOTE_URL "  Remote MCP URL [https://your-mcp-server.example.com/mcp]: " "https://your-mcp-server.example.com/mcp"
set "MCP_SERVER_COMMAND=npx"
call set "MCP_SERVER_ARGS=-y mcp-remote %%MCP_REMOTE_URL%%"
exit /b

:ConfigureMcpRemoteUvx
if /I "%UVX_AVAILABLE%"=="N" echo  [WARNING] uvx is not installed yet. The config will be saved, but the MCP bridge will not launch until uvx is available.
call :Prompt MCP_SERVER_NAME "  MCP server name [archive]: " "archive"
call :Prompt MCP_TOOL_PREFIX "  Tool prefix [mcp]: " "mcp"
call :Prompt MCP_REMOTE_URL "  Remote MCP URL [https://your-mcp-server.example.com/mcp]: " "https://your-mcp-server.example.com/mcp"
set "MCP_SERVER_COMMAND=uvx"
call set "MCP_SERVER_ARGS=mcp-remote %%MCP_REMOTE_URL%%"
exit /b

:ConfigureMcpCustom
call :Prompt MCP_SERVER_NAME "  MCP server name [archive]: " "archive"
call :Prompt MCP_TOOL_PREFIX "  Tool prefix [mcp]: " "mcp"
call :Prompt MCP_SERVER_COMMAND "  MCP launch command [python]: " "python"
call :Prompt MCP_SERVER_ARGS "  MCP launch args [leave blank for none]: " ""
exit /b

:ConfigureMcpAdvanced
call :Prompt MCP_SERVER_ENV "  MCP env mapping ^(KEY=value;FOO=bar^) [optional]: " ""
call :Prompt MCP_SERVER_CWD "  MCP working directory [optional]: " ""
call :PromptYesNo MCP_ADVANCED_TIMEOUTS "  Tune MCP timeouts and retries now? (Y/N) [N]: " "N"
if /I "%MCP_ADVANCED_TIMEOUTS%"=="Y" (
    call :Prompt MCP_SERVER_CONNECT_TIMEOUT_SECONDS "  Connect timeout seconds [10]: " "10"
    call :Prompt MCP_SERVER_DISCOVERY_TIMEOUT_SECONDS "  Discovery timeout seconds [15]: " "15"
    call :Prompt MCP_SERVER_TOOL_TIMEOUT_SECONDS "  Tool timeout seconds [30]: " "30"
    call :Prompt MCP_SERVER_MAX_RETRIES "  Max retries [2]: " "2"
    call :Prompt MCP_SERVER_RETRY_BACKOFF_SECONDS "  Retry backoff seconds [0.5]: " "0.5"
)
exit /b

:WriteEnvFile
if exist "%ENV_TMP%" del /f /q "%ENV_TMP%" >nul 2>&1
type nul > "%ENV_TMP%"

call :WriteTextLine "# Zephyr runtime configuration"
call :WriteTextLine "# Generated by setup.bat"
call :WriteBlank
call :WriteTextLine "# Primary provider"
call :WriteTextLine "LLM_PROVIDER=%SELECTED_PROVIDER%"
if /I "%SELECTED_PROVIDER%"=="ollama" (
    call :WriteVarLine "OLLAMA_BASE_URL" "OLLAMA_BASE_URL"
    call :WriteVarLine "OLLAMA_MODEL" "OLLAMA_MODEL"
    call :WriteTextLine "# OPENROUTER_API_KEY=sk-or-your-key-here"
    call :WriteTextLine "# OPENROUTER_MODEL=openai/gpt-oss-120b:free"
    call :WriteTextLine "# LLAMACPP_MODEL_PATH=LLM/gemma-4/gemma-4-E4B-it-UD-Q8_K_XL.gguf"
    call :WriteTextLine "# LLAMACPP_N_CTX=32768"
    call :WriteTextLine "# LLAMACPP_N_GPU_LAYERS=-1"
    call :WriteTextLine "# LLAMACPP_CHAT_FORMAT="
)
if /I "%SELECTED_PROVIDER%"=="openrouter" (
    call :WriteVarLine "OPENROUTER_API_KEY" "OPENROUTER_API_KEY"
    call :WriteVarLine "OPENROUTER_MODEL" "OPENROUTER_MODEL"
    call :WriteTextLine "# OLLAMA_BASE_URL=http://localhost:11434"
    call :WriteTextLine "# OLLAMA_MODEL=llama3.1:8b"
    call :WriteTextLine "# LLAMACPP_MODEL_PATH=LLM/gemma-4/gemma-4-E4B-it-UD-Q8_K_XL.gguf"
    call :WriteTextLine "# LLAMACPP_N_CTX=32768"
    call :WriteTextLine "# LLAMACPP_N_GPU_LAYERS=-1"
    call :WriteTextLine "# LLAMACPP_CHAT_FORMAT="
)
if /I "%SELECTED_PROVIDER%"=="llamacpp" (
    call :WriteVarLine "LLAMACPP_MODEL_PATH" "LLAMACPP_MODEL_PATH"
    call :WriteVarLine "LLAMACPP_N_CTX" "LLAMACPP_N_CTX"
    call :WriteVarLine "LLAMACPP_N_GPU_LAYERS" "LLAMACPP_N_GPU_LAYERS"
    call :WriteTextLine "# LLAMACPP_CHAT_FORMAT="
    call :WriteTextLine "# OLLAMA_BASE_URL=http://localhost:11434"
    call :WriteTextLine "# OLLAMA_MODEL=llama3.1:8b"
    call :WriteTextLine "# OPENROUTER_API_KEY=sk-or-your-key-here"
    call :WriteTextLine "# OPENROUTER_MODEL=openai/gpt-oss-120b:free"
)

call :WriteBlank
call :WriteTextLine "# Runtime behavior"
call :WriteVarLine "EMBEDDING_MODEL_NAME" "EMBEDDING_MODEL_NAME"
call :WriteVarLine "REQUIRE_CONFIRMATION" "REQUIRE_CONFIRMATION"
call :WriteVarLine "SANDBOX_BACKEND" "SANDBOX_BACKEND"
call :WriteVarLine "SANDBOX_DOCKER_IMAGE" "SANDBOX_DOCKER_IMAGE"

call :WriteBlank
call :WriteTextLine "# Optional path overrides"
if /I "%CUSTOM_PATHS%"=="Y" (
    call :WriteVarLine "SEARCH_DIR" "SEARCH_DIR"
    call :WriteVarLine "DB_PATH" "DB_PATH"
    call :WriteVarLine "VECTOR_STORE_DIR" "VECTOR_STORE_DIR"
    call :WriteVarLine "EMBEDDING_MODEL_DIR" "EMBEDDING_MODEL_DIR"
) else (
    call :WriteTextLine "# SEARCH_DIR=."
    call :WriteTextLine "# DB_PATH=data/zephyr.db"
    call :WriteTextLine "# VECTOR_STORE_DIR=data/vector_store"
    call :WriteTextLine "# EMBEDDING_MODEL_DIR=LLM/vector-models"
)

call :WriteBlank
call :WriteTextLine "# MCP / external tooling"
call :WriteVarLine "MCP_ENABLED" "MCP_ENABLED"
call :WriteVarLine "EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED" "EXTERNAL_SUBPROCESS_INTEGRATIONS_ENABLED"
if /I "%MCP_ENABLED%"=="true" if defined MCP_SERVER_COMMAND (
    call :WriteVarLine "MCP_SERVER_NAME" "MCP_SERVER_NAME"
    call :WriteVarLine "MCP_SERVER_COMMAND" "MCP_SERVER_COMMAND"
    if defined MCP_SERVER_ARGS call :WriteVarLine "MCP_SERVER_ARGS" "MCP_SERVER_ARGS"
    if defined MCP_SERVER_ENV call :WriteVarLine "MCP_SERVER_ENV" "MCP_SERVER_ENV"
    if defined MCP_SERVER_CWD call :WriteVarLine "MCP_SERVER_CWD" "MCP_SERVER_CWD"
    call :WriteVarLine "MCP_TOOL_PREFIX" "MCP_TOOL_PREFIX"
    if defined MCP_SERVER_CONNECT_TIMEOUT_SECONDS call :WriteVarLine "MCP_SERVER_CONNECT_TIMEOUT_SECONDS" "MCP_SERVER_CONNECT_TIMEOUT_SECONDS"
    if defined MCP_SERVER_DISCOVERY_TIMEOUT_SECONDS call :WriteVarLine "MCP_SERVER_DISCOVERY_TIMEOUT_SECONDS" "MCP_SERVER_DISCOVERY_TIMEOUT_SECONDS"
    if defined MCP_SERVER_TOOL_TIMEOUT_SECONDS call :WriteVarLine "MCP_SERVER_TOOL_TIMEOUT_SECONDS" "MCP_SERVER_TOOL_TIMEOUT_SECONDS"
    if defined MCP_SERVER_MAX_RETRIES call :WriteVarLine "MCP_SERVER_MAX_RETRIES" "MCP_SERVER_MAX_RETRIES"
    if defined MCP_SERVER_RETRY_BACKOFF_SECONDS call :WriteVarLine "MCP_SERVER_RETRY_BACKOFF_SECONDS" "MCP_SERVER_RETRY_BACKOFF_SECONDS"
) else (
    call :WriteTextLine "# MCP_SERVER_NAME=archive"
    call :WriteTextLine "# MCP_SERVER_COMMAND=python"
    call :WriteTextLine "# MCP_SERVER_ARGS=-m archive_mcp"
    call :WriteTextLine "# MCP_SERVER_ENV=API_KEY=demo;WORKSPACE=local"
    call :WriteTextLine "# MCP_SERVER_CWD=./tools/archive"
    call :WriteTextLine "# MCP_TOOL_PREFIX=mcp"
)
call :WriteTextLine "# Multi-server setups can also use MCP_SERVERS_JSON or MCP_SERVER_1_* keys."

move /y "%ENV_TMP%" "%ENV_FILE%" >nul
exit /b

:WriteTextLine
setlocal DisableDelayedExpansion
set "WRITE_TEXT=%~1"
powershell -NoProfile -Command "Add-Content -LiteralPath $env:ENV_TMP -Value $env:WRITE_TEXT" >nul
endlocal
exit /b

:WriteVarLine
setlocal DisableDelayedExpansion
set "WRITE_KEY=%~1"
set "WRITE_VALUE="
call set "WRITE_VALUE=%%%~2%%"
powershell -NoProfile -Command "Add-Content -LiteralPath $env:ENV_TMP -Value ($env:WRITE_KEY + '=' + $env:WRITE_VALUE)" >nul
endlocal
exit /b

:WriteBlank
setlocal DisableDelayedExpansion
set "WRITE_TEXT="
powershell -NoProfile -Command "Add-Content -LiteralPath $env:ENV_TMP -Value $env:WRITE_TEXT" >nul
endlocal
exit /b

:EnsureDirectory
if not exist "%~1" mkdir "%~1" >nul 2>&1
exit /b

:EnsureDirectoryFromVar
setlocal DisableDelayedExpansion
set "TARGET="
call set "TARGET=%%%~1%%"
if defined TARGET if not exist "%TARGET%" mkdir "%TARGET%" >nul 2>&1
endlocal
exit /b

:EnsureParentFromVar
setlocal DisableDelayedExpansion
set "TARGET="
call set "TARGET=%%%~1%%"
if defined TARGET for %%I in ("%TARGET%") do if not exist "%%~dpI" mkdir "%%~dpI" >nul 2>&1
endlocal
exit /b

:AbortSetup
echo.
echo  [ERROR] %~1
echo.
pause
popd >nul 2>&1
endlocal
exit /b 1

:script_end
popd >nul 2>&1
endlocal
exit /b 0
