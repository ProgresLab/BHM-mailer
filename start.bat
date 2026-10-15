@echo off
setlocal

cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=8000"
set "APP_URL=http://%HOST%:%PORT%"

title BHM Chemicals Mailing Tool

echo.
echo ==========================================
echo   BHM Chemicals Mailing Tool - local start
echo ==========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.11+ and try again.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating local virtual environment...
  python -m venv .venv
  if errorlevel 1 goto :error
)

echo Installing or checking Python dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

if not exist ".env" (
  echo Creating local .env from .env.example...
  copy ".env.example" ".env" >nul
  if errorlevel 1 goto :error
)

echo.
echo Starting local server on %APP_URL%
echo A separate server window will stay open while the app is running.
echo.

start "BHM Mailer Server" ".venv\Scripts\python.exe" -m uvicorn app.main:app --host %HOST% --port %PORT%

echo Waiting for the app to load...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$url='%APP_URL%'; for ($i = 0; $i -lt 60; $i++) { try { Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 1 | Out-Null; exit 0 } catch { Write-Host '.' -NoNewline; Start-Sleep -Milliseconds 500 } }; exit 1"
if errorlevel 1 (
  echo.
  echo The app did not respond on %APP_URL%.
  echo Check the "BHM Mailer Server" window for details.
  echo.
  pause
  exit /b 1
)

echo.
echo App is ready. Opening browser...
start "" "%APP_URL%"

echo.
echo Ready. To stop the app, close the "BHM Mailer Server" window.
echo.
pause

exit /b 0

:error
echo.
echo Startup failed. Check the message above.
echo.
pause
exit /b 1
