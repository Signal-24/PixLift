# One-time (or after moving the folder): create .venv and install deps.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error "Python not found on PATH. Install Python 3.10+ and retry."
}

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    Write-Host "Creating virtual environment (.venv)..."
    python -m venv .venv
}

Write-Host "Installing requirements..."
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\pip.exe install -r requirements.txt

$local = Join-Path $PSScriptRoot "run-local.ps1"
$example = Join-Path $PSScriptRoot "scripts\run-local.example.ps1"
if (-not (Test-Path $local)) {
    Copy-Item $example $local
    Write-Host "Created run-local.ps1 from example — edit Real-ESRGAN / ffmpeg paths if needed."
}

Write-Host ""
Write-Host "Setup done. Double-click PixLift.bat to start, or run:"
Write-Host "  .\PixLift.bat"
Write-Host ""
Write-Host "Tools: put Real-ESRGAN + ffmpeg under tools\ (see tools\README.md)"
Write-Host "       or set paths in run-local.ps1 / PIXLIFT_* env vars."
