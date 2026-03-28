@echo off
title Elira AI - Mobile Access
color 0A
echo.
echo   ╔══════════════════════════════════════════╗
echo   ║   ELIRA AI - Mobile / LAN Access Mode    ║
echo   ╚══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: Получаем IP адрес
echo [INFO] Определяю IP адрес...
set IP=
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /R "IPv4"') do (
    if not defined IP set "IP=%%a"
)
set IP=%IP: =%

if "%IP%"=="" (
    echo [ERROR] Не удалось определить IP. Проверь Wi-Fi подключение.
    pause
    exit /b 1
)

echo.
echo   Твой IP: %IP%
echo.

:: ═══ Firewall — открываем порты 5173 и 8000 ═══
echo [INFO] Проверяю firewall...
netsh advfirewall firewall show rule name="Elira Frontend" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Добавляю правило firewall для порта 5173...
    netsh advfirewall firewall add rule name="Elira Frontend" dir=in action=allow protocol=TCP localport=5173 >nul 2>&1
    if errorlevel 1 (
        echo [WARN] Не удалось добавить правило. Запусти .bat от имени Администратора!
    ) else (
        echo [OK] Порт 5173 открыт
    )
) else (
    echo [OK] Правило для 5173 уже есть
)

netsh advfirewall firewall show rule name="Elira Backend" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Добавляю правило firewall для порта 8000...
    netsh advfirewall firewall add rule name="Elira Backend" dir=in action=allow protocol=TCP localport=8000 >nul 2>&1
    if errorlevel 1 (
        echo [WARN] Не удалось добавить правило. Запусти .bat от имени Администратора!
    ) else (
        echo [OK] Порт 8000 открыт
    )
) else (
    echo [OK] Правило для 8000 уже есть
)

echo.
echo   Для доступа с телефона:
echo     1. Телефон и ПК в одной Wi-Fi сети
echo     2. Открой: http://%IP%:5173
echo.

:: ═══ Запуск бекенда на 0.0.0.0 ═══
echo [INFO] Запускаю бекенд на 0.0.0.0...
start /min "Elira Backend (LAN)" cmd /c "cd /d "%~dp0backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 4 /nobreak > nul

:: ═══ Запуск фронтенда на 0.0.0.0 ═══
echo [INFO] Запускаю фронтенд на 0.0.0.0...
start "" cmd /c "set VITE_API_BASE_URL=http://%IP%:8000&& set VITE_HOST=0.0.0.0&& cd /d "%~dp0" && npm --prefix frontend run dev"

timeout /t 3 /nobreak > nul

echo.
echo   ════════════════════════════════════════
echo   ✓ Elira доступна: http://%IP%:5173
echo   ✓ API:            http://%IP%:8000/docs
echo   ════════════════════════════════════════
echo.
echo   Для остановки — закрой это окно.
echo.
pause
