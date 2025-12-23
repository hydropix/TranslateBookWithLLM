@echo off
echo ============================================
echo   Prompt Optimizer - Lancement Optimisation
echo ============================================
echo.

REM Se placer dans le repertoire racine du projet
cd /d "%~dp0\.."

echo Repertoire de travail: %CD%
echo Configuration: prompt_optimizer/prompt_optimizer_config.yaml
echo.

echo Demarrage de l'optimisation...
echo (Cela peut prendre plusieurs minutes selon le nombre d'iterations)
echo.

python -m prompt_optimizer.optimize --config prompt_optimizer/prompt_optimizer_config.yaml --verbose

echo.
if errorlevel 1 (
    echo [ERREUR] L'optimisation a echoue
) else (
    echo ============================================
    echo   Optimisation terminee!
    echo   Resultats dans: prompt_optimization_results/
    echo ============================================
)
echo.
pause
