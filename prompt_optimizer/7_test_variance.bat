@echo off
echo ============================================
echo   Test de Variance - Meme prompt, meme texte
echo ============================================
echo.

cd /d "%~dp0\.."

python -m prompt_optimizer.test_variance --config prompt_optimizer/prompt_optimizer_config.yaml --runs 5

echo.
pause
