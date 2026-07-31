"""Kullanici tercihleri (tema/dil), i18n metinleri ve tamamlanma sesi."""

import json
import os
import tempfile

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
        "model_hd_tip": "Hızlı model (animevideov3) — video 2x/3x native; foto her zaman 4x",
        "model_4k_tip": "Yüksek detay (x4plus) — foto 4x native; videoda 4x sonrası 2x/3x'e indirilir",
        "scale_photo_tip": "Fotoğraflar her zaman 4x büyütülür (model native ölçeği)",
        "scale_video_tip": "Video / GIF için 2x veya 3x",
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
        "warning_title": "Uyarı",
        "audio_dropped_warning": "Ses birleştirilemedi; video sessiz olarak kaydedildi.",
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
        "clear_file": "Dosyayı kaldır",
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
        "model_hd_tip": "Fast model (animevideov3) — native 2x/3x for video; photos always 4x",
        "model_4k_tip": "High detail (x4plus) — photos at native 4x; video runs 4x then downscales to 2x/3x",
        "scale_photo_tip": "Photos always upscale at 4x (model native scale)",
        "scale_video_tip": "2x or 3x for video / GIF",
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
        "warning_title": "Warning",
        "audio_dropped_warning": "Audio could not be merged; video was saved without sound.",
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
        "clear_file": "Clear file",
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
