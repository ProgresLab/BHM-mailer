@echo off
setlocal
cd /d "%~dp0"
title BHM Mailer - IMAP ON - SMTP ON
if not exist ".venv\Scripts\python.exe" (
  echo Brak lokalnego venv. Przygotuj zaleznosci zgodnie z README.
  pause
  exit /b 1
)
echo BHM Mailer: IMAP ON + SMTP ON - http://127.0.0.1:8000
echo SMTP dostepne. Kazda kampania wymaga osobnego zatwierdzenia w aplikacji.
echo Pozostaw to okno otwarte. Zamkniecie przegladarki nie zatrzymuje aplikacji.
".venv\Scripts\python.exe" tools\run_bhm_operational.py %*
if errorlevel 1 pause
