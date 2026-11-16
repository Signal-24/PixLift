# PixLift

Desktop app to upscale videos, photos, and GIFs using **Real-ESRGAN (ncnn-vulkan)** and **ffmpeg**.  
PySide6 UI — Turkish / English, dark / light theme.

> Third-party engines are **not** bundled. Install Real-ESRGAN + ffmpeg yourself ([tools/README.md](tools/README.md)).

## Features

- Scale: **photos 4x** (fixed) · **video/GIF 2x / 3x**
- Models: **Fast** (animevideov3) / **Quality** (x4plus; for video 2x/3x runs native 4x then downscales)
- Audio boost: Off / Auto / +25% / +50% / +100%
- Output FPS: Original / 30fps / 60fps
- Completion sound
- Language: TR / EN
- Locks preferences while a job is running
- **Output validation:** Real-ESRGAN can exit with code 0 yet write a black/blank image (GPU memory or
  driver errors). PixLift checks every result against the source, never leaves a bad file next to your
  original, and automatically retries with smaller tile sizes (`-t 128 / 64 / 32`) before reporting an error.
  For videos/GIFs the first frames are checked early and the frame count is verified before merging.

## Requirements

- Python 3.10+ (tested on 3.13)
- Windows, Linux, or macOS with a Vulkan-capable GPU (Intel / AMD / NVIDIA)
- [Real-ESRGAN-ncnn-vulkan](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases) + models
- [ffmpeg](https://ffmpeg.org/download.html) (`ffmpeg` and `ffprobe`)

### System requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 8 GB (photos / small GIFs) | **16 GB** for video |
| GPU | Vulkan-capable (Intel / AMD / NVIDIA) | Dedicated GPU; integrated is much slower |
| Disk | A few GB free | Extra space ≈ several× the source video (temp frames) |

Long / high-resolution videos benefit from **32 GB** RAM. Upscaling is GPU-bound; weak or integrated GPUs mean long runtimes.

## Quick start

```bash
git clone https://github.com/Signal-24/PixLift.git
cd PixLift
```

**Windows (easiest):** double-click `setup.bat` (installs deps and starts the app) or `PixLift.bat` anytime after setup.  
Optional: copy `scripts/run-local.example.ps1` → `run-local.ps1` and set tool paths.

**Manual (all platforms):**

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
# source .venv/bin/activate

pip install -r requirements.txt
```

Place tools under `tools/` (see [tools/README.md](tools/README.md)) **or** set `PIXLIFT_REALESRGAN` / `PIXLIFT_FFMPEG` / `PIXLIFT_FFPROBE`, then:

```bash
python pixlift.py
```
## Build Windows .exe (optional)

```bash
pip install -r requirements-dev.txt
# or: build.bat
pyinstaller --noconfirm --onefile --windowed --name PixLift pixlift.py
```

Output: `dist/PixLift.exe`. Put a `tools/` folder next to the exe (same layout as above), or rely on env vars / PATH.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `PIXLIFT_REALESRGAN` | Full path to `realesrgan-ncnn-vulkan` |
| `PIXLIFT_FFMPEG` | Full path to `ffmpeg` |
| `PIXLIFT_FFPROBE` | Full path to `ffprobe` |

Resolution order: **env → PATH → `./tools/...`**.

## License

MIT — see [LICENSE](LICENSE).

Real-ESRGAN and ffmpeg have their own licenses; comply with those when redistributing binaries.

## Disclaimer

Personal / hobby tool. Upscaling is GPU-heavy; expect long runtimes on integrated graphics. No warranty.
