@echo off
echo ============================================
echo   Prompt Optimizer - Ouvrir Meilleur Prompt
echo ============================================
echo.

REM Se placer dans le repertoire racine du projet
cd /d "%~dp0\.."

set BEST_PROMPT=prompt_optimization_results\best_prompts\prompt_01.yaml

if not exist "%BEST_PROMPT%" (
    echo [ERREUR] Aucun meilleur prompt trouve
    echo Fichier attendu: %BEST_PROMPT%
    echo.
    echo Lancez d'abord une optimisation avec 3_run_optimization.bat
    echo.
    pause
    exit /b 1
)

echo Ouverture de: %BEST_PROMPT%
echo.

REM Essayer d'ouvrir avec l'editeur par defaut
start "" "%BEST_PROMPT%"

echo Le fichier devrait s'ouvrir dans votre editeur par defaut.
echo.
pause
