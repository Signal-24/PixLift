# External tools (not shipped in git)

PixLift shells out to **Real-ESRGAN ncnn-vulkan** and **ffmpeg** / **ffprobe**.
Binaries are large and licensed separately — download them yourself.

## Layout (recommended)

```
PixLift/
  tools/
    realesrgan/
      realesrgan-ncnn-vulkan.exe   # Windows
      models/                      # required .bin / .param files
    ffmpeg/
      bin/
        ffmpeg.exe
        ffprobe.exe
```

On Linux/macOS use `realesrgan-ncnn-vulkan`, `ffmpeg`, and `ffprobe` without `.exe`.

## Downloads

- Real-ESRGAN ncnn-vulkan releases: https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases  
  Unpack so `models/` sits next to the executable (PixLift runs with that folder as cwd).
- ffmpeg builds: https://ffmpeg.org/download.html (need `ffmpeg` + `ffprobe`)

## Alternatives

1. Put the tools on your **PATH**, or  
2. Set environment variables:

```text
PIXLIFT_REALESRGAN=/full/path/to/realesrgan-ncnn-vulkan
PIXLIFT_FFMPEG=/full/path/to/ffmpeg
PIXLIFT_FFPROBE=/full/path/to/ffprobe
```

Windows PowerShell example:

```powershell
$env:PIXLIFT_REALESRGAN = "C:\tools\realesrgan\realesrgan-ncnn-vulkan.exe"
$env:PIXLIFT_FFMPEG = "C:\ffmpeg\bin\ffmpeg.exe"
$env:PIXLIFT_FFPROBE = "C:\ffmpeg\bin\ffprobe.exe"
python pixlift.py
```
