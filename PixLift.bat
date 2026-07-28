@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment missing. Running setup...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
  if errorlevel 1 (
    echo Setup failed.
    pause
    exit /b 1
  )
)

if exist "run-local.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-local.ps1"
) else (
  ".venv\Scripts\python.exe" "%~dp0pixlift.py"
)

if errorlevel 1 (
  echo.
  echo PixLift exited with an error.
  pause
)
