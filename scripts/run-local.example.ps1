# Example local launcher — copy to project root as run-local.ps1 (gitignored) and edit paths.
# PixLift.bat uses this file when present; otherwise it runs with tools on PATH / tools\.

$Root = Split-Path -Parent $PSScriptRoot
if (Test-Path (Join-Path $PSScriptRoot "pixlift.py")) {
    $Root = $PSScriptRoot
}

$env:PIXLIFT_REALESRGAN = "C:\path\to\realesrgan-ncnn-vulkan.exe"
$env:PIXLIFT_FFMPEG = "C:\path\to\ffmpeg.exe"
$env:PIXLIFT_FFPROBE = "C:\path\to\ffprobe.exe"

Set-Location $Root
$py = Join-Path $Root ".venv\Scripts\python.exe"
if (Test-Path $py) {
    & $py .\pixlift.py
} else {
    python .\pixlift.py
}
