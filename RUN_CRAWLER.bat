@echo off
title SEG301 Focused Web Crawler
cd /d "%~dp0"

echo ==============================================
echo      SEG301 FOCUSED WEB CRAWLER
echo ==============================================
echo.

python -m pip install -r requirements.txt

echo.
echo Starting crawler...
echo.

python main.py

echo.
echo ==============================================
echo Output database:
echo %CD%\data\crawler.db
echo ==============================================
echo.
pause
