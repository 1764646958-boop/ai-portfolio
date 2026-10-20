@echo off
setlocal
cd /d "%~dp0"
title kwkagent Launcher

 echo ========================================
 echo           Starting kwkagent
 echo ========================================
 echo.

if not exist ".env" (
    echo [ERROR] .env was not found.
    echo Create and configure .env before starting the project.
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo [ERROR] Frontend dependencies are missing.
    echo Run: cd frontend ^&^& npm ci
    pause
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Desktop is not running.
    echo Start Docker Desktop and run this script again.
    pause
    exit /b 1
)

echo [1/3] Starting PostgreSQL, Redis, etcd, MinIO, Milvus and Attu...
docker compose up -d --wait postgres redis etcd minio standalone attu
if errorlevel 1 (
    echo [ERROR] Docker infrastructure failed to start.
    pause
    exit /b 1
)

powershell.exe -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    echo [2/3] Opening backend window...
    start "kwkagent Backend" /D "%~dp0" cmd.exe /k uv run uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
) else (
    echo [2/3] Backend is already running on port 8000.
)

echo Waiting for backend readiness...
powershell.exe -NoProfile -Command "$deadline = (Get-Date).AddSeconds(120); while ((Get-Date) -lt $deadline) { try { $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/docs' -TimeoutSec 2; if ($response.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Seconds 1 }; exit 1"
if errorlevel 1 (
    echo [ERROR] Backend did not become ready within 120 seconds.
    echo Check the kwkagent Backend window for the Python traceback.
    pause
    exit /b 1
)

powershell.exe -NoProfile -Command "if (Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    echo [3/3] Opening frontend window...
    start "kwkagent Frontend" /D "%~dp0frontend" cmd.exe /k npm.cmd run dev
) else (
    echo [3/3] Frontend is already running on port 3000.
)

echo.
echo ========================================
echo Startup commands have been sent.
echo Frontend: http://localhost:3000/
echo API docs: http://127.0.0.1:8000/docs
echo.
echo Keep the Backend and Frontend windows open.
echo Close them or press Ctrl+C in them to stop the app.
echo ========================================

powershell.exe -NoProfile -Command "Start-Sleep -Seconds 3"
start "" "http://localhost:3000/"
exit /b 0
