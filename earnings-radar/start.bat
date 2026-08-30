@echo off
REM ===================================================================
REM  Earnings Radar — start and keep running
REM
REM  Double-click this file, or run it from PowerShell. Leave the window
REM  open: closing it stops the system.
REM
REM  Catalyst detection sweeps every 30 seconds around the clock, so the
REM  laptop needs to stay awake. This script asks Windows not to sleep
REM  while it runs, and restores your normal settings when it exits.
REM ===================================================================

cd /d "%~dp0"
title Earnings Radar

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   No virtual environment found in this folder.
  echo   Expected: %CD%\.venv\Scripts\python.exe
  echo.
  echo   Run this once to create it:
  echo     python -m venv .venv
  echo     .venv\Scripts\pip install -e ".[dev]"
  echo.
  pause
  exit /b 1
)

if not exist ".env" (
  echo.
  echo   No .env file in %CD%
  echo.
  echo   If you made one in Notepad it may have saved as .env.txt —
  echo   turn on File name extensions in Explorer's View menu to check.
  echo.
  pause
  exit /b 1
)

echo.
echo   Checking providers before starting...
echo.
.venv\Scripts\python.exe -m app.preflight
if errorlevel 1 (
  echo.
  echo   Preflight found a blocking problem. Fix the FAIL lines above.
  echo   Starting anyway would run the system with something important
  echo   silently broken.
  echo.
  choice /c YN /m "   Start anyway"
  if errorlevel 2 exit /b 1
)

REM Keep the machine awake while this window is open. Balanced-scheme
REM values are restored on exit below.
powercfg /change standby-timeout-ac 0 >nul 2>&1
powercfg /change hibernate-timeout-ac 0 >nul 2>&1

echo.
echo   ==========================================================
echo    Earnings Radar is running.
echo.
echo    Dashboard:  http://localhost:8000
echo    Health:     http://localhost:8000/api/health
echo.
echo    Leave this window open. Ctrl-C stops it.
echo   ==========================================================
echo.

.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

REM Restore the usual sleep behaviour (30 min standby, 60 min hibernate).
echo.
echo   Stopped. Restoring normal sleep settings.
powercfg /change standby-timeout-ac 30 >nul 2>&1
powercfg /change hibernate-timeout-ac 60 >nul 2>&1
pause
