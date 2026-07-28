"""PixLift - desktop video/image upscaler (Real-ESRGAN + ffmpeg wrapper)."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

from PySide6.QtCore import Qt, QRectF, QThread, QTimer, Signal, QUrl
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


def _app_dir():
    """Script veya donmus exe klasoru (yanina tools/ konabilir)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _first_existing(paths):
    for path in paths:
        if path and os.path.isfile(path):
            return os.path.abspath(path)
    return None


def resolve_realesrgan():
    """Sirayla: env → PATH → ./tools (repo veya exe yaninda)."""
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

NO_CREATE_WINDOW = 0x08000000 if os.name == "nt" else 0

# GPU/surucu bazi kare-kombinasyonlarinda ncnn-vulkan'i tik sikici bir sekilde
# donduruyor (gozlemlendi: 1920x1080 + 4x + tile=128). Kareler arasi bekleme
# suresi sabit degil: Kaliteli model + yuksek cozunurlukte tek kare 90sn'yi asabiliyor.
STALL_TIMEOUT_SECONDS = 90
STALL_TIMEOUT_MIN_SECONDS = 120
STALL_PER_FRAME_MULT = 4.0

ACCENT = {"dark": "#22D3EE", "light": "#0891B2"}
DEFAULT_THEME = "dark"
DEFAULT_LANGUAGE = "tr"
CONFIG_PATH = os.path.join(os.environ.get("APPDATA", tempfile.gettempdir()), "PixLift", "config.json")

# UI metinleri — TR / EN
STRINGS = {
    "tr": {
        "drop_empty": "Bir video, fotoğraf veya GIF dosyası sürükleyip bırakın\nveya aşağıdan seçin",
        "browse": "Dosya Seç...",
        "section_scale": "BÜYÜTME",
        "section_model": "MODEL",
        "section_audio": "SES",
        "section_fps": "FPS",
        "model_hd": "Hızlı",
        "model_4k": "Kaliteli",
        "model_hd_tip": "Hızlı model (animevideov3) — dakikalar sürer; çıktı boyutu BÜYÜTME ile belirlenir",
        "model_4k_tip": "Yüksek detay (x4plus) — daha yavaş, daha keskin; çıktı boyutu BÜYÜTME ile belirlenir",
        "audio_off": "Kapalı",
        "audio_auto": "Otomatik",
        "audio_25": "+%25",
        "audio_50": "+%50",
        "audio_100": "+%100",
        "audio_tip": "Ses yükseltme: kapalı, otomatik analiz veya sabit yüzde",
        "fps_original": "Orijinal",
        "fps_30": "30",
        "fps_60": "60",
        "fps_tip": "Çıktı kare hızı (süre korunur)",
        "eta_prefix": "Tahmini süre:",
        "run": "Çalıştır",
        "stop": "Durdur",
        "open_folder": "Klasörü Aç",
        "play_video": "Videoyu Oynat",
        "play_photo": "Fotoğrafı Aç",
        "play_gif": "GIF'i Aç",
        "remaining": "Kalan süre:",
        "done": "Tamamlandı ✓",
        "error_occurred": "Hata oluştu.",
        "stopped": "İşlem durduruldu.",
        "stopping": "Durduruluyor...",
        "error_title": "Hata",
        "browse_title": "Video, fotoğraf veya GIF seç",
        "browse_filter": "Desteklenen dosyalar (*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.jpg *.jpeg *.png *.webp *.gif)",
        "theme_to_light": "Açık temaya geç",
        "theme_to_dark": "Koyu temaya geç",
        "lang_tip": "Switch to English",
        "warn_bitrate": (
            "<br><span style='color:#f59e0b;'>Uyarı: Bu kaynağın bit oranı düşük "
            "görünüyor - Hızlı model + 3x'te koyu bölgelerde blok/mozaik "
            "artefaktı görülebilir.</span>"
        ),
        "photo": "Fotoğraf",
        "missing_title": "PixLift - Eksik bileşen",
        "missing_body": "Şu araçlar bulunamadı, PixLift çalışamaz:\n",
        "read_fail": "okunamadı",
        "kind_image": "Görsel",
        "kind_video": "Video",
    },
    "en": {
        "drop_empty": "Drop a video, photo or GIF here\nor choose a file below",
        "browse": "Choose File...",
        "section_scale": "SCALE",
        "section_model": "MODEL",
        "section_audio": "AUDIO",
        "section_fps": "FPS",
        "model_hd": "Fast",
        "model_4k": "Quality",
        "model_hd_tip": "Fast model (animevideov3) — minutes; output size is set by SCALE",
        "model_4k_tip": "High detail (x4plus) — slower, sharper; output size is set by SCALE",
        "audio_off": "Off",
        "audio_auto": "Auto",
        "audio_25": "+25%",
        "audio_50": "+50%",
        "audio_100": "+100%",
        "audio_tip": "Boost: off, auto analysis, or fixed percent",
        "fps_original": "Original",
        "fps_30": "30",
        "fps_60": "60",
        "fps_tip": "Output frame rate (duration preserved)",
        "eta_prefix": "Estimated time:",
        "run": "Run",
        "stop": "Stop",
        "open_folder": "Open Folder",
        "play_video": "Play Video",
        "play_photo": "Open Photo",
        "play_gif": "Open GIF",
        "remaining": "Time left:",
        "done": "Done ✓",
        "error_occurred": "An error occurred.",
        "stopped": "Cancelled.",
        "stopping": "Stopping...",
        "error_title": "Error",
        "browse_title": "Choose video, photo or GIF",
        "browse_filter": "Supported files (*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.jpg *.jpeg *.png *.webp *.gif)",
        "theme_to_light": "Switch to light theme",
        "theme_to_dark": "Switch to dark theme",
        "lang_tip": "Türkçe'ye geç",
        "warn_bitrate": (
            "<br><span style='color:#f59e0b;'>Warning: This source looks low-bitrate — "
            "Fast model + 3x may show block artifacts in dark areas.</span>"
        ),
        "photo": "Photo",
        "missing_title": "PixLift - Missing tools",
        "missing_body": "These tools were not found; PixLift cannot run:\n",
        "read_fail": "could not be read",
        "kind_image": "Image",
        "kind_video": "Video",
    },
}


def load_config():
    data = {"theme": DEFAULT_THEME, "language": DEFAULT_LANGUAGE}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if saved.get("theme") in ACCENT:
            data["theme"] = saved["theme"]
        if saved.get("language") in STRINGS:
            data["language"] = saved["language"]
    except Exception:  # noqa: BLE001
        pass
    return data


def save_config(**updates):
    data = load_config()
    data.update({k: v for k, v in updates.items() if v is not None})
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:  # noqa: BLE001
        pass


def load_theme_preference():
    return load_config()["theme"]


def save_theme_preference(theme):
    save_config(theme=theme)


def play_completion_sound():
    """Kisa tamamlanma uyarisi (Windows)."""
    try:
        import winsound

        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except Exception:  # noqa: BLE001
        try:
            print("\a", end="", flush=True)
        except Exception:  # noqa: BLE001
            pass


def build_stylesheet(theme):
    accent = ACCENT[theme]
    if theme == "dark":
        c = {
            "bg": "#1e1f22",
            "card": "#2a2c30",
            "border": "rgba(34, 211, 238, 0.35)",
            "disabled_bg": "#3a3d42",
            "text": "#e8e8e8",
            "muted": "#9aa0a6",
            "accent_hover": "#5eead4",
            "accent_pressed": "#0e8a9c",
            "input_bg": "#26282c",
        }
    else:
        c = {
            "bg": "#f3f5f7",
            "card": "#ffffff",
            "border": "rgba(8, 145, 178, 0.35)",
            "disabled_bg": "#dde1e6",
            "text": "#1f2124",
            "muted": "#5f6368",
            "accent_hover": "#22d3ee",
            "accent_pressed": "#067a8c",
            "input_bg": "#ffffff",
        }

    return f"""
    QMainWindow, QWidget {{
        background: {c['bg']};
        color: {c['text']};
        font-family: 'Segoe UI';
        font-size: 13px;
    }}
    QLabel#titleLabel {{
        font-size: 22px;
        font-weight: 600;
        color: {c['text']};
    }}
    QLabel#infoLabel {{
        color: {c['muted']};
        font-size: 12px;
        padding: 2px 2px;
    }}
    QLabel#dropZone {{
        border: 2px dashed {c['border']};
        border-radius: 10px;
        padding: 28px;
        background: {c['card']};
        color: {c['muted']};
        font-size: 13px;
    }}
    QLabel#dropZone[hasFile="true"] {{
        border-color: {accent};
        color: {c['text']};
        font-weight: 600;
    }}
    QLabel#dropZone[dragOver="true"] {{
        border-color: {accent};
        background: {c['input_bg']};
    }}
    QFrame#card {{
        background: {c['card']};
        border: 1px solid {c['border']};
        border-radius: 10px;
        padding: 8px;
    }}
    QLabel#sectionTitle {{
        color: {c['muted']};
        font-weight: 600;
        font-size: 11px;
        padding-left: 2px;
    }}
    QRadioButton, QCheckBox {{
        padding: 4px;
        spacing: 8px;
    }}
    QRadioButton::indicator {{
        width: 15px;
        height: 15px;
        border-radius: 8px;
        border: 2px solid {c['border']};
        background: {c['input_bg']};
    }}
    QRadioButton::indicator:checked {{
        border: 2px solid {accent};
        background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
            stop:0 {accent}, stop:0.5 {accent}, stop:0.6 {c['card']}, stop:1 {c['card']}
        );
    }}
    QRadioButton:checked {{
        color: {accent};
        font-weight: 600;
    }}
    QCheckBox::indicator {{
        width: 15px;
        height: 15px;
        border-radius: 4px;
        border: 2px solid {c['border']};
        background: {c['input_bg']};
    }}
    QCheckBox::indicator:checked {{
        border: 2px solid {accent};
        background: {accent};
    }}
    QCheckBox:checked {{
        color: {accent};
        font-weight: 600;
    }}
    QPushButton {{
        background: {c['card']};
        border: 1px solid {c['border']};
        border-radius: 8px;
        padding: 8px 16px;
        color: {c['text']};
        font-weight: 600;
    }}
    QPushButton:hover {{
        border-color: {accent};
        color: {accent};
    }}
    QPushButton:disabled {{
        color: {c['muted']};
        border-color: {c['border']};
    }}
    QPushButton#runButton {{
        background: {accent};
        border: none;
        color: #06202b;
        font-size: 14px;
        padding: 11px 16px;
        border-radius: 9px;
    }}
    QPushButton#runButton:hover {{
        background: {c['accent_hover']};
    }}
    QPushButton#runButton:pressed {{
        background: {c['accent_pressed']};
    }}
    QPushButton#runButton:disabled {{
        background: {c['disabled_bg']};
        color: {c['muted']};
    }}
    QPushButton#stopButton {{
        background: {c['card']};
        border: 1px solid #ef4444;
        color: #ef4444;
        font-size: 14px;
        padding: 11px 16px;
        border-radius: 9px;
    }}
    QPushButton#stopButton:hover {{
        background: #ef4444;
        color: #ffffff;
    }}
    QPushButton#stopButton:disabled {{
        background: {c['disabled_bg']};
        border-color: {c['disabled_bg']};
        color: {c['muted']};
    }}
    QPushButton#themeButton {{
        background: {c['card']};
        border: 1px solid {c['border']};
        border-radius: 20px;
        font-size: 16px;
        padding: 0px;
    }}
    QPushButton#themeButton:hover {{
        border-color: {accent};
    }}
    QProgressBar {{
        border: none;
        border-radius: 6px;
        background: {c['border']};
        height: 12px;
        text-align: center;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background: {accent};
        border-radius: 6px;
    }}
    QLabel#hintLabel {{
        color: {c['muted']};
        font-size: 12px;
    }}
    QLabel#statusLabel {{
        color: {c['muted']};
        font-size: 12px;
        padding-top: 4px;
    }}
    QLabel#etaLabel {{
        color: {accent};
        font-size: 13px;
        font-weight: 600;
        padding-top: 6px;
    }}
    """


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


def probe_video(path):
    """ffprobe ile video/ses temel bilgilerini al."""
    result = run_hidden(
        [
            FFPROBE_EXE,
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
    result = run_hidden([FFMPEG_EXE, "-i", audio_path, "-af", "volumedetect", "-f", "null", "-"])
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


class PipelineError(Exception):
    pass


class UpscaleWorker(QThread):
    progress = Signal(int)
    status = Signal(str)
    finished_ok = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, input_path, scale, quality_key, audio_mode="auto", output_fps=None):
        super().__init__()
        self.input_path = input_path
        self.scale = scale
        self.quality_key = quality_key
        # audio_mode: "off" | "auto" | "25" | "50" | "100"
        self.audio_mode = audio_mode
        self.output_fps = output_fps  # None = orijinal
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def log(self, message):
        self.status.emit(message)

    def _wait_realesrgan(self, proc, frames_out, total_frames, stall_limit, stderr_path):
        """Real-ESRGAN bitene kadar izle; kare ilerlemesi yoksa stall_limit sonra kes.

        stderr dosyaya yazilir (PIPE + okumamak Windows'ta sureci kilitleyebilir).
        """
        last_done = 0
        last_progress_time = time.time()
        while proc.poll() is None:
            if self._cancelled:
                proc.kill()
                return False
            done = len([f for f in os.listdir(frames_out) if f.endswith(".png")])
            if done != last_done:
                last_done = done
                last_progress_time = time.time()
            elif time.time() - last_progress_time > stall_limit:
                proc.kill()
                stderr_tail = ""
                try:
                    with open(stderr_path, "r", encoding="utf-8", errors="replace") as f:
                        stderr_tail = f.read()[-800:]
                except OSError:
                    pass
                detail = f"\n{stderr_tail}" if stderr_tail.strip() else ""
                raise PipelineError(
                    f"Büyütme {done}. karede takıldı "
                    f"(~{int(stall_limit)} sn ilerleme yok; GPU/sürücü veya VRAM olabilir) - "
                    "tekrar deneyin; tekrarlanırsa 2x veya Hızlı model deneyin."
                    f"{detail}"
                )
            pct = 5 + int(90 * done / max(total_frames, 1))
            self.progress.emit(min(pct, 95))
            time.sleep(0.5)
        return True

    def _run_realesrgan_frames(self, frames_in, frames_out, model, scale, stall_limit, total_frames):
        stderr_path = os.path.join(os.path.dirname(frames_out), "realesrgan_stderr.log")
        with open(stderr_path, "w", encoding="utf-8", errors="replace") as stderr_file:
            proc = subprocess.Popen(
                [
                    REALESRGAN_EXE,
                    "-i", frames_in,
                    "-o", frames_out,
                    "-n", model,
                    "-s", str(scale),
                    "-t", "0",
                    "-f", "png",
                ],
                cwd=os.path.dirname(REALESRGAN_EXE),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=stderr_file,
                creationflags=NO_CREATE_WINDOW,
            )
            alive = self._wait_realesrgan(proc, frames_out, total_frames, stall_limit, stderr_path)

        if not alive:
            return False

        if proc.returncode != 0:
            stderr_tail = ""
            try:
                with open(stderr_path, "r", encoding="utf-8", errors="replace") as f:
                    stderr_tail = f.read()[-800:]
            except OSError:
                pass
            raise PipelineError(f"Büyütme başarısız:\n{stderr_tail}")
        return True

    def run(self):
        temp_dir = tempfile.mkdtemp(prefix="pixlift_")
        try:
            if is_image_file(self.input_path):
                self._run_image_pipeline()
            elif is_gif_file(self.input_path):
                self._run_gif_pipeline(temp_dir)
            else:
                self._run_pipeline(temp_dir)
            if self._cancelled:
                self.cancelled.emit()
        except PipelineError as e:
            if not self._cancelled:
                self.failed.emit(str(e))
        except Exception as e:  # noqa: BLE001 - kisisel arac, genel hata mesaji yeterli
            if not self._cancelled:
                self.failed.emit(f"Beklenmeyen hata: {e}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _run_image_pipeline(self):
        info = probe_image(self.input_path)
        model = BENCHMARKS[self.quality_key]["model"]
        estimated_total = max(estimate_seconds(info, self.quality_key), 1.0)

        base, ext = os.path.splitext(self.input_path)
        out_ext = image_output_format(ext)
        output_path = f"{base}_PixLift_{self.scale}x.{out_ext}"

        self.status.emit(f"Görsel büyütülüyor ({model}, {self.scale}x)...")
        self.progress.emit(5)

        start = time.time()
        stderr_path = os.path.join(tempfile.gettempdir(), f"pixlift_img_{os.getpid()}.log")
        with open(stderr_path, "w", encoding="utf-8", errors="replace") as stderr_file:
            proc = subprocess.Popen(
                [
                    REALESRGAN_EXE,
                    "-i", self.input_path,
                    "-o", output_path,
                    "-n", model,
                    "-s", str(self.scale),
                    "-t", "0",
                    "-f", out_ext,
                ],
                cwd=os.path.dirname(REALESRGAN_EXE),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=stderr_file,
                creationflags=NO_CREATE_WINDOW,
            )
            stall_limit = max(estimated_total * 4, STALL_TIMEOUT_SECONDS, STALL_TIMEOUT_MIN_SECONDS)
            while proc.poll() is None:
                if self._cancelled:
                    proc.kill()
                    return
                elapsed = time.time() - start
                if elapsed > stall_limit:
                    proc.kill()
                    raise PipelineError(
                        "Büyütme takıldı (GPU sürücü sorunu olabilir) - "
                        "tekrar deneyin veya daha küçük bir görsel kullanın."
                    )
                pct = 5 + int(90 * min(elapsed / estimated_total, 1.0))
                self.progress.emit(min(pct, 95))
                time.sleep(0.2)

        if proc.returncode != 0:
            stderr_tail = ""
            try:
                with open(stderr_path, "r", encoding="utf-8", errors="replace") as f:
                    stderr_tail = f.read()[-800:]
            except OSError:
                pass
            raise PipelineError(f"Büyütme başarısız:\n{stderr_tail}")

        self.progress.emit(100)
        self.finished_ok.emit(output_path)

    def _run_pipeline(self, temp_dir):
        info = probe_video(self.input_path)
        frames_in = os.path.join(temp_dir, "frames_in")
        frames_out = os.path.join(temp_dir, "frames_out")
        os.makedirs(frames_in, exist_ok=True)
        os.makedirs(frames_out, exist_ok=True)

        self.status.emit("Kareler çıkarılıyor...")
        self.progress.emit(1)
        result = run_hidden(
            [
                FFMPEG_EXE, "-y", "-i", self.input_path,
                "-qscale:v", "2",
                os.path.join(frames_in, "frame_%05d.png"),
            ]
        )
        if result.returncode != 0:
            raise PipelineError(f"Kare çıkarma başarısız:\n{result.stderr[-800:]}")
        if self._cancelled:
            return

        total_frames = len([f for f in os.listdir(frames_in) if f.endswith(".png")])
        if total_frames == 0:
            raise PipelineError("Hiç kare çıkarılamadı.")

        audio_path = os.path.join(temp_dir, "audio.m4a")
        audio_final = audio_path
        if info["has_audio"]:
            self.status.emit("Ses ayrılıyor...")
            result = run_hidden(
                [FFMPEG_EXE, "-y", "-i", self.input_path, "-vn", "-acodec", "copy", audio_path]
            )
            if result.returncode != 0:
                raise PipelineError(f"Ses çıkarma başarısız:\n{result.stderr[-800:]}")

            if self.audio_mode != "off":
                audio_final = os.path.join(temp_dir, "audio_boosted.m4a")
                if self.audio_mode == "auto":
                    gain = analyze_audio_gain(audio_path, self.log)
                    if gain > 0.1:
                        self.status.emit(f"Ses {gain:.1f}dB yükseltiliyor...")
                        result = run_hidden(
                            [FFMPEG_EXE, "-y", "-i", audio_path, "-af", f"volume={gain:.1f}dB", audio_final]
                        )
                        if result.returncode != 0:
                            raise PipelineError(f"Ses yükseltme başarısız:\n{result.stderr[-800:]}")
                    else:
                        audio_final = audio_path
                else:
                    mult = {"25": 1.25, "50": 1.5, "100": 2.0}.get(self.audio_mode, 1.0)
                    self.status.emit(f"Ses x{mult:.2f}...")
                    result = run_hidden(
                        [FFMPEG_EXE, "-y", "-i", audio_path, "-af", f"volume={mult}", audio_final]
                    )
                    if result.returncode != 0:
                        raise PipelineError(f"Ses yükseltme başarısız:\n{result.stderr[-800:]}")

        self.progress.emit(5)
        if self._cancelled:
            return

        model = BENCHMARKS[self.quality_key]["model"]
        stall_limit = stall_timeout_for_job(info, self.quality_key, self.scale)
        self.log(
            f"Büyütülüyor ({model}, {self.scale}x) - "
            f"kare ~{format_duration(estimate_seconds_per_frame(info, self.quality_key, self.scale))}, "
            f"takılma eşiği {int(stall_limit)} sn..."
        )
        if not self._run_realesrgan_frames(
            frames_in, frames_out, model, self.scale, stall_limit, total_frames
        ):
            return

        self.progress.emit(95)
        self.status.emit("Video yeniden birleştiriliyor...")

        base, _ = os.path.splitext(self.input_path)
        output_path = f"{base}_PixLift_{self.scale}x.mp4"

        cmd = [
            FFMPEG_EXE, "-y",
            "-framerate", str(info["fps"]),
            "-i", os.path.join(frames_out, "frame_%05d.png"),
        ]
        if info["has_audio"]:
            cmd += ["-i", audio_final]
        if self.output_fps:
            cmd += ["-vf", f"fps={self.output_fps}"]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p"]
        if info["has_audio"]:
            # fps degisince yeniden encode guvenli; boost sonrasi zaten aac olabilir
            cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
        cmd += [output_path]

        result = run_hidden(cmd)
        if result.returncode != 0:
            raise PipelineError(f"Birleştirme başarısız:\n{result.stderr[-800:]}")

        self.progress.emit(100)
        self.finished_ok.emit(output_path)

    def _run_gif_pipeline(self, temp_dir):
        info = probe_video(self.input_path)
        frames_in = os.path.join(temp_dir, "frames_in")
        frames_out = os.path.join(temp_dir, "frames_out")
        os.makedirs(frames_in, exist_ok=True)
        os.makedirs(frames_out, exist_ok=True)

        self.status.emit("Kareler çıkarılıyor...")
        self.progress.emit(1)
        result = run_hidden(
            [
                FFMPEG_EXE, "-y", "-i", self.input_path,
                "-qscale:v", "2",
                os.path.join(frames_in, "frame_%05d.png"),
            ]
        )
        if result.returncode != 0:
            raise PipelineError(f"Kare çıkarma başarısız:\n{result.stderr[-800:]}")
        if self._cancelled:
            return

        total_frames = len([f for f in os.listdir(frames_in) if f.endswith(".png")])
        if total_frames == 0:
            raise PipelineError("Hiç kare çıkarılamadı.")

        self.progress.emit(5)

        model = BENCHMARKS[self.quality_key]["model"]
        stall_limit = stall_timeout_for_job(info, self.quality_key, self.scale)
        self.log(
            f"Büyütülüyor ({model}, {self.scale}x) - "
            f"takılma eşiği {int(stall_limit)} sn..."
        )
        if not self._run_realesrgan_frames(
            frames_in, frames_out, model, self.scale, stall_limit, total_frames
        ):
            return

        self.progress.emit(95)
        self.status.emit("GIF yeniden birleştiriliyor...")

        base, _ = os.path.splitext(self.input_path)
        output_path = f"{base}_PixLift_{self.scale}x.gif"

        # Duz -pix_fmt yerine palette uretip kullanmak (256 renk sinirlamasinda)
        # buyutulmus kareler icin cok daha az bantlanma/renk bozulmasi verir.
        cmd = [
            FFMPEG_EXE, "-y",
            "-framerate", str(info["fps"]),
            "-i", os.path.join(frames_out, "frame_%05d.png"),
            "-vf", (
                f"fps={self.output_fps}," if self.output_fps else ""
            ) + "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
            "-loop", "0",
            output_path,
        ]

        result = run_hidden(cmd)
        if result.returncode != 0:
            raise PipelineError(f"Birleştirme başarısız:\n{result.stderr[-800:]}")

        self.progress.emit(100)
        self.finished_ok.emit(output_path)


class AnimatedProgressBar(QWidget):
    """Renkli, kayan gradyanli ilerleme cubugu - islemin gorsel olarak 'canli' hissettirmesi icin."""

    WAVE_COLORS = [QColor("#22D3EE"), QColor("#818CF8"), QColor("#34D399"), QColor("#22D3EE")]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._phase = 0.0
        self.setFixedHeight(16)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)

    def setValue(self, value):
        self._value = max(0, min(100, value))
        self.update()

    def _tick(self):
        if self._value <= 0 or self._value >= 100:
            return
        self._phase = (self._phase + 0.012) % 1.0
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#00000022"))
        painter.drawRoundedRect(rect, radius, radius)

        if self._value <= 0:
            return

        filled_width = rect.width() * (self._value / 100)
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.setClipPath(path)

        gradient = QLinearGradient(0, 0, rect.width(), 0)
        stops = len(self.WAVE_COLORS)
        for i, color in enumerate(self.WAVE_COLORS):
            pos = (i / (stops - 1) + self._phase) % 1.0
            gradient.setColorAt(pos, color)
        # Bar'in tam kenarlarinin (0.0/1.0) her zaman bir renkle kapli olmasini garantile.
        gradient.setColorAt(0.0, self.WAVE_COLORS[0])
        gradient.setColorAt(1.0, self.WAVE_COLORS[-1])

        painter.setBrush(QBrush(gradient))
        painter.drawRect(QRectF(0, 0, filled_width, rect.height()))

        painter.setClipping(False)
        painter.setPen(QColor("#ffffff"))
        font = QFont()
        font.setPixelSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, f"%{self._value}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PixLift")
        self.setMinimumWidth(640)
        self.setAcceptDrops(True)

        cfg = load_config()
        self.language = cfg["language"]
        self.theme = cfg["theme"]

        self.input_path = None
        self.video_info = None
        self.is_image = False
        self.is_gif = False
        self.worker = None
        self.output_path = None
        self.apply_theme()

        self.process_start_time = None
        self.estimated_total_seconds = 0
        self.current_progress_pct = 0
        self.eta_timer = QTimer(self)
        self.eta_timer.timeout.connect(self.update_eta)

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        self.title_label = QLabel("PixLift")
        self.title_label.setObjectName("titleLabel")
        title_row.addWidget(self.title_label)
        title_row.addStretch()

        self.lang_btn = QPushButton()
        self.lang_btn.setObjectName("themeButton")
        self.lang_btn.setFixedSize(40, 40)
        self.lang_btn.setCursor(Qt.PointingHandCursor)
        self.lang_btn.clicked.connect(self.toggle_language)
        title_row.addWidget(self.lang_btn)

        self.theme_btn = QPushButton()
        self.theme_btn.setObjectName("themeButton")
        self.theme_btn.setFixedSize(40, 40)
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.clicked.connect(self.toggle_theme)
        title_row.addWidget(self.theme_btn)
        layout.addLayout(title_row)
        layout.addSpacing(6)

        self.file_label = QLabel()
        self.file_label.setObjectName("dropZone")
        self.file_label.setProperty("hasFile", False)
        self.file_label.setProperty("dragOver", False)
        self.file_label.setWordWrap(True)
        self.file_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.file_label)

        self.browse_btn = QPushButton()
        self.browse_btn.clicked.connect(self.browse_file)
        layout.addWidget(self.browse_btn)

        self.info_label = QLabel("")
        self.info_label.setObjectName("infoLabel")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        sections_row = QHBoxLayout()
        sections_row.setSpacing(10)

        scale_card = QFrame()
        scale_card.setObjectName("card")
        scale_layout = QHBoxLayout(scale_card)
        self.scale_2x = QRadioButton("2x")
        self.scale_3x = QRadioButton("3x")
        self.scale_2x.setChecked(True)
        self.scale_group = QButtonGroup(self)
        self.scale_group.addButton(self.scale_2x)
        self.scale_group.addButton(self.scale_3x)
        scale_layout.addWidget(self.scale_2x)
        scale_layout.addWidget(self.scale_3x)
        scale_col, self.scale_title = self._column("", scale_card, return_title=True)
        sections_row.addLayout(scale_col)

        model_card = QFrame()
        model_card.setObjectName("card")
        model_layout = QVBoxLayout(model_card)
        self.model_hd = QRadioButton()
        self.model_4k = QRadioButton()
        self.model_hd.setChecked(True)
        self.model_group = QButtonGroup(self)
        self.model_group.addButton(self.model_hd)
        self.model_group.addButton(self.model_4k)
        model_layout.addWidget(self.model_hd)
        model_layout.addWidget(self.model_4k)
        model_col, self.model_title = self._column("", model_card, return_title=True)
        sections_row.addLayout(model_col)

        self.audio_card = QFrame()
        self.audio_card.setObjectName("card")
        audio_layout = QVBoxLayout(self.audio_card)
        self.audio_off = QRadioButton()
        self.audio_auto = QRadioButton()
        self.audio_25 = QRadioButton()
        self.audio_50 = QRadioButton()
        self.audio_100 = QRadioButton()
        self.audio_auto.setChecked(True)
        self.audio_group = QButtonGroup(self)
        for btn in (self.audio_off, self.audio_auto, self.audio_25, self.audio_50, self.audio_100):
            self.audio_group.addButton(btn)
            audio_layout.addWidget(btn)
        audio_col, self.audio_title = self._column("", self.audio_card, return_title=True)
        sections_row.addLayout(audio_col)

        self.fps_card = QFrame()
        self.fps_card.setObjectName("card")
        fps_layout = QVBoxLayout(self.fps_card)
        self.fps_original = QRadioButton()
        self.fps_30 = QRadioButton()
        self.fps_60 = QRadioButton()
        self.fps_original.setChecked(True)
        self.fps_group = QButtonGroup(self)
        for btn in (self.fps_original, self.fps_30, self.fps_60):
            self.fps_group.addButton(btn)
            fps_layout.addWidget(btn)
        fps_col, self.fps_title = self._column("", self.fps_card, return_title=True)
        sections_row.addLayout(fps_col)

        layout.addLayout(sections_row)

        for btn in (self.scale_2x, self.scale_3x, self.model_hd, self.model_4k):
            btn.toggled.connect(self.update_hint)

        self.hint_label = QLabel("")
        self.hint_label.setObjectName("hintLabel")
        self.hint_label.setWordWrap(True)
        self.hint_label.setTextFormat(Qt.RichText)
        layout.addWidget(self.hint_label)

        layout.addSpacing(4)
        run_row = QHBoxLayout()
        self.run_btn = QPushButton()
        self.run_btn.setObjectName("runButton")
        self.run_btn.setEnabled(False)
        self.run_btn.setMinimumHeight(38)
        self.run_btn.clicked.connect(self.start_processing)
        run_row.addWidget(self.run_btn)

        self.stop_btn = QPushButton()
        self.stop_btn.setObjectName("stopButton")
        self.stop_btn.setMinimumHeight(38)
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self.stop_processing)
        run_row.addWidget(self.stop_btn)
        layout.addLayout(run_row)

        self.progress_bar = AnimatedProgressBar()
        layout.addWidget(self.progress_bar)

        self.eta_label = QLabel("")
        self.eta_label.setObjectName("etaLabel")
        self.eta_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.eta_label)

        result_row = QHBoxLayout()
        self.open_folder_btn = QPushButton()
        self.open_folder_btn.setVisible(False)
        self.open_folder_btn.clicked.connect(self.open_output_folder)
        self.play_btn = QPushButton()
        self.play_btn.setVisible(False)
        self.play_btn.clicked.connect(self.play_output)
        result_row.addWidget(self.open_folder_btn)
        result_row.addWidget(self.play_btn)
        layout.addLayout(result_row)

        self.setCentralWidget(root)
        self.retranslate_ui()

    def t(self, key):
        return STRINGS.get(self.language, STRINGS["tr"]).get(key, key)

    def retranslate_ui(self):
        has_file = bool(self.input_path)
        if not has_file:
            self.file_label.setText(self.t("drop_empty"))
        self.browse_btn.setText(self.t("browse"))
        self.scale_title.setText(self.t("section_scale"))
        self.model_title.setText(self.t("section_model"))
        self.audio_title.setText(self.t("section_audio"))
        self.fps_title.setText(self.t("section_fps"))
        self.model_hd.setText(self.t("model_hd"))
        self.model_4k.setText(self.t("model_4k"))
        self.model_hd.setToolTip(self.t("model_hd_tip"))
        self.model_4k.setToolTip(self.t("model_4k_tip"))
        self.audio_off.setText(self.t("audio_off"))
        self.audio_auto.setText(self.t("audio_auto"))
        self.audio_25.setText(self.t("audio_25"))
        self.audio_50.setText(self.t("audio_50"))
        self.audio_100.setText(self.t("audio_100"))
        tip = self.t("audio_tip")
        for btn in (self.audio_off, self.audio_auto, self.audio_25, self.audio_50, self.audio_100):
            btn.setToolTip(tip)
        self.fps_original.setText(self.t("fps_original"))
        self.fps_30.setText(self.t("fps_30"))
        self.fps_60.setText(self.t("fps_60"))
        fps_tip = self.t("fps_tip")
        for btn in (self.fps_original, self.fps_30, self.fps_60):
            btn.setToolTip(fps_tip)
        self.run_btn.setText(self.t("run"))
        self.stop_btn.setText(self.t("stop"))
        self.open_folder_btn.setText(self.t("open_folder"))
        self.lang_btn.setText("EN" if self.language == "tr" else "TR")
        self.lang_btn.setToolTip(self.t("lang_tip"))
        self.update_theme_button()
        if self.video_info:
            self._refresh_info_label()
            self.update_hint()
        if self.play_btn.isVisible():
            self._refresh_play_btn_text()

    def toggle_language(self):
        self.language = "en" if self.language == "tr" else "tr"
        save_config(language=self.language)
        self.retranslate_ui()

    # --- Tema ---

    def apply_theme(self):
        QApplication.instance().setStyleSheet(build_stylesheet(self.theme))

    def update_theme_button(self):
        self.theme_btn.setText("☀" if self.theme == "dark" else "\U0001F319")
        self.theme_btn.setToolTip(
            self.t("theme_to_light") if self.theme == "dark" else self.t("theme_to_dark")
        )

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.apply_theme()
        self.update_theme_button()
        save_theme_preference(self.theme)

    # --- Dosya secimi ---

    def _section_title(self, text):
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    def _column(self, title_text, card, return_title=False):
        col = QVBoxLayout()
        col.setSpacing(6)
        title = self._section_title(title_text)
        col.addWidget(title)
        col.addWidget(card)
        return (col, title) if return_title else col

    def _set_drop_zone_property(self, name, value):
        self.file_label.setProperty(name, value)
        self.file_label.style().unpolish(self.file_label)
        self.file_label.style().polish(self.file_label)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_drop_zone_property("dragOver", True)

    def dragLeaveEvent(self, event):
        self._set_drop_zone_property("dragOver", False)

    def dropEvent(self, event: QDropEvent):
        self._set_drop_zone_property("dragOver", False)
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path.lower().endswith(ALL_EXTENSIONS):
                self.load_file(path)

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.t("browse_title"),
            "",
            self.t("browse_filter"),
        )
        if path:
            self.load_file(path)

    def _refresh_info_label(self):
        info = self.video_info
        if not info:
            return
        if self.is_image:
            self.info_label.setText(
                f"{info['width']}x{info['height']} | "
                f"{info['file_size'] / 1024:.0f} KB | {self.t('photo')}"
            )
        else:
            kind_label = "GIF" if self.is_gif else f"{info['bitrate'] / 1000:.0f} kbps"
            self.info_label.setText(
                f"{info['width']}x{info['height']} | {info['fps']:.2f} fps | "
                f"{info['duration']:.1f} sn | {info['frame_count']} kare | {kind_label}"
            )

    def load_file(self, path):
        self.is_image = is_image_file(path)
        self.is_gif = is_gif_file(path)
        try:
            self.video_info = probe_image(path) if self.is_image else probe_video(path)
        except Exception as e:  # noqa: BLE001
            kind = self.t("kind_image") if self.is_image else self.t("kind_video")
            QMessageBox.critical(self, self.t("error_title"), f"{kind} {self.t('read_fail')}:\n{e}")
            return

        self.input_path = path
        self.file_label.setText(os.path.basename(path))
        self._set_drop_zone_property("hasFile", True)
        self._refresh_info_label()

        show_av = not self.is_image and not self.is_gif
        self.audio_title.setVisible(show_av)
        self.audio_card.setVisible(show_av)
        self.fps_title.setVisible(not self.is_image)
        self.fps_card.setVisible(not self.is_image)

        self.run_btn.setEnabled(True)
        self.update_hint()

    # --- Tahmin / uyari metni ---

    def update_hint(self):
        if not self.video_info:
            return
        quality_key = "quality" if self.model_4k.isChecked() else "fast"
        scale = 3 if self.scale_3x.isChecked() else 2
        seconds = estimate_seconds(self.video_info, quality_key)
        text = f"{self.t('eta_prefix')} {format_duration(seconds)}"

        if quality_key == "fast" and scale == 3 and low_bitrate_risk(self.video_info):
            text += self.t("warn_bitrate")
        self.hint_label.setText(text)

    def _selected_audio_mode(self):
        if self.audio_off.isChecked():
            return "off"
        if self.audio_25.isChecked():
            return "25"
        if self.audio_50.isChecked():
            return "50"
        if self.audio_100.isChecked():
            return "100"
        return "auto"

    def _selected_output_fps(self):
        if self.fps_30.isChecked():
            return 30
        if self.fps_60.isChecked():
            return 60
        return None

    def _preference_widgets(self):
        return (
            self.browse_btn,
            self.scale_2x,
            self.scale_3x,
            self.model_hd,
            self.model_4k,
            self.audio_off,
            self.audio_auto,
            self.audio_25,
            self.audio_50,
            self.audio_100,
            self.fps_original,
            self.fps_30,
            self.fps_60,
            self.lang_btn,
            self.theme_btn,
        )

    def _set_controls_busy(self, busy):
        """Uretim sirasinda tercihleri ve dosya secimini kilitle."""
        enabled = not busy
        for w in self._preference_widgets():
            w.setEnabled(enabled)
        self.setAcceptDrops(enabled)
        # Ses/FPS kartlari gizliyse de widget state tutarli kalsin
        if not busy and self.input_path:
            show_av = not self.is_image and not self.is_gif
            self.audio_card.setEnabled(show_av)
            for btn in (self.audio_off, self.audio_auto, self.audio_25, self.audio_50, self.audio_100):
                btn.setEnabled(show_av)
            show_fps = not self.is_image
            self.fps_card.setEnabled(show_fps)
            for btn in (self.fps_original, self.fps_30, self.fps_60):
                btn.setEnabled(show_fps)

    # --- Isleme ---

    def start_processing(self):
        scale = 3 if self.scale_3x.isChecked() else 2
        quality_key = "quality" if self.model_4k.isChecked() else "fast"
        audio_mode = self._selected_audio_mode() if not self.is_image and not self.is_gif else "off"
        output_fps = None if self.is_image else self._selected_output_fps()

        self.run_btn.setEnabled(False)
        self.stop_btn.setVisible(True)
        self.stop_btn.setEnabled(True)
        self.open_folder_btn.setVisible(False)
        self.play_btn.setVisible(False)
        self.progress_bar.setValue(0)
        self.eta_label.setText("")
        self._set_controls_busy(True)

        self.estimated_total_seconds = estimate_seconds(self.video_info, quality_key)
        self.process_start_time = time.time()
        self.current_progress_pct = 0
        self.update_eta()
        self.eta_timer.start(1000)

        self.worker = UpscaleWorker(
            self.input_path,
            scale,
            quality_key,
            audio_mode=audio_mode,
            output_fps=output_fps,
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_ok.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.cancelled.connect(self.on_cancelled)
        self.worker.start()

    def stop_processing(self):
        if self.worker:
            self.worker.cancel()
        self.stop_btn.setEnabled(False)
        self.eta_label.setText(self.t("stopping"))

    def on_progress(self, pct):
        self.current_progress_pct = pct
        self.progress_bar.setValue(pct)

    def update_eta(self):
        elapsed = time.time() - self.process_start_time
        if self.current_progress_pct >= 3:
            remaining = elapsed / self.current_progress_pct * (100 - self.current_progress_pct)
        else:
            remaining = self.estimated_total_seconds - elapsed
        remaining = max(0, remaining)
        minutes, seconds = divmod(int(round(remaining)), 60)
        self.eta_label.setText(f"{self.t('remaining')} ~{minutes:02d}:{seconds:02d}")

    def _refresh_play_btn_text(self):
        if self.is_image:
            self.play_btn.setText(self.t("play_photo"))
        elif self.is_gif:
            self.play_btn.setText(self.t("play_gif"))
        else:
            self.play_btn.setText(self.t("play_video"))

    def on_finished(self, output_path):
        self.eta_timer.stop()
        self.output_path = output_path
        self.eta_label.setText(self.t("done"))
        self.run_btn.setEnabled(True)
        self.stop_btn.setVisible(False)
        self.open_folder_btn.setVisible(True)
        self._refresh_play_btn_text()
        self.play_btn.setVisible(True)
        self._set_controls_busy(False)
        play_completion_sound()

    def on_failed(self, message):
        self.eta_timer.stop()
        self.eta_label.setText(self.t("error_occurred"))
        self.run_btn.setEnabled(True)
        self.stop_btn.setVisible(False)
        self._set_controls_busy(False)
        QMessageBox.critical(self, self.t("error_title"), message)

    def on_cancelled(self):
        self.eta_timer.stop()
        self.eta_label.setText(self.t("stopped"))
        self.progress_bar.setValue(0)
        self.run_btn.setEnabled(True)
        self.stop_btn.setVisible(False)
        self._set_controls_busy(False)

    def open_output_folder(self):
        if self.output_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self.output_path)))

    def play_output(self):
        if self.output_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_path))


def main():
    missing = check_tools_available()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    lang = load_config()["language"]
    strings = STRINGS.get(lang, STRINGS["tr"])
    if missing:
        QMessageBox.critical(
            None,
            strings["missing_title"],
            strings["missing_body"] + "\n".join(missing),
        )
        sys.exit(1)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
