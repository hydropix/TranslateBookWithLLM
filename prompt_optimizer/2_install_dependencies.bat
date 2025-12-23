@echo off
echo ============================================
echo   Prompt Optimizer - Installation Dependances
echo ============================================
echo.

echo Installation des packages Python necessaires...
echo.

pip install pyyaml python-dotenv requests

echo.
if errorlevel 1 (
    echo [ERREUR] L'installation a echoue
    pause
    exit /b 1
) else (
    echo ============================================
    echo   Installation terminee avec succes!
    echo ============================================
)
echo.
pause
