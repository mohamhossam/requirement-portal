@echo off
setlocal enabledelayedexpansion
pip config set global.index-url https://au00447.etisalat.corp.ae:8443/repository/pi-py/simple/
pip config set global.trusted-host au00447.etisalat.corp.ae
python -m pip config set global.timeout 60
:: ==============================================================================
:: Configuration and Defaults
:: ==============================================================================
set "PROVIDER=fake"
set "PROFILE_CHECK_ARGS="
set "SETUP=0"
set "CHECKONLY=0"
set "DEBUGTRACE=0"
set "MIGRATE=0"

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

set "FRONTEND_ROOT=%PROJECT_ROOT%\frontend"
set "VIRTUAL_ENVIRONMENT=%PROJECT_ROOT%\.venv"
set "LOGS_ROOT=%PROJECT_ROOT%\logs"
set "COMPOSE_PATH=%PROJECT_ROOT%\compose.yaml"
set "DEBUG_TRACE_FILE=%LOGS_ROOT%\debug.log"

:: ==============================================================================
:: Argument Parsing
:: ==============================================================================
:parse_args
if "%~1"=="" goto end_parse_args
set "PARAM=%~1"

if /i "%PARAM%"=="-Provider" (
    set "PROVIDER=%~2"
    set "PROFILE_CHECK_ARGS=--explicit-provider %~2"
    shift & shift
    goto parse_args
)
if /i "%PARAM%"=="-Setup" (
    set "SETUP=1"
    shift
    goto parse_args
)
if /i "%PARAM%"=="-CheckOnly" (
    set "CHECKONLY=1"
    shift
    goto parse_args
)
if /i "%PARAM%"=="-Migrate" (
    set "MIGRATE=1"
    shift
    goto parse_args
)
if /i "%PARAM%"=="-DebugTrace" (
    set "DEBUGTRACE=1"
    shift
    goto parse_args
)
if /i "%PARAM%"=="/Setup" ( set "SETUP=1" & shift & goto parse_args )
if /i "%PARAM%"=="/CheckOnly" ( set "CHECKONLY=1" & shift & goto parse_args )
if /i "%PARAM%"=="/DebugTrace" ( set "DEBUGTRACE=1" & shift & goto parse_args )

echo Unknown argument: %PARAM%
exit /b 1
:end_parse_args

:: Validate Provider
if /i not "%PROVIDER%"=="fake" if /i not "%PROVIDER%"=="local" if /i not "%PROVIDER%"=="openai" if /i not "%PROVIDER%"=="openrouter" (
    echo [ERROR] Invalid provider matching "-Provider". Choose 'fake', 'local', 'openai', or 'openrouter'.
    exit /b 1
)

:: ==============================================================================
:: Main Pipeline Logic
:: ==============================================================================
pushd "%PROJECT_ROOT%"

:: Step 1: Handle Setup and Virtual Environment Detection
if "%SETUP%"=="1" (
    call :ResolveVenvPython
    if "!PYTHON_PATH!"=="" (
        call :NewVirtualEnvironment
    )
)

call :ResolveVenvPython
if "!PYTHON_PATH!"=="" (
    echo [ERROR] The .venv environment is missing. Run "start.cmd -Setup" first.
    popd & exit /b 1
)

:: Step 2: Handle Frontend Tools Detection
call :ResolveNodeTools
if "!NODE_PATH!"=="" (
    echo [ERROR] Node.js 22 and npm were not found. Install Node.js 22, then rerun.
    popd & exit /b 1
)

:: Step 3: Setup Installations
if "%SETUP%"=="1" (
    call :WriteStep "Installing backend dependencies..."
    "%PYTHON_PATH%" -m pip install -e ".[dev]"
    if errorlevel 1 ( echo [ERROR] Backend dependency installation failed. & popd & exit /b 1 )

    call :WriteStep "Installing locked frontend dependencies..."
    pushd "%FRONTEND_ROOT%"
    call "%NPM_PATH%" ci
    if errorlevel 1 ( echo [ERROR] Frontend dependency installation failed. & popd & exit /b 1 )
    popd
)

:: Step 4: Verify frontend dependencies are installed
set "VITE_SCRIPT=%FRONTEND_ROOT%\node_modules\vite\bin\vite.js"
if not exist "%VITE_SCRIPT%" (
    echo [ERROR] Frontend dependencies are missing. Run "start.cmd -Setup" first.
    popd & exit /b 1
)

:: Step 5: Configure environment and validate settings
set "LLM_PROVIDER=%PROVIDER%"
if "%DEBUGTRACE%"=="1" (
    set "DEBUG_TRACE_ENABLED=true"
    set "DEBUG_TRACE_PATH=%DEBUG_TRACE_FILE%"
)
call :WriteStep "Validating model configuration..."
"%PYTHON_PATH%" -m smb_requirement_agent.interfaces.cli.llm check %PROFILE_CHECK_ARGS%
if errorlevel 1 ( echo [ERROR] Application configuration validation failed. & popd & exit /b 1 )

:: Step 6: Detect the persistence target
set "PERSISTENCE_TARGET="
for /f "usebackq delims=" %%T in (`"%PYTHON_PATH%" -m smb_requirement_agent.infrastructure.persistence.startup_check --target`) do set "PERSISTENCE_TARGET=%%T"
if "%PERSISTENCE_TARGET%"=="" ( echo [ERROR] Persistence target detection failed. & popd & exit /b 1 )

if "%CHECKONLY%"=="1" (
    call :WriteStep "Checking persistence readiness..."
    "%PYTHON_PATH%" -m smb_requirement_agent.infrastructure.persistence.startup_check
    if errorlevel 1 ( popd & exit /b 1 )
    call :WriteStep "Startup prerequisites and configuration are valid."
    popd & exit /b 0
)

:: Step 7: Fail fast when the fixed API or UI port is already taken
call :WriteStep "Checking local API and UI ports..."
"%PYTHON_PATH%" "%PROJECT_ROOT%\scripts\check_ports.py" --port "API=8000" --port "Review UI=5173"
if errorlevel 1 ( popd & exit /b 1 )

:: Step 8: Make sure PostgreSQL is reachable when the app needs it
if /i "%PERSISTENCE_TARGET%"=="local-postgres" (
    "%PYTHON_PATH%" -m smb_requirement_agent.infrastructure.persistence.startup_check --quiet
    if errorlevel 1 (
        call :ResolveCommandPath "docker.exe"
        if "!FOUND_PATH!"=="" (
            echo [ERROR] Local PostgreSQL is not ready and Docker was not found. Install/start Docker Desktop, or set PERSISTENCE_PROVIDER=memory.
            popd & exit /b 1
        )
        call :WriteStep "Starting local PostgreSQL with Docker Compose..."
        "!FOUND_PATH!" compose --file "%COMPOSE_PATH%" up --detach postgres
        if errorlevel 1 ( echo [ERROR] PostgreSQL Compose startup failed. & popd & exit /b 1 )
        call :WriteStep "Waiting for PostgreSQL to become ready..."
        call :WaitForPersistence
        if errorlevel 1 ( popd & exit /b 1 )
    )
) else if /i "%PERSISTENCE_TARGET%"=="external-postgres" (
    call :WriteStep "Checking external PostgreSQL readiness..."
    "%PYTHON_PATH%" -m smb_requirement_agent.infrastructure.persistence.startup_check
    if errorlevel 1 ( popd & exit /b 1 )
    if not "%MIGRATE%"=="1" (
        echo [ERROR] DATABASE_URL names an external PostgreSQL. Rerun with -Migrate to apply pending migrations to it.
        popd & exit /b 1
    )
)

:: Step 9: Apply pending database migrations
if /i not "%PERSISTENCE_TARGET%"=="memory" (
    call :WriteStep "Applying pending database migrations..."
    "%PYTHON_PATH%" -m smb_requirement_agent.infrastructure.persistence.migrate
    if errorlevel 1 ( echo [ERROR] Database migration failed. & popd & exit /b 1 )
)

:: Step 10: Start the API in its own window and wait for its health check
set "WAIT_FOR_URL=%PROJECT_ROOT%\scripts\wait_for_url.py"
call :WriteStep "Starting API on http://127.0.0.1:8000..."
start "SMB Requirement Agent API" /D "%PROJECT_ROOT%" cmd /k ""%PYTHON_PATH%" -m uvicorn smb_requirement_agent.interfaces.api.main:app --host 127.0.0.1 --port 8000"
"%PYTHON_PATH%" "%WAIT_FOR_URL%" --name "API" --url "http://127.0.0.1:8000/health" --timeout 30
if errorlevel 1 ( popd & exit /b 1 )

:: Step 11: Start the review UI in its own window and wait for it to be ready
call :WriteStep "Starting review UI on http://127.0.0.1:5173..."
start "SMB Requirement Agent UI" /D "%FRONTEND_ROOT%" cmd /k ""%NODE_PATH%" "%VITE_SCRIPT%" --host 127.0.0.1 --port 5173"
"%PYTHON_PATH%" "%WAIT_FOR_URL%" --name "Review UI" --url "http://127.0.0.1:5173" --timeout 30
if errorlevel 1 ( popd & exit /b 1 )

echo.
echo Application ready
echo   Review UI:  http://127.0.0.1:5173
echo   API docs:   http://127.0.0.1:8000/docs
echo   Health:     http://127.0.0.1:8000/health
echo   Provider:   %PROVIDER%
set "KNOWLEDGE_TARGET=unknown"
for /f "usebackq delims=" %%T in (`"%PYTHON_PATH%" -m smb_requirement_agent.interfaces.knowledge_target`) do set "KNOWLEDGE_TARGET=%%T"
echo   Knowledge:  %KNOWLEDGE_TARGET%
if "%DEBUGTRACE%"=="1" (
    echo   Debug trace: %DEBUG_TRACE_FILE%
    echo   WARNING: includes requirement text and final LLM completions.
)
echo.
echo The API and review UI are running in separate Command Prompt windows.
echo Close both windows, or press Ctrl+C in each, to stop the application.

popd
exit /b 0

:: ==============================================================================
:: Functions Definitions
:: ==============================================================================

:WriteStep
echo ^[startup^] %~1
goto :eof

:ResolveCommandPath
:: %1 = executable name (e.g. node.exe)
:: Returns %FOUND_PATH%
set "FOUND_PATH="
for %%I in (%~1) do set "FOUND_PATH=%%~$PATH:I"
goto :eof

:ResolveVenvPython
set "PYTHON_PATH="
:: Check both .venv and .venv-uv folder profiles
for %%E in ("%VIRTUAL_ENVIRONMENT%" "%PROJECT_ROOT%\.venv-uv") do (
    for %%P in ("%%~E\Scripts\python.exe" "%%~E\bin\python.exe") do (
        if exist "%%~P" (
            "%%~P" -c "import sys; raise SystemExit(0)" >nul 2>&1
            if !errorlevel! equ 0 (
                set "PYTHON_PATH=%%~P"
                goto :eof
            )
        )
    )
)
goto :eof

:NewVirtualEnvironment
:: Check for Python Launcher
call :ResolveCommandPath "py.exe"
if not "!FOUND_PATH!"=="" (
    call :WriteStep "Creating Python 3.12 virtual environment..."
    rem if below command giving error, try <your_python_3.12_path> -m venv "%VIRTUAL_ENVIRONMENT%"
    "%FOUND_PATH%" -3.12 -m venv "%VIRTUAL_ENVIRONMENT%"
    if errorlevel 1 (
        echo [ERROR] Python failed to create .venv. Confirm Python 3.12 is installed.
        exit /b 1
    )
    goto :eof
)
:: Fallback to systemic configurations
for %%N in (python3.12.exe python.exe) do (
    call :ResolveCommandPath "%%N"
    if not "!FOUND_PATH!"=="" (
        call :WriteStep "Creating Python virtual environment..."
        rem if below command giving error, try <your_python_3.12_path> -m venv "%VIRTUAL_ENVIRONMENT%"
        "!FOUND_PATH!" -m venv "%VIRTUAL_ENVIRONMENT%"
        if errorlevel 1 (
            echo [ERROR] Python failed to create .venv. Confirm Python 3.12 or newer is installed.
            exit /b 1
        )
        goto :eof
    )
)
echo [ERROR] Python 3.12 was not found. Install it, then run "start.cmd -Setup" again.
exit /b 1

:ResolveNodeTools
set "NODE_PATH="
set "NPM_PATH="

call :ResolveCommandPath "node.exe"
if not "!FOUND_PATH!"=="" set "NODE_PATH=!FOUND_PATH!"

call :ResolveCommandPath "npm.cmd"
if not "!FOUND_PATH!"=="" set "NPM_PATH=!FOUND_PATH!"

:: Check portable folder fallback if native path lookup misses
if "!NODE_PATH!"=="" (
    if exist "%PROJECT_ROOT%\.tools" (
        for /r "%PROJECT_ROOT%\.tools" %%F in (node.exe) do (
            if exist "%%F" (
                set "NODE_PATH=%%F"
                set "NPM_PATH=%%~dpFnpm.cmd"
                goto :eof
            )
        )
    )
)
goto :eof

:: ==============================================================================
:: Persistence Readiness Polling
:: ==============================================================================

:WaitForPersistence
set "PERSISTENCE_ATTEMPT=0"
:WaitForPersistenceLoop
"%PYTHON_PATH%" -m smb_requirement_agent.infrastructure.persistence.startup_check --quiet
if not errorlevel 1 goto :eof
set /a PERSISTENCE_ATTEMPT+=1
if %PERSISTENCE_ATTEMPT% geq 30 (
    "%PYTHON_PATH%" -m smb_requirement_agent.infrastructure.persistence.startup_check
    echo [ERROR] PostgreSQL did not become ready within 30 seconds.
    exit /b 1
)
:: Roughly a 1-second pause per attempt; ping has no native sleep-only mode.
ping -n 2 127.0.0.1 >nul
goto :WaitForPersistenceLoop
