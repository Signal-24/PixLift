# Example local launcher — copy to run-local.ps1 (gitignored) and edit paths.
$env:PIXLIFT_REALESRGAN = "C:\path\to\realesrgan-ncnn-vulkan.exe"
$env:PIXLIFT_FFMPEG = "C:\path\to\ffmpeg.exe"
$env:PIXLIFT_FFPROBE = "C:\path\to\ffprobe.exe"
Set-Location $PSScriptRoot\..
python .\pixlift.py
