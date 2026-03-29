@echo off
setlocal
title Elira AI
color 0A

cd /d "%~dp0"

echo.
echo [INFO] Startup order: backend ^> Tauri
echo [INFO] Core deps: backend\requirements.txt and npm install
echo [INFO] Optional deps: backend\requirements-optional.txt
echo [INFO] Missing optional packages only disable vector memory and screenshot.
echo [INFO] Check Dashboard for Project Brain capability warnings.
echo.

if not exist "backend\.venv\Scripts\python.exe" (
    echo [ERROR] Missing backend virtualenv: backend\.venv\Scripts\python.exe
    echo [HINT] Run:
    echo        cd backend
    echo        python -m venv .venv
    echo        .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist "node_modules" (
    echo [0/3] Installing root npm dependencies...
    call npm.cmd install
    if errorlevel 1 (
        echo [ERROR] npm install failed
        pause
        exit /b 1
    )
)

echo [1/3] Starting backend on 127.0.0.1:8000...
start /min "Elira Backend" cmd /c "cd /d \"%~dp0backend\" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 3 /nobreak > nul

echo [2/3] Starting Tauri dev shell...
call npm.cmd run tauri dev

if errorlevel 1 (
    echo.
    echo [ERROR] Tauri dev failed to start.
    echo [HINT] Try:
    echo        npm install
    echo        npm run tauri dev
    pause
    exit /b 1
)

echo.
echo [INFO] If the dashboard shows missing packages, install backend\requirements-optional.txt
echo [INFO] Backend keeps running in a separate window until you close it.
echo.

endlocal
exit /b 0
