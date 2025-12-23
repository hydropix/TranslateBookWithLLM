@echo off
echo ============================================
echo   Prompt Optimizer - Verification Prerequis
echo ============================================
echo.

REM Verifier Python
echo [1/3] Verification de Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo   [ERREUR] Python n'est pas installe ou pas dans le PATH
    goto :error
) else (
    python --version
    echo   [OK] Python trouve
)
echo.

REM Verifier les dependances Python
echo [2/3] Verification des dependances Python...
python -c "import yaml" >nul 2>&1
if errorlevel 1 (
    echo   [MANQUANT] pyyaml - Installation: pip install pyyaml
    set MISSING_DEPS=1
) else (
    echo   [OK] pyyaml
)

python -c "import dotenv" >nul 2>&1
if errorlevel 1 (
    echo   [MANQUANT] python-dotenv - Installation: pip install python-dotenv
    set MISSING_DEPS=1
) else (
    echo   [OK] python-dotenv
)

python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo   [MANQUANT] requests - Installation: pip install requests
    set MISSING_DEPS=1
) else (
    echo   [OK] requests
)
echo.

REM Verifier le fichier .env
echo [3/3] Verification du fichier .env...
if exist "..\..\.env" (
    echo   [OK] .env trouve
) else (
    if exist "..\.env" (
        echo   [OK] .env trouve
    ) else (
        echo   [ERREUR] .env non trouve - Creez-le a la racine du projet
        goto :error
    )
)
echo.

if defined MISSING_DEPS (
    echo ============================================
    echo   Des dependances sont manquantes!
    echo   Executez: pip install pyyaml python-dotenv requests
    echo ============================================
) else (
    echo ============================================
    echo   Tous les prerequis sont satisfaits!
    echo   Vous pouvez lancer l'optimisation.
    echo ============================================
)
echo.
pause
exit /b 0

:error
echo.
echo Corrigez les erreurs ci-dessus avant de continuer.
pause
exit /b 1
