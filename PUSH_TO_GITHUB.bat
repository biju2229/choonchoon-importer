@echo off
title Push Cloud Importer to GitHub
color 0a
echo ================================================================
echo    ChoonChoon - Telegram Cloud Importer (GitHub Setup)
echo ================================================================
echo.
set /p REPO_URL="Enter your GitHub Repository URL (e.g. https://github.com/yourname/choonchoon-importer.git): "
if "%REPO_URL%"=="" (
    echo [Error] Repository URL cannot be empty!
    pause
    exit /b
)

echo.
echo Initializing Git repository...
cd /d "%~dp0"
git init
git add .
git commit -m "ChoonChoon 24x7 Telegram Cloud Importer"
git branch -M main
git remote remove origin 2>nul
git remote add origin %REPO_URL%
git push -u origin main --force

echo.
echo ================================================================
echo  Code uploaded to GitHub successfully!
echo ================================================================
pause
