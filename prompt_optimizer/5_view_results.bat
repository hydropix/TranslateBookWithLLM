@echo off
echo ============================================
echo   Prompt Optimizer - Consultation Resultats
echo ============================================
echo.

REM Se placer dans le repertoire racine du projet
cd /d "%~dp0\.."

set RESULTS_DIR=prompt_optimization_results

if not exist "%RESULTS_DIR%" (
    echo [ERREUR] Aucun resultat trouve dans %RESULTS_DIR%
    echo Lancez d'abord une optimisation avec 3_run_optimization.bat
    echo.
    pause
    exit /b 1
)

echo Repertoire des resultats: %RESULTS_DIR%
echo.

echo === Fichiers disponibles ===
dir /b "%RESULTS_DIR%"
echo.

if exist "%RESULTS_DIR%\final_report.json" (
    echo === Rapport Final ===
    echo.
    type "%RESULTS_DIR%\final_report.json"
    echo.
)

if exist "%RESULTS_DIR%\best_prompts" (
    echo.
    echo === Meilleurs Prompts ===
    dir /b "%RESULTS_DIR%\best_prompts"
    echo.
    echo Pour voir le meilleur prompt:
    echo   type "%RESULTS_DIR%\best_prompts\prompt_01.yaml"
)

echo.
pause
