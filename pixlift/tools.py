"""Dis arac (realesrgan-ncnn-vulkan, ffmpeg, ffprobe) cozumleme ve calistirma."""

import os
import shutil
import subprocess
import sys


def _app_dir():
    """Script veya donmus exe klasoru (yanina tools/ konabilir)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _first_existing(paths):
    for path in paths:
        if path and os.path.isfile(path):
            return os.path.abspath(path)
    return None


def resolve_realesrgan():
    """Sirayla: env -> PATH -> ./tools (repo veya exe yaninda)."""
    env = os.environ.get("PIXLIFT_REALESRGAN", "").strip()
    name = "realesrgan-ncnn-vulkan.exe" if os.name == "nt" else "realesrgan-ncnn-vulkan"
    base = _app_dir()
    return _first_existing(
        [
            env or None,
            shutil.which("realesrgan-ncnn-vulkan"),
            shutil.which("realesrgan-ncnn-vulkan.exe"),
            os.path.join(base, "tools", "realesrgan", name),
            os.path.join(base, "tools", name),
            os.path.join(base, name),
        ]
    )


def resolve_ffmpeg():
    env = os.environ.get("PIXLIFT_FFMPEG", "").strip()
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    base = _app_dir()
    return _first_existing(
        [
            env or None,
            shutil.which("ffmpeg"),
            shutil.which("ffmpeg.exe"),
            os.path.join(base, "tools", "ffmpeg", "bin", name),
            os.path.join(base, "tools", "ffmpeg", name),
            os.path.join(base, "tools", name),
        ]
    )


def resolve_ffprobe():
    env = os.environ.get("PIXLIFT_FFPROBE", "").strip()
    name = "ffprobe.exe" if os.name == "nt" else "ffprobe"
    base = _app_dir()
    ffmpeg = resolve_ffmpeg()
    beside_ffmpeg = os.path.join(os.path.dirname(ffmpeg), name) if ffmpeg else None
    return _first_existing(
        [
            env or None,
            shutil.which("ffprobe"),
            shutil.which("ffprobe.exe"),
            beside_ffmpeg,
            os.path.join(base, "tools", "ffmpeg", "bin", name),
            os.path.join(base, "tools", "ffmpeg", name),
            os.path.join(base, "tools", name),
        ]
    )


def refresh_tool_paths():
    """Test / yeniden cozumleme icin global yollari guncelle."""
    global REALESRGAN_EXE, FFMPEG_EXE, FFPROBE_EXE
    REALESRGAN_EXE = resolve_realesrgan()
    FFMPEG_EXE = resolve_ffmpeg()
    FFPROBE_EXE = resolve_ffprobe()
    return REALESRGAN_EXE, FFMPEG_EXE, FFPROBE_EXE


REALESRGAN_EXE = None
FFMPEG_EXE = None
FFPROBE_EXE = None
refresh_tool_paths()

NO_CREATE_WINDOW = 0x08000000 if os.name == "nt" else 0


def run_hidden(args, **kwargs):
    # stdin acikca DEVNULL verilmezse, --windowed (konsolsuz) paketlenmis exe'de
    # miras alinan gecersiz stdin bazi alt sureclerin donmasina yol acabiliyor.
    return subprocess.run(
        args,
        creationflags=NO_CREATE_WINDOW,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        **kwargs,
    )


def check_tools_available():
    """Eksik araclari insan-okunur etiketlerle dondur."""
    refresh_tool_paths()
    checks = [
        (REALESRGAN_EXE, "realesrgan-ncnn-vulkan (PIXLIFT_REALESRGAN or tools/realesrgan/)"),
        (FFMPEG_EXE, "ffmpeg (PIXLIFT_FFMPEG or PATH or tools/ffmpeg/)"),
        (FFPROBE_EXE, "ffprobe (PIXLIFT_FFPROBE or beside ffmpeg)"),
    ]
    return [label for path, label in checks if not path or not os.path.isfile(path)]
