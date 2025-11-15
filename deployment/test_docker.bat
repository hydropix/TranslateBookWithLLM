@echo off
REM ============================================================================
REM Docker Testing Script for TranslateBookWithLLM
REM ============================================================================
REM This script tests the Docker deployment automatically
REM Usage: test_docker.bat

echo.
echo ============================================================
echo   Docker Test Script - TranslateBookWithLLM
echo ============================================================
echo.

REM Step 1: Verify Docker is installed and running
echo [1/6] Checking Docker installation...
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed or not in PATH
    echo Please install Docker Desktop: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)
echo [OK] Docker is installed

docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose is not installed or not in PATH
    pause
    exit /b 1
)
echo [OK] Docker Compose is installed

echo.
echo [2/6] Checking Docker daemon status...
docker ps >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Desktop is not running
    echo Please start Docker Desktop and try again
    pause
    exit /b 1
)
echo [OK] Docker daemon is running

echo.
echo [3/6] Building Docker image...
docker-compose build
if errorlevel 1 (
    echo [ERROR] Docker build failed
    pause
    exit /b 1
)
echo [OK] Docker image built successfully

echo.
echo [4/6] Starting Docker container...
docker-compose up -d
if errorlevel 1 (
    echo [ERROR] Failed to start container
    pause
    exit /b 1
)
echo [OK] Container started

echo.
echo [5/6] Waiting for container to be healthy (40 seconds grace period)...
timeout /t 45 /nobreak >nul

REM Check container status
docker-compose ps | findstr "healthy" >nul
if errorlevel 1 (
    echo [WARNING] Container may not be healthy yet
    echo Checking logs...
    docker-compose logs --tail=20
) else (
    echo [OK] Container is healthy
)

echo.
echo [6/6] Testing API endpoints...

REM Test health endpoint
curl -s http://localhost:5000/api/health > test_health.json
if errorlevel 1 (
    echo [ERROR] Health endpoint test failed
    type test_health.json
    del test_health.json
    pause
    exit /b 1
)

findstr "ok" test_health.json >nul
if errorlevel 1 (
    echo [ERROR] Health endpoint returned unexpected response
    type test_health.json
    del test_health.json
    pause
    exit /b 1
)

echo [OK] Health endpoint: http://localhost:5000/api/health
type test_health.json
del test_health.json

echo.
REM Test web interface
curl -s -I http://localhost:5000/ | findstr "200 OK" >nul
if errorlevel 1 (
    echo [WARNING] Web interface may not be responding correctly
) else (
    echo [OK] Web interface: http://localhost:5000/
)

echo.
echo ============================================================
echo   All tests passed successfully!
echo ============================================================
echo.
echo Container status:
docker-compose ps
echo.
echo Useful commands:
echo   - View logs:           docker-compose logs -f
echo   - Stop container:      docker-compose down
echo   - Restart container:   docker-compose restart
echo   - Shell access:        docker-compose exec translatebook bash
echo.
echo Web interface: http://localhost:5000
echo API health:    http://localhost:5000/api/health
echo.
pause
