@echo off
REM ============================================
REM TranslateBookWithLLM - Smart Launcher
REM Installation + Update + Launch All-in-One
REM ============================================

setlocal enabledelayedexpansion

echo.
echo ============================================
echo TranslateBookWithLLM - Smart Launcher
echo ============================================
echo.

REM ========================================
REM STEP 1: Check Python Installation
REM ========================================
echo [1/7] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo.
    echo Please install Python 3.8+ from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] Python %PYTHON_VERSION% detected
echo.

REM ========================================
REM STEP 2: Virtual Environment Setup
REM ========================================
echo [2/7] Checking virtual environment...
if not exist "venv" (
    echo [INFO] First-time setup detected - creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
    set FIRST_INSTALL=1
) else (
    echo [OK] Virtual environment exists
    set FIRST_INSTALL=0
)
echo.

REM ========================================
REM STEP 3: Activate Virtual Environment
REM ========================================
echo [3/7] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)
echo [OK] Virtual environment activated
echo.

REM ========================================
REM STEP 4: Check for Updates
REM ========================================
echo [4/7] Checking for updates...

REM Check if git is available and update
git --version >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Checking for code updates from Git...
    git fetch >nul 2>&1

    for /f %%i in ('git rev-parse HEAD') do set LOCAL_COMMIT=%%i
    for /f %%i in ('git rev-parse @{u} 2^>nul') do set REMOTE_COMMIT=%%i

    if not "!LOCAL_COMMIT!"=="!REMOTE_COMMIT!" (
        if not "!REMOTE_COMMIT!"=="" (
            echo [INFO] Updates available! Pulling latest changes...
            git pull
            set NEEDS_UPDATE=1
        )
    ) else (
        echo [OK] Code is up to date
    )
) else (
    echo [INFO] Git not available, skipping code update check
)

REM Check if requirements changed or first install
REM Initialize NEEDS_UPDATE to 0 by default
set NEEDS_UPDATE=0

if !FIRST_INSTALL!==1 (
    set NEEDS_UPDATE=1
    echo [INFO] First installation - will install all dependencies
) else (
    if exist "venv\.requirements_hash" (
        REM Compare requirements.txt hash
        for /f "delims=" %%i in ('certutil -hashfile requirements.txt MD5 ^| find /v "hash"') do set NEW_HASH=%%i
        set /p OLD_HASH=<venv\.requirements_hash
        if not "!NEW_HASH!"=="!OLD_HASH!" (
            echo [INFO] Dependencies changed - updating packages...
            set NEEDS_UPDATE=1
        )
    ) else (
        echo [INFO] No hash found - will update dependencies
        set NEEDS_UPDATE=1
    )
)
echo.

REM ========================================
REM STEP 5: Install/Update Dependencies
REM ========================================
echo [5/7] Managing dependencies...
echo [DEBUG] NEEDS_UPDATE=%NEEDS_UPDATE%

if "!NEEDS_UPDATE!"=="1" (
    echo [INFO] Upgrading pip...
    python -m pip install --upgrade pip --quiet

    echo [INFO] Installing/updating dependencies from requirements.txt...
    pip install -r requirements.txt --upgrade
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        echo [ERROR] Please check your internet connection and try again
        pause
        exit /b 1
    )

    REM Save requirements hash
    for /f "delims=" %%i in ('certutil -hashfile requirements.txt MD5 ^| find /v "hash"') do echo %%i>venv\.requirements_hash

    echo [OK] Dependencies updated successfully
) else (
    echo [OK] Dependencies are up to date (NEEDS_UPDATE=0)
    echo [INFO] If you suspect missing packages, delete venv\.requirements_hash and rerun
)
echo.

REM ========================================
REM STEP 6: Environment Setup
REM ========================================
echo [6/7] Checking environment configuration...

REM Create .env if missing
if not exist ".env" (
    if exist ".env.example" (
        echo [INFO] Creating .env from template...
        copy .env.example .env >nul
        echo [OK] .env file created
        echo [WARNING] Please edit .env to configure your LLM settings
        echo.
        notepad .env
    ) else (
        echo [WARNING] .env.example not found, skipping .env creation
    )
) else (
    echo [OK] .env configuration exists
)

REM Create output directory
if not exist "translated_files" (
    mkdir translated_files
    echo [INFO] Created output directory: translated_files
)
echo.

REM ========================================
REM STEP 7: Quick Integrity Check (Silent)
REM ========================================
if exist "fix_installation.py" (
    python fix_installation.py >nul 2>&1
)

REM ========================================
REM LAUNCH APPLICATION
REM ========================================
echo ============================================
echo Setup Complete! Starting Application...
echo ============================================
echo.
echo Web interface will be available at:
echo http://localhost:5000
echo.
echo The browser will open automatically in a few seconds.
echo Please wait...
echo.
echo Press Ctrl+C to stop the server
echo ============================================
echo.

REM Start the Flask application (browser auto-opens from Python code)
python translation_api.py

REM If server stops
echo.
echo ============================================
echo Server stopped
echo ============================================
pause
