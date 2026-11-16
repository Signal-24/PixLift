"""Ana pencere (PySide6 UI) ve uygulama girisi."""

import os
import sys
import time

from PySide6.QtCore import QBuffer, QIODevice, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from . import icons
from .media import (
    ALL_EXTENSIONS,
    estimate_seconds,
    format_duration,
    is_gif_file,
    is_image_file,
    low_bitrate_risk,
    probe_image,
    probe_video,
)
from .settings import (
    STRINGS,
    load_config,
    play_completion_sound,
    save_config,
    save_theme_preference,
)
from .theme import accent_color, build_stylesheet, icon_color, muted_icon_color
from .tools import check_tools_available
from .widgets import AnimatedProgressBar
from .worker import UpscaleWorker

_CHIP_TEXT_COLOR = "#2b1400"
_STOP_COLOR = "#ef4444"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PixLift")
        self.setMinimumSize(640, 760)
        self.setAcceptDrops(True)

        cfg = load_config()
        self.language = cfg["language"]
        self.theme = cfg["theme"]

        self.queue = []  # [{"path", "info", "status", "output", "error", "warning"}, ...]
        self.queue_pos = 0
        self._queue_running = False
        self.worker = None
        self._retired_workers = []  # bitmemis eski worker'lar (QThread cop toplayiciya kaptirilmasin)
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
        title_row.setSpacing(10)
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(34, 34)
        title_row.addWidget(self.logo_label)
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
        self.theme_btn.setIconSize(QSize(19, 19))
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.clicked.connect(self.toggle_theme)
        title_row.addWidget(self.theme_btn)
        layout.addLayout(title_row)
        layout.addSpacing(6)

        self.drop_frame = QFrame()
        self.drop_frame.setObjectName("dropZoneFrame")
        drop_grid = QGridLayout(self.drop_frame)
        drop_grid.setContentsMargins(0, 0, 0, 0)
        drop_grid.setSpacing(0)

        self.file_label = QLabel()
        self.file_label.setObjectName("dropZone")
        self.file_label.setProperty("hasFile", False)
        self.file_label.setProperty("dragOver", False)
        self.file_label.setWordWrap(True)
        self.file_label.setAlignment(Qt.AlignCenter)
        self.file_label.setMinimumHeight(88)
        drop_grid.addWidget(self.file_label, 0, 0)

        self.clear_btn = QPushButton()
        self.clear_btn.setObjectName("clearFileButton")
        self.clear_btn.setIconSize(QSize(13, 13))
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setVisible(False)
        self.clear_btn.clicked.connect(self.clear_file)
        drop_grid.addWidget(self.clear_btn, 0, 0, Qt.AlignTop | Qt.AlignRight)
        layout.addWidget(self.drop_frame)

        self.browse_btn = QPushButton()
        self.browse_btn.clicked.connect(self.browse_file)
        layout.addWidget(self.browse_btn)

        self.info_label = QLabel("")
        self.info_label.setObjectName("infoLabel")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.queue_list = QListWidget()
        self.queue_list.setObjectName("queueList")
        self.queue_list.setMaximumHeight(140)
        self.queue_list.setVisible(False)
        layout.addWidget(self.queue_list)

        self._section_icons = []
        sections_row = QHBoxLayout()
        sections_row.setSpacing(10)

        scale_card = QFrame()
        scale_card.setObjectName("card")
        scale_layout = QHBoxLayout(scale_card)
        self.scale_2x = QRadioButton("2x")
        self.scale_3x = QRadioButton("3x")
        self.scale_4x = QRadioButton("4x")
        for btn in (self.scale_2x, self.scale_3x, self.scale_4x):
            btn.setObjectName("choiceChip")
        self.scale_2x.setChecked(True)
        self.scale_group = QButtonGroup(self)
        self.scale_group.addButton(self.scale_2x)
        self.scale_group.addButton(self.scale_3x)
        self.scale_group.addButton(self.scale_4x)
        scale_layout.addWidget(self.scale_2x)
        scale_layout.addWidget(self.scale_3x)
        scale_layout.addWidget(self.scale_4x)
        self.scale_4x.setVisible(False)
        scale_col, self.scale_header, self.scale_title = self._column(icons.resize_icon, scale_card)
        sections_row.addLayout(scale_col)

        model_card = QFrame()
        model_card.setObjectName("card")
        model_layout = QVBoxLayout(model_card)
        self.model_hd = QRadioButton()
        self.model_4k = QRadioButton()
        for btn in (self.model_hd, self.model_4k):
            btn.setObjectName("choiceChip")
        self.model_hd.setChecked(True)
        self.model_group = QButtonGroup(self)
        self.model_group.addButton(self.model_hd)
        self.model_group.addButton(self.model_4k)
        model_layout.addWidget(self.model_hd)
        model_layout.addWidget(self.model_4k)
        model_col, self.model_header, self.model_title = self._column(icons.spark_icon, model_card)
        sections_row.addLayout(model_col)

        self.audio_card = QFrame()
        self.audio_card.setObjectName("card")
        audio_layout = QVBoxLayout(self.audio_card)
        audio_layout.setSpacing(3)
        self.audio_off = QRadioButton()
        self.audio_auto = QRadioButton()
        self.audio_25 = QRadioButton()
        self.audio_50 = QRadioButton()
        self.audio_100 = QRadioButton()
        self.audio_auto.setChecked(True)
        self.audio_group = QButtonGroup(self)
        for btn in (self.audio_off, self.audio_auto, self.audio_25, self.audio_50, self.audio_100):
            btn.setObjectName("choiceChip")
            self.audio_group.addButton(btn)
            audio_layout.addWidget(btn)
        audio_col, self.audio_header, self.audio_title = self._column(icons.speaker_icon, self.audio_card)
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
            btn.setObjectName("choiceChip")
            self.fps_group.addButton(btn)
            fps_layout.addWidget(btn)
        fps_col, self.fps_header, self.fps_title = self._column(icons.clock_icon, self.fps_card)
        sections_row.addLayout(fps_col)

        self._apply_saved_preferences(cfg)
        layout.addLayout(sections_row)

        for btn in (self.scale_2x, self.scale_3x, self.scale_4x, self.model_hd, self.model_4k):
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
        self.run_btn.setIconSize(QSize(15, 15))
        self.run_btn.setEnabled(False)
        self.run_btn.setMinimumHeight(38)
        self.run_btn.clicked.connect(self.start_processing)
        run_row.addWidget(self.run_btn)

        self.stop_btn = QPushButton()
        self.stop_btn.setObjectName("stopButton")
        self.stop_btn.setIconSize(QSize(15, 15))
        self.stop_btn.setMinimumHeight(38)
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self.stop_processing)
        run_row.addWidget(self.stop_btn)
        layout.addLayout(run_row)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress_bar = AnimatedProgressBar()
        layout.addWidget(self.progress_bar)

        self.eta_label = QLabel("")
        self.eta_label.setObjectName("etaLabel")
        self.eta_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.eta_label)

        result_row = QHBoxLayout()
        self.open_folder_btn = QPushButton()
        self.open_folder_btn.setIconSize(QSize(15, 15))
        self.open_folder_btn.setVisible(False)
        self.open_folder_btn.clicked.connect(self.open_output_folder)
        self.play_btn = QPushButton()
        self.play_btn.setIconSize(QSize(15, 15))
        self.play_btn.setVisible(False)
        self.play_btn.clicked.connect(self.play_output)
        result_row.addWidget(self.open_folder_btn)
        result_row.addWidget(self.play_btn)
        layout.addLayout(result_row)

        self.setCentralWidget(root)
        self.retranslate_ui()
        self._apply_icons()

    def _apply_saved_preferences(self, cfg):
        """Onceki oturumdan kaydedilen olcek/model/ses/fps tercihlerini uygula."""
        if cfg["scale"] == 3:
            self.scale_3x.setChecked(True)
        if cfg["model"] == "quality":
            self.model_4k.setChecked(True)
        audio_btn = {
            "off": self.audio_off,
            "auto": self.audio_auto,
            "25": self.audio_25,
            "50": self.audio_50,
            "100": self.audio_100,
        }.get(cfg["audio_mode"])
        if audio_btn:
            audio_btn.setChecked(True)
        fps_btn = {0: self.fps_original, 30: self.fps_30, 60: self.fps_60}.get(cfg["fps"])
        if fps_btn:
            fps_btn.setChecked(True)

    def _apply_icons(self):
        """Tema/renklere bagli tum ikonlari (yeniden) ciz - baslangicta ve tema degisiminde."""
        ic = icon_color(self.theme)
        muted = muted_icon_color(self.theme)
        acc = accent_color(self.theme)
        chip_text = QColor(_CHIP_TEXT_COLOR)

        self.logo_label.setPixmap(icons.logo_pixmap(acc, chip_text, 34))
        self.theme_btn.setIcon(icons.sun_icon(ic, 19) if self.theme == "dark" else icons.moon_icon(ic, 19))
        self.clear_btn.setIcon(icons.x_icon(muted, 13))
        self.run_btn.setIcon(icons.play_icon(chip_text, 15))
        self.stop_btn.setIcon(icons.stop_icon(QColor(_STOP_COLOR), 15))
        self.open_folder_btn.setIcon(icons.folder_icon(ic, 16))
        self.play_btn.setIcon(icons.play_icon(ic, 15))

        for icon_label, icon_fn in self._section_icons:
            icon_label.setPixmap(icon_fn(muted, 14).pixmap(14, 14))

        if not self.queue:
            self._set_drop_empty_html()

    def _set_drop_empty_html(self):
        pm = icons.upload_icon(muted_icon_color(self.theme), 40).pixmap(40, 40)
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        pm.save(buf, "PNG")
        b64 = bytes(buf.data().toBase64()).decode("ascii")
        text = self.t("drop_empty").replace("\n", "<br>")
        self.file_label.setText(
            f"<div align='center'><img src='data:image/png;base64,{b64}'><br><br>{text}</div>"
        )

    def t(self, key, **kwargs):
        template = STRINGS.get(self.language, STRINGS["tr"]).get(key, key)
        return template.format(**kwargs) if kwargs else template

    def retranslate_ui(self):
        has_file = bool(self.queue)
        if not has_file:
            self._set_drop_empty_html()
        self.browse_btn.setText(self.t("browse"))
        self.clear_btn.setToolTip(self.t("clear_file"))
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
        if self.queue:
            self._refresh_file_display()
            self._update_scale_options()
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
        self.theme_btn.setToolTip(
            self.t("theme_to_light") if self.theme == "dark" else self.t("theme_to_dark")
        )

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.apply_theme()
        self.update_theme_button()
        self._apply_icons()
        save_theme_preference(self.theme)

    # --- Dosya secimi ---

    def _column(self, icon_fn, card):
        col = QVBoxLayout()
        col.setSpacing(6)
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(5)
        icon_label = QLabel()
        icon_label.setFixedSize(14, 14)
        title = QLabel("")
        title.setObjectName("sectionTitle")
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title)
        header_layout.addStretch()
        col.addWidget(header)
        col.addWidget(card)
        self._section_icons.append((icon_label, icon_fn))
        return col, header, title

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
        paths = [u.toLocalFile() for u in urls if u.toLocalFile().lower().endswith(ALL_EXTENSIONS)]
        if paths:
            self.load_files(paths)

    def browse_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            self.t("browse_title"),
            "",
            self.t("browse_filter"),
        )
        if paths:
            self.load_files(paths)

    def _refresh_info_label(self):
        """Tek dosya modunda boyut/sure bilgisini goster (kuyruk >1 iken kullanilmaz)."""
        if not self.queue:
            return
        item = self.queue[0]
        info = item["info"]
        if info is None:
            return
        path = item["path"]
        if is_image_file(path):
            self.info_label.setText(
                f"{info['width']}x{info['height']} | "
                f"{info['file_size'] / 1024:.0f} KB | {self.t('photo')}"
            )
        else:
            kind_label = "GIF" if is_gif_file(path) else f"{info['bitrate'] / 1000:.0f} kbps"
            self.info_label.setText(
                f"{info['width']}x{info['height']} | {info['fps']:.2f} fps | "
                f"{info['duration']:.1f} sn | {info['frame_count']} kare | {kind_label}"
            )

    def _refresh_queue_list(self):
        status_key = {
            "pending": "queue_pending",
            "processing": "queue_processing",
            "done": "queue_done",
            "failed": "queue_failed",
            "cancelled": "queue_cancelled",
        }
        self.queue_list.clear()
        for item in self.queue:
            label = f"{os.path.basename(item['path'])} — {self.t(status_key[item['status']])}"
            if item.get("warning"):
                label += " ⚠"
            self.queue_list.addItem(label)

    def _refresh_file_display(self):
        count = len(self.queue)
        if count == 0:
            self._set_drop_empty_html()
            self._set_drop_zone_property("hasFile", False)
            self.clear_btn.setVisible(False)
            self.queue_list.setVisible(False)
            self.info_label.setText("")
            return

        self._set_drop_zone_property("hasFile", True)
        self.clear_btn.setVisible(True)

        if count == 1:
            self.file_label.setText(os.path.basename(self.queue[0]["path"]))
            self.queue_list.setVisible(False)
            self._refresh_info_label()
            return

        self.file_label.setText(self.t("queue_files_selected", count=count))
        self.queue_list.setVisible(True)
        self._refresh_queue_list()
        if self._queue_running:
            current = min(self.queue_pos + 1, count)
            self.info_label.setText(self.t("queue_status_label", current=current, total=count))
        else:
            self.info_label.setText("")

    def _queue_has_non_image(self):
        return any(not is_image_file(item["path"]) for item in self.queue)

    def _queue_has_true_video(self):
        return any(
            not is_image_file(item["path"]) and not is_gif_file(item["path"]) for item in self.queue
        )

    def load_files(self, paths):
        single_fresh = len(paths) == 1 and not self.queue
        for path in paths:
            img = is_image_file(path)
            try:
                info = probe_image(path) if img else probe_video(path)
            except Exception as e:  # noqa: BLE001
                if single_fresh:
                    kind = self.t("kind_image") if img else self.t("kind_video")
                    QMessageBox.critical(self, self.t("error_title"), f"{kind} {self.t('read_fail')}:\n{e}")
                    return
                self.queue.append(
                    {"path": path, "info": None, "status": "failed", "output": None, "error": str(e), "warning": None}
                )
                continue
            self.queue.append(
                {"path": path, "info": info, "status": "pending", "output": None, "error": None, "warning": None}
            )

        if not self.queue:
            return

        self._refresh_file_display()

        show_av = self._queue_has_true_video()
        self.audio_header.setVisible(show_av)
        self.audio_card.setVisible(show_av)
        show_fps = self._queue_has_non_image()
        self.fps_header.setVisible(show_fps)
        self.fps_card.setVisible(show_fps)
        self._update_scale_options()

        self.run_btn.setEnabled(True)
        self._set_controls_busy(False)
        self.update_hint()

    def clear_file(self):
        """Kuyruktaki tum dosyalari kaldir; bos baslangic durumuna don."""
        if self.worker and self.worker.isRunning():
            return
        self.queue = []
        self.queue_pos = 0
        self._queue_running = False
        self.output_path = None
        self.queue_list.clear()
        self._set_drop_empty_html()
        self._set_drop_zone_property("hasFile", False)
        self.clear_btn.setVisible(False)
        self.info_label.setText("")
        self.hint_label.setText("")
        self.status_label.setText("")
        self.eta_label.setText("")
        self.progress_bar.setValue(0)
        self.run_btn.setEnabled(False)
        self.open_folder_btn.setVisible(False)
        self.play_btn.setVisible(False)
        self.queue_list.setVisible(False)
        self.audio_header.setVisible(True)
        self.audio_card.setVisible(True)
        self.fps_header.setVisible(True)
        self.fps_card.setVisible(True)
        self.scale_2x.setVisible(True)
        self.scale_3x.setVisible(True)
        self.scale_4x.setVisible(False)
        if not self.scale_2x.isChecked() and not self.scale_3x.isChecked():
            self.scale_2x.setChecked(True)
        self._set_controls_busy(False)

    def _update_scale_options(self):
        """Kuyruk yalnizca foto iceriyorsa: sabit 4x. Aksi halde: 2x / 3x."""
        photo_only = bool(self.queue) and not self._queue_has_non_image()
        self.scale_2x.setVisible(not photo_only)
        self.scale_3x.setVisible(not photo_only)
        self.scale_4x.setVisible(photo_only)
        if photo_only:
            self.scale_4x.setChecked(True)
            tip = self.t("scale_photo_tip")
            self.scale_4x.setToolTip(tip)
            self.scale_2x.setToolTip("")
            self.scale_3x.setToolTip("")
        else:
            if self.scale_4x.isChecked():
                self.scale_2x.setChecked(True)
            tip = self.t("scale_video_tip")
            self.scale_2x.setToolTip(tip)
            self.scale_3x.setToolTip(tip)
            self.scale_4x.setToolTip("")

    # --- Tahmin / uyari metni ---

    def update_hint(self):
        if not self.queue:
            return
        quality_key = "quality" if self.model_4k.isChecked() else "fast"
        scale = self._selected_scale()
        total_seconds = sum(
            estimate_seconds(item["info"], quality_key) for item in self.queue if item["info"] is not None
        )
        units = {"sec": self.t("unit_sec"), "min": self.t("unit_min"), "hr": self.t("unit_hr")}
        text = f"{self.t('eta_prefix')} {format_duration(total_seconds, units=units)}"

        if quality_key == "fast" and scale == 3:
            risky = any(
                not is_image_file(item["path"]) and item["info"] is not None and low_bitrate_risk(item["info"])
                for item in self.queue
            )
            if risky:
                text += self.t("warn_bitrate")
        self.hint_label.setText(text)

    def _selected_scale(self):
        return 3 if self.scale_3x.isChecked() else 2

    def _effective_scale_for(self, path):
        return 4 if is_image_file(path) else self._selected_scale()

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
            self.scale_4x,
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
        """Uretim sirasinda tercihleri kilitle; bitince kuyruk icerigine gore ac."""
        self.setAcceptDrops(not busy)
        self.clear_btn.setEnabled(not busy and bool(self.queue))

        if busy:
            for w in self._preference_widgets():
                w.setEnabled(False)
            self.audio_card.setEnabled(False)
            self.fps_card.setEnabled(False)
            return

        # --- Kilit ac ---
        has_file = bool(self.queue)
        photo_only = has_file and not self._queue_has_non_image()
        show_av = has_file and self._queue_has_true_video()
        show_fps = has_file and self._queue_has_non_image()

        self.browse_btn.setEnabled(True)
        self.lang_btn.setEnabled(True)
        self.theme_btn.setEnabled(True)

        self.model_hd.setEnabled(has_file)
        self.model_4k.setEnabled(has_file)

        self._update_scale_options()
        self.scale_2x.setEnabled(has_file and not photo_only)
        self.scale_3x.setEnabled(has_file and not photo_only)
        self.scale_4x.setEnabled(photo_only)

        self.audio_card.setEnabled(show_av)
        for btn in (self.audio_off, self.audio_auto, self.audio_25, self.audio_50, self.audio_100):
            btn.setEnabled(show_av)

        self.fps_card.setEnabled(show_fps)
        for btn in (self.fps_original, self.fps_30, self.fps_60):
            btn.setEnabled(show_fps)

    # --- Isleme ---

    def start_processing(self):
        if not self.queue:
            return

        prefs = {"model": "quality" if self.model_4k.isChecked() else "fast"}
        if self._queue_has_non_image():
            prefs["scale"] = self._selected_scale()
            prefs["fps"] = self._selected_output_fps() or 0
        if self._queue_has_true_video():
            prefs["audio_mode"] = self._selected_audio_mode()
        save_config(**prefs)

        for item in self.queue:
            if item["status"] != "failed":
                item["status"] = "pending"
            item["output"] = None
            item["warning"] = None
        self.queue_pos = 0
        self._queue_running = True

        self.run_btn.setEnabled(False)
        self.stop_btn.setVisible(True)
        self.stop_btn.setEnabled(True)
        self.open_folder_btn.setVisible(False)
        self.play_btn.setVisible(False)
        self.progress_bar.setValue(0)
        self.eta_label.setText("")
        self._set_controls_busy(True)

        self._process_current_queue_item()

    def _process_current_queue_item(self):
        while self.queue_pos < len(self.queue) and self.queue[self.queue_pos]["status"] == "failed":
            self.queue_pos += 1  # yukleme sirasinda okunamayan dosyalari atla

        if self.queue_pos >= len(self.queue):
            self._finish_queue()
            return

        item = self.queue[self.queue_pos]
        item["status"] = "processing"
        self._refresh_file_display()

        path = item["path"]
        img = is_image_file(path)
        gif = is_gif_file(path)
        scale = self._effective_scale_for(path)
        quality_key = "quality" if self.model_4k.isChecked() else "fast"
        audio_mode = self._selected_audio_mode() if not img and not gif else "off"
        output_fps = None if img else self._selected_output_fps()

        self.estimated_total_seconds = estimate_seconds(item["info"], quality_key)
        self.process_start_time = time.time()
        self.current_progress_pct = 0
        self.update_eta()
        self.eta_timer.start(1000)

        # Onceki worker sinyali yolladiktan sonra run() sonundaki temizligi hala suruyor
        # olabilir; referansi birakirsak calisan QThread yok edilir.
        self._retired_workers = [w for w in self._retired_workers if w.isRunning()]
        if self.worker is not None and self.worker.isRunning():
            self._retired_workers.append(self.worker)
        self.worker = UpscaleWorker(
            path,
            scale,
            quality_key,
            audio_mode=audio_mode,
            output_fps=output_fps,
            strings=STRINGS.get(self.language, STRINGS["tr"]),
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.status.connect(self.on_status)
        self.worker.finished_ok.connect(self._on_item_finished)
        self.worker.failed.connect(self._on_item_failed)
        self.worker.cancelled.connect(self._on_item_cancelled)
        self.worker.warning.connect(self._on_item_warning)
        self.worker.start()

    def stop_processing(self):
        if self.worker:
            self.worker.cancel()
        self.stop_btn.setEnabled(False)
        self.eta_label.setText(self.t("stopping"))

    def on_progress(self, pct):
        self.current_progress_pct = pct
        self.progress_bar.setValue(pct)

    def on_status(self, message):
        self.status_label.setText(message)

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
        if not self.queue:
            return
        path = self.queue[0]["path"]
        if is_image_file(path):
            self.play_btn.setText(self.t("play_photo"))
        elif is_gif_file(path):
            self.play_btn.setText(self.t("play_gif"))
        else:
            self.play_btn.setText(self.t("play_video"))

    def _on_item_finished(self, output_path):
        item = self.queue[self.queue_pos]
        item["status"] = "done"
        item["output"] = output_path
        self.output_path = output_path

        if len(self.queue) == 1:
            self._queue_running = False
            self.eta_timer.stop()
            self.status_label.setText("")
            self.eta_label.setText(self.t("done"))
            self.run_btn.setEnabled(True)
            self.stop_btn.setVisible(False)
            self.open_folder_btn.setVisible(True)
            self._refresh_play_btn_text()
            self.play_btn.setVisible(True)
            self._set_controls_busy(False)
            play_completion_sound()
            return

        self.queue_pos += 1
        self._process_current_queue_item()

    def _on_item_failed(self, message):
        item = self.queue[self.queue_pos]
        item["status"] = "failed"
        item["error"] = message

        if len(self.queue) == 1:
            self._queue_running = False
            self.eta_timer.stop()
            self.status_label.setText("")
            self.eta_label.setText(self.t("error_occurred"))
            self.run_btn.setEnabled(True)
            self.stop_btn.setVisible(False)
            self._set_controls_busy(False)
            QMessageBox.critical(self, self.t("error_title"), message)
            return

        self.queue_pos += 1
        self._process_current_queue_item()

    def _on_item_warning(self, message):
        item = self.queue[self.queue_pos]
        item["warning"] = message

        if len(self.queue) == 1:
            QMessageBox.warning(self, self.t("warning_title"), message)

    def _on_item_cancelled(self):
        for item in self.queue[self.queue_pos:]:
            if item["status"] in ("pending", "processing"):
                item["status"] = "cancelled"
        self._queue_running = False
        self.eta_timer.stop()
        self.status_label.setText("")
        self.eta_label.setText(self.t("stopped"))
        self.progress_bar.setValue(0)
        self.run_btn.setEnabled(True)
        self.stop_btn.setVisible(False)
        self._set_controls_busy(False)
        self._refresh_file_display()

    def _finish_queue(self):
        self._queue_running = False
        self.eta_timer.stop()
        self._refresh_file_display()
        self.run_btn.setEnabled(True)
        self.stop_btn.setVisible(False)
        self._set_controls_busy(False)

        done = sum(1 for it in self.queue if it["status"] == "done")
        failed = sum(1 for it in self.queue if it["status"] == "failed")
        total = len(self.queue)
        self.status_label.setText("")
        self.eta_label.setText(self.t("queue_summary", done=done, total=total, failed=failed))
        self.progress_bar.setValue(100)
        if self.queue:
            self.output_path = self.queue[0]["path"]
            self.open_folder_btn.setVisible(True)
        play_completion_sound()

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
