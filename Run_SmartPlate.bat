@echo off
title SmartPlate - Web Application Launcher
color 0A
echo =================================================================
echo   PCCOE SmartPlate: Campus Canteen Sustainability System
echo =================================================================
echo.
echo Starting SmartPlate application...
cd /d "%~dp0"
python run_with_browser.py
if errorlevel 1 (
    echo.
    echo Server stopped with error. Make sure Python and Flask are installed.
    pause
)
