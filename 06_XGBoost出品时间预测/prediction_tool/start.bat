@echo off
chcp 65001 >nul
title Prediction Tool

echo ========================================
echo   Cha Yin Prediction Tool
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    pause
    exit /b 1
)

echo [1/2] Installing dependencies...
pip install -r requirements.txt -q 2>nul

echo [2/2] Starting server...
echo.
echo   Open: http://localhost:5000
echo   Press Ctrl+C to stop
echo.
python app.py
pause
