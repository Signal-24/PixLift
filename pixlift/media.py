"""Dosya turu yardimcilari, model/olcek mantigi, ve video/gorsel probing."""

import json
import os
import re
import subprocess

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


def format_duration(seconds, units=None):
    units = units or {"sec": "sn", "min": "dk", "hr": "saat"}
    seconds = int(round(seconds))
    if seconds < 90:
        return f"~{seconds} {units['sec']}"
    minutes = seconds / 60
    if minutes < 90:
        return f"~{minutes:.0f} {units['min']}"
    return f"~{minutes / 60:.1f} {units['hr']}"


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


# --- Cikti dogrulama -------------------------------------------------------
#
# realesrgan-ncnn-vulkan, Vulkan/GPU hatasi aldiginda (bellek yetmemesi, surucu
# zaman asimi vb.) coker ya da hata kodu dondurmek yerine islenemeyen kisimlari
# sifir (siyah) birakip dosyayi yazar ve 0 ile cikar. Goruntu okunamadiginda da
# 0 ile cikiyor. Bu yuzden cikis koduna guvenilemez; cikti icerigi dogrulanir.

# Motor "-t" (tile) degerleri: 0 = otomatik. Siyah/bos cikti genellikle GPU
# bellegi yetmediginde olusur; daha kucuk parcalar daha az bellek ister.
TILE_FALLBACKS = (0, 128, 64, 32)

SAMPLE_SIZE = 64
# 64x64 hucreden bu orandan fazlasi giris/cikti arasinda cok farkliysa cikti bozuk sayilir.
BAD_CELL_DIFF = 80
BAD_CELL_FRACTION = 0.01

_GPU_ERROR_RE = re.compile(
    r"vk[A-Za-z]+\s+failed|out of (?:device )?memory|device lost|VK_ERROR", re.IGNORECASE
)


def image_sample(path, timeout=120):
    """Gorseli 64x64 gri olcege kucultup ham baytlari dondur; okunamazsa None."""
    if not tools.FFMPEG_EXE or not os.path.isfile(path):
        return None
    try:
        result = subprocess.run(
            [
                tools.FFMPEG_EXE, "-v", "error", "-i", path,
                "-vf", f"scale={SAMPLE_SIZE}:{SAMPLE_SIZE}:flags=area",
                "-pix_fmt", "gray", "-f", "rawvideo", "-",
            ],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            creationflags=tools.NO_CREATE_WINDOW,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    data = result.stdout
    if result.returncode != 0 or len(data) != SAMPLE_SIZE * SAMPLE_SIZE:
        return None
    return data


def sample_stats(sample):
    """(ortalama, standart sapma) - 0..255 gri duzeyi."""
    n = len(sample)
    mean = sum(sample) / n
    var = sum((b - mean) ** 2 for b in sample) / n
    return mean, var ** 0.5


def looks_corrupt(in_sample, out_sample):
    """Giris ayrintiliyken cikti duz renkse ya da bolgesel olarak siyahsa True.

    Iki ornek ayni 64x64 hucre duzenindedir; boyutlari farkli olsa da karsilastirilabilir.
    """
    if in_sample is None or out_sample is None:
        return False
    in_mean, in_std = sample_stats(in_sample)
    out_mean, out_std = sample_stats(out_sample)
    if out_std < 1.5 and in_std >= 8:
        return True  # duz siyah / yesil / gri
    if out_mean < 3 and in_mean >= 15:
        return True  # neredeyse tamamen siyah
    bad = sum(1 for a, b in zip(in_sample, out_sample) if abs(a - b) > BAD_CELL_DIFF)
    return bad / len(in_sample) > BAD_CELL_FRACTION  # islenememis bolge (siyah parca)


def engine_stderr_problem(stderr_text):
    """Motor stderr'inden sebep kodu: 'decode_failed' | 'gpu_error' | None."""
    text = stderr_text or ""
    if "decode image" in text and "failed" in text:
        return "decode_failed"
    if _GPU_ERROR_RE.search(text):
        return "gpu_error"
    return None


def output_problem(input_path, output_path, returncode=0, stderr_text="", input_sample=None):
    """Motor ciktisini dogrula. Sorun yoksa None, varsa kisa bir sebep kodu dondur.

    Kodlar: exit_code, decode_failed, gpu_error, no_output, unreadable, blank_output.
    """
    if returncode != 0:
        return "exit_code"
    stderr_problem = engine_stderr_problem(stderr_text)
    if stderr_problem == "decode_failed":
        return stderr_problem
    if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
        return "no_output"
    if input_sample is None:
        input_sample = image_sample(input_path)
    out_sample = image_sample(output_path)
    if out_sample is None and input_sample is not None:
        return "unreadable"
    if looks_corrupt(input_sample, out_sample):
        return "blank_output"
    return stderr_problem  # gpu_error ya da None
