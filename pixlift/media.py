"""Dosya turu yardimcilari, model/olcek mantigi, ve video/gorsel probing."""

import json
import os

from PySide6.QtGui import QImage

from . import tools
from .tools import run_hidden

VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
GIF_EXTENSIONS = (".gif",)
ALL_EXTENSIONS = VIDEO_EXTENSIONS + IMAGE_EXTENSIONS + GIF_EXTENSIONS


def is_image_file(path):
    return os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS


def is_gif_file(path):
    return os.path.splitext(path)[1].lower() in GIF_EXTENSIONS


def image_output_format(ext):
    ext = ext.lower().lstrip(".")
    if ext == "jpeg":
        ext = "jpg"
    return ext if ext in ("jpg", "png", "webp") else "png"


# Bu oturumda olculen kare-basi sure (saniye) ve referans piksel sayisi (950x718).
BENCHMARKS = {
    "fast": {"model": "realesr-animevideov3", "seconds_per_frame": 1.5, "ref_px": 950 * 718},
    "quality": {"model": "realesrgan-x4plus", "seconds_per_frame": 37.0, "ref_px": 950 * 718},
}

# ncnn-vulkan'da bu modeller yalniz native 4x agina sahip. -s 2/3 verilirse
# karo (tile) birlestirme bozulur ve mozaik artefakti olusur. Native 4x calistirip
# hedef olcege ffmpeg ile indirmek gerekir (Python Real-ESRGAN outscale mantigi).
FIXED_NATIVE_SCALE = {
    "realesrgan-x4plus": 4,
    "realesrgan-x4plus-anime": 4,
    "realesrnet-x4plus": 4,
}


def engine_scale_for(model, requested_scale):
    """Real-ESRGAN -s degeri: model native olcegi varsa onu kullan."""
    native = FIXED_NATIVE_SCALE.get(model)
    return int(native if native is not None else requested_scale)


def needs_post_downscale(model, requested_scale):
    native = FIXED_NATIVE_SCALE.get(model)
    return native is not None and int(requested_scale) != int(native)


def even_dim(value):
    value = int(value)
    return value if value % 2 == 0 else value - 1


def target_size(info, scale):
    return even_dim(info["width"] * scale), even_dim(info["height"] * scale)


# GPU/surucu bazi kare-kombinasyonlarinda ncnn-vulkan'i tik sikici bir sekilde
# donduruyor (gozlemlendi: 1920x1080 + 4x + tile=128). Kareler arasi bekleme
# suresi sabit degil: Kaliteli model + yuksek cozunurlukte tek kare 90sn'yi asabiliyor.
STALL_TIMEOUT_SECONDS = 90
STALL_TIMEOUT_MIN_SECONDS = 120
STALL_PER_FRAME_MULT = 4.0


def probe_video(path):
    """ffprobe ile video/ses temel bilgilerini al."""
    result = run_hidden(
        [
            tools.FFPROBE_EXE,
            "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            path,
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe başarısız:\n{result.stderr[-800:]}")

    data = json.loads(result.stdout)
    video_stream = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    if video_stream is None:
        raise RuntimeError("Video akışı bulunamadı.")

    num, den = video_stream["r_frame_rate"].split("/")
    fps = float(num) / float(den) if float(den) != 0 else float(num)
    duration = float(data["format"].get("duration") or video_stream.get("duration") or 0)
    width = int(video_stream["width"])
    height = int(video_stream["height"])
    bitrate = int(video_stream.get("bit_rate") or data["format"].get("bit_rate") or 0)
    frame_count = int(round(duration * fps)) if duration else int(video_stream.get("nb_frames") or 0)
    has_audio = any(s["codec_type"] == "audio" for s in data["streams"])

    return {
        "width": width,
        "height": height,
        "fps": fps,
        "duration": duration,
        "bitrate": bitrate,
        "frame_count": max(frame_count, 1),
        "has_audio": has_audio,
    }


def probe_image(path):
    """Gorsel boyutlarini al (ffprobe yerine QImage - video akisi/ses varsayimi yok)."""
    image = QImage(path)
    if image.isNull():
        raise RuntimeError("Görsel okunamadı veya format desteklenmiyor.")

    return {
        "width": image.width(),
        "height": image.height(),
        "fps": 0,
        "duration": 0,
        "bitrate": 0,
        "frame_count": 1,
        "has_audio": False,
        "file_size": os.path.getsize(path),
    }


def estimate_seconds(info, quality_key):
    bench = BENCHMARKS[quality_key]
    px = info["width"] * info["height"]
    per_frame = bench["seconds_per_frame"] * (px / bench["ref_px"])
    return per_frame * info["frame_count"]


def estimate_seconds_per_frame(info, quality_key, scale=3):
    """Tek kare icin tahmini sure (olcek 4x referans; 2x daha hafif, 3x orta)."""
    bench = BENCHMARKS[quality_key]
    px = info["width"] * info["height"]
    per_frame = bench["seconds_per_frame"] * (px / bench["ref_px"])
    # Benchmark'lar 4x civari; 2x daha hafif, 3x orta.
    scale_factor = {2: 0.55, 3: 0.8, 4: 1.0}.get(int(scale), 1.0)
    return max(per_frame * scale_factor, 1.0)


def stall_timeout_for_job(info, quality_key, scale=3):
    """Iki kare arasinda en fazla bu kadar beklenir; asilirsa asili sayilir."""
    per_frame = estimate_seconds_per_frame(info, quality_key, scale)
    return max(
        STALL_TIMEOUT_SECONDS,
        STALL_TIMEOUT_MIN_SECONDS,
        per_frame * STALL_PER_FRAME_MULT,
    )


def format_duration(seconds):
    seconds = int(round(seconds))
    if seconds < 90:
        return f"~{seconds} sn"
    minutes = seconds / 60
    if minutes < 90:
        return f"~{minutes:.0f} dk"
    return f"~{minutes / 60:.1f} saat"


def low_bitrate_risk(info):
    """Kaba bir 'sikistirilmis kaynak' isareti - kesin bir kural degil, sadece uyari."""
    if not info["bitrate"] or not info["fps"]:
        return False
    bits_per_pixel_per_frame = info["bitrate"] / (info["width"] * info["height"] * info["fps"])
    return bits_per_pixel_per_frame < 0.03


def analyze_audio_gain(audio_path, log):
    """Sessiz ses icin guvenli bir kazanc (dB) hesapla; yeterince yuksekse 0 doner."""
    result = run_hidden([tools.FFMPEG_EXE, "-i", audio_path, "-af", "volumedetect", "-f", "null", "-"])
    mean_db = max_db = None
    for line in result.stderr.splitlines():
        if "mean_volume:" in line:
            mean_db = float(line.split("mean_volume:")[1].replace("dB", "").strip())
        elif "max_volume:" in line:
            max_db = float(line.split("max_volume:")[1].replace("dB", "").strip())

    if mean_db is None or max_db is None:
        return 0.0

    log(f"Ses seviyesi: ortalama {mean_db:.1f}dB, tepe {max_db:.1f}dB")
    if mean_db >= -30:
        return 0.0

    headroom_target = -2.0
    gain = headroom_target - max_db
    return max(0.0, min(gain, 20.0))
