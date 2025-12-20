@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM Test simple du benchmark - traduction Ollama uniquement (sans evaluation)

echo ============================================
echo Test du systeme de benchmark
echo ============================================
echo.

cd /d "%~dp0.."

REM Test 1: Verification des imports
echo [TEST 1] Verification des imports...
python -c "from benchmark.cli import main; print('OK')"
if errorlevel 1 (
    echo ECHEC - Erreur d import
    pause
    exit /b 1
)
echo.

REM Test 2: Chargement des langues et textes
echo [TEST 2] Chargement des donnees...
python -c "from benchmark.runner import BenchmarkRunner; from benchmark.config import BenchmarkConfig; r = BenchmarkRunner(BenchmarkConfig()); r.load_languages(); r.load_reference_texts(); print('OK')"
if errorlevel 1 (
    echo ECHEC
    pause
    exit /b 1
)
echo.

REM Test 3: Test connexion Ollama
echo [TEST 3] Test connexion Ollama...
python test_ollama_only.py
if errorlevel 1 (
    echo ECHEC - Voir erreur ci-dessus
    pause
    exit /b 1
)
echo.

echo ============================================
echo Tests termines avec succes
echo ============================================
pause
