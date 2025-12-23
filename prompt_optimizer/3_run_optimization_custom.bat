@echo off
echo ============================================
echo   Prompt Optimizer - Optimisation Personnalisee
echo ============================================
echo.

REM Se placer dans le repertoire racine du projet
cd /d "%~dp0\.."

REM Parametres par defaut
set ITERATIONS=10
set POPULATION=5

REM Demander les parametres
echo Parametres actuels:
echo   - Iterations: %ITERATIONS%
echo   - Population: %POPULATION%
echo.

set /p ITERATIONS="Nombre d'iterations [%ITERATIONS%]: "
set /p POPULATION="Taille de la population [%POPULATION%]: "

echo.
echo Configuration:
echo   - Iterations: %ITERATIONS%
echo   - Population: %POPULATION%
echo.

set /p CONFIRM="Lancer l'optimisation? (O/N): "
if /i not "%CONFIRM%"=="O" (
    echo Annule.
    pause
    exit /b 0
)

echo.
echo Demarrage de l'optimisation...
echo.

python -m prompt_optimizer.optimize ^
    --config prompt_optimizer/prompt_optimizer_config.yaml ^
    --iterations %ITERATIONS% ^
    --population %POPULATION% ^
    --verbose

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
