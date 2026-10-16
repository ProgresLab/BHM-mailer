@echo off
setlocal
cd /d "%~dp0"
title BHM Mailer - IMAP ON - SMTP OFF
if not exist ".venv\Scripts\python.exe" (
  echo Brak lokalnego venv. Najpierw przygotuj zaleznosci zgodnie z README.
  pause
  exit /b 1
)
echo BHM Mailer: http://127.0.0.1:8000 - IMAP ON, SMTP zawsze OFF.
echo Pozostaw to okno otwarte. Zamkniecie przegladarki nie zatrzymuje aplikacji.
".venv\Scripts\python.exe" tools\run_imap_safe.py
if errorlevel 1 pause
