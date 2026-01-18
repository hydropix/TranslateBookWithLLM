@echo off
REM ============================================
REM TranslateBookWithLLM - Start Application
REM Quick Launch Script
REM ============================================

echo.
echo ============================================
echo TranslateBookWithLLM - Launcher
echo ============================================
echo.

REM ========================================
REM Check if setup was run
REM ========================================
if not exist "venv" (
    echo [ERROR] Virtual environment not found!
    echo.
    echo Please run setup.bat first to install the application.
    echo.
    pause
    exit /b 1
)

REM ========================================
REM Activate Virtual Environment
REM ========================================
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    echo [ERROR] Try running setup.bat to fix the installation
    pause
    exit /b 1
)
echo [OK] Environment ready
echo.

REM ========================================
REM LAUNCH APPLICATION
REM ========================================
echo ============================================
echo Starting Application...
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
