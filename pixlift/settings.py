"""Kullanici tercihleri (tema/dil), i18n metinleri ve tamamlanma sesi."""

import json
import os
import tempfile

ACCENT = {"dark": "#FBBF24", "light": "#B45309"}
DEFAULT_THEME = "dark"
DEFAULT_LANGUAGE = "tr"
DEFAULT_SCALE = 2
DEFAULT_MODEL = "fast"
DEFAULT_AUDIO_MODE = "auto"
DEFAULT_FPS = 0  # 0 = orijinal ("original") - None kullanilmiyor, cunku
# save_config'in "None -> degistirme" filtresi gercek bir fps=None guncellemesini
# sessizce yutar.
VALID_SCALES = (2, 3)
VALID_MODELS = ("fast", "quality")
VALID_AUDIO_MODES = ("off", "auto", "25", "50", "100")
VALID_FPS = (0, 30, 60)
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
        "unit_sec": "sn",
        "unit_min": "dk",
        "unit_hr": "saat",
        "w_extracting_frames": "Kareler çıkarılıyor...",
        "w_extract_frames_failed": "Kare çıkarma başarısız",
        "w_no_frames": "Hiç kare çıkarılamadı.",
        "w_separating_audio": "Ses ayrılıyor...",
        "w_extract_audio_failed": "Ses çıkarma başarısız",
        "w_boosting_audio_gain": "Ses {gain:.1f}dB yükseltiliyor...",
        "w_boosting_audio_mult": "Ses x{mult:.2f}...",
        "w_boost_audio_failed": "Ses yükseltme başarısız",
        "w_upscaling_video": (
            "Büyütülüyor ({model}, {scale_note}) - "
            "kare ~{per_frame}, takılma eşiği {stall} sn..."
        ),
        "w_upscaling_gif": "Büyütülüyor ({model}, {scale_note}) - takılma eşiği {stall} sn...",
        "w_stall_video": (
            "Büyütme {done}. karede takıldı "
            "(~{stall} sn ilerleme yok; GPU/sürücü veya VRAM olabilir) - "
            "tekrar deneyin; tekrarlanırsa 2x veya Hızlı model deneyin."
        ),
        "w_upscale_failed": "Büyütme başarısız",
        "w_merging_video": "Video yeniden birleştiriliyor...",
        "w_merge_failed": "Birleştirme başarısız",
        "w_upscaling_photo": "Görsel büyütülüyor ({model}, {scale_note})...",
        "w_stall_photo": (
            "Büyütme takıldı (GPU sürücü sorunu olabilir) - "
            "tekrar deneyin veya daha küçük bir görsel kullanın."
        ),
        "w_downscaling_photo": "Hedef boyuta indiriliyor ({scale}x)...",
        "w_resize_failed": "Boyut ayarı başarısız",
        "w_merging_gif": "GIF yeniden birleştiriliyor...",
        "w_unexpected_error": "Beklenmeyen hata: {error}",
        "queue_pending": "Bekliyor",
        "queue_processing": "İşleniyor",
        "queue_done": "Tamam",
        "queue_failed": "Hata",
        "queue_cancelled": "İptal",
        "queue_files_selected": "{count} dosya seçildi",
        "queue_status_label": "İşleniyor: {current}/{total}",
        "queue_summary": "{done}/{total} tamamlandı, {failed} hata.",
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
        "unit_sec": "sec",
        "unit_min": "min",
        "unit_hr": "hr",
        "w_extracting_frames": "Extracting frames...",
        "w_extract_frames_failed": "Frame extraction failed",
        "w_no_frames": "No frames were extracted.",
        "w_separating_audio": "Extracting audio...",
        "w_extract_audio_failed": "Audio extraction failed",
        "w_boosting_audio_gain": "Boosting audio by {gain:.1f}dB...",
        "w_boosting_audio_mult": "Audio x{mult:.2f}...",
        "w_boost_audio_failed": "Audio boost failed",
        "w_upscaling_video": (
            "Upscaling ({model}, {scale_note}) - "
            "frame ~{per_frame}, stall threshold {stall}s..."
        ),
        "w_upscaling_gif": "Upscaling ({model}, {scale_note}) - stall threshold {stall}s...",
        "w_stall_video": (
            "Upscale stalled at frame {done} "
            "(~{stall}s with no progress; could be a GPU driver or VRAM issue) - "
            "try again; if it repeats, try 2x or the Fast model."
        ),
        "w_upscale_failed": "Upscale failed",
        "w_merging_video": "Re-merging video...",
        "w_merge_failed": "Merge failed",
        "w_upscaling_photo": "Upscaling photo ({model}, {scale_note})...",
        "w_stall_photo": (
            "Upscale stalled (could be a GPU driver issue) - "
            "try again or use a smaller image."
        ),
        "w_downscaling_photo": "Downscaling to target size ({scale}x)...",
        "w_resize_failed": "Resize failed",
        "w_merging_gif": "Re-merging GIF...",
        "w_unexpected_error": "Unexpected error: {error}",
        "queue_pending": "Pending",
        "queue_processing": "Processing",
        "queue_done": "Done",
        "queue_failed": "Failed",
        "queue_cancelled": "Cancelled",
        "queue_files_selected": "{count} files selected",
        "queue_status_label": "Processing: {current}/{total}",
        "queue_summary": "{done}/{total} completed, {failed} failed.",
    },
}


def load_config():
    data = {
        "theme": DEFAULT_THEME,
        "language": DEFAULT_LANGUAGE,
        "scale": DEFAULT_SCALE,
        "model": DEFAULT_MODEL,
        "audio_mode": DEFAULT_AUDIO_MODE,
        "fps": DEFAULT_FPS,
    }
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if saved.get("theme") in ACCENT:
            data["theme"] = saved["theme"]
        if saved.get("language") in STRINGS:
            data["language"] = saved["language"]
        if saved.get("scale") in VALID_SCALES:
            data["scale"] = saved["scale"]
        if saved.get("model") in VALID_MODELS:
            data["model"] = saved["model"]
        if saved.get("audio_mode") in VALID_AUDIO_MODES:
            data["audio_mode"] = saved["audio_mode"]
        if saved.get("fps") in VALID_FPS:
            data["fps"] = saved["fps"]
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
