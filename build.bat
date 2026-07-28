@echo off
cd /d "%~dp0"
python -m PyInstaller --noconfirm --onefile --windowed --name PixLift pixlift.py
if errorlevel 1 (
  echo Build failed.
  exit /b 1
)
echo.
echo Built: dist\PixLift.exe
echo Place tools\ next to the exe, or set PIXLIFT_* environment variables.
