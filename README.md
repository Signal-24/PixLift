# PixLift

Desktop app to upscale videos, photos, and GIFs using **Real-ESRGAN (ncnn-vulkan)** and **ffmpeg**.  
PySide6 UI — Turkish / English, dark / light theme.

> Third-party engines are **not** bundled. Install Real-ESRGAN + ffmpeg yourself ([tools/README.md](tools/README.md)).

## Features

- Scale **2x / 4x**
- Models: **Fast** (animevideov3) / **Quality** (x4plus, slower) — scale (2x/4x) sets output size, not the model name
- Audio boost: Off / Auto / +25% / +50% / +100%
- Output FPS: Original / 30 / 60
- Completion sound
- Language: TR / EN
- Locks preferences while a job is running

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
git clone https://github.com/Mendocan/PixLift.git
cd PixLift
```

**Windows (easiest):** double-click `setup.bat` once, then double-click `PixLift.bat` anytime.  
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
