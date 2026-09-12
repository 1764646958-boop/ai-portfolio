@echo off
chcp 65001 >nul
title Chengchu AI Guide v2 Demo
cd /d "%~dp0"

rem ---- pick python: prefer this folder's .venv, else sibling .venv ----
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%~dp0..\fde-08-daogou\.venv\Scripts\python.exe"

set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

echo ============================================================
echo   Chengchu AI Guide  v2  -  Q08 demo
echo   Starting FastAPI on port 8000 ...
echo   Press Ctrl+C to stop the uvicorn server when done.
echo ============================================================

start "chengchu-uvicorn" "%PY%" -m uvicorn server:app --host 0.0.0.0 --port 8000

echo.
echo Waiting a few seconds for uvicorn to boot ...
timeout /t 6 /nobreak >nul

echo Starting cloudflared quick tunnel ...
echo The public HTTPS URL will appear below (copy it to share).
echo.
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://127.0.0.1:8000 --no-autoupdate

pause
