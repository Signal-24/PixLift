@echo off
setlocal
cd /d "%~dp0"

echo PixLift setup...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 (
  echo.
  echo Setup failed.
  pause
  exit /b 1
)

echo.
echo Launching PixLift...
call "%~dp0PixLift.bat"
