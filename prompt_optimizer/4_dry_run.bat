@echo off
echo ============================================
echo   Prompt Optimizer - Test de Configuration
echo ============================================
echo.

REM Se placer dans le repertoire racine du projet
cd /d "%~dp0\.."

echo Verification de la configuration sans execution...
echo.

python -m prompt_optimizer.optimize --config prompt_optimizer/prompt_optimizer_config.yaml --dry-run

echo.
if errorlevel 1 (
    echo [ERREUR] La configuration est invalide
) else (
    echo ============================================
    echo   Configuration valide!
    echo   Vous pouvez lancer l'optimisation.
    echo ============================================
)
echo.
pause
