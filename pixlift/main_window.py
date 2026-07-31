"""Ana pencere (PySide6 UI) ve uygulama girisi."""

import os
import sys
import time

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

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
from .theme import build_stylesheet
from .tools import check_tools_available
from .widgets import AnimatedProgressBar
from .worker import UpscaleWorker


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

        self.clear_btn = QPushButton("×")
        self.clear_btn.setObjectName("clearFileButton")
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

        sections_row = QHBoxLayout()
        sections_row.setSpacing(10)

        scale_card = QFrame()
        scale_card.setObjectName("card")
        scale_layout = QHBoxLayout(scale_card)
        self.scale_2x = QRadioButton("2x")
        self.scale_3x = QRadioButton("3x")
        self.scale_4x = QRadioButton("4x")
        self.scale_2x.setChecked(True)
        self.scale_group = QButtonGroup(self)
        self.scale_group.addButton(self.scale_2x)
        self.scale_group.addButton(self.scale_3x)
        self.scale_group.addButton(self.scale_4x)
        scale_layout.addWidget(self.scale_2x)
        scale_layout.addWidget(self.scale_3x)
        scale_layout.addWidget(self.scale_4x)
        self.scale_4x.setVisible(False)
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
        if self.video_info:
            self._refresh_info_label()
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
        self.clear_btn.setVisible(True)
        self._refresh_info_label()

        show_av = not self.is_image and not self.is_gif
        self.audio_title.setVisible(show_av)
        self.audio_card.setVisible(show_av)
        self.fps_title.setVisible(not self.is_image)
        self.fps_card.setVisible(not self.is_image)
        self._update_scale_options()

        self.run_btn.setEnabled(True)
        self._set_controls_busy(False)
        self.update_hint()

    def clear_file(self):
        """Secili dosyayi kaldir; bos baslangic durumuna don."""
        if self.worker and self.worker.isRunning():
            return
        self.input_path = None
        self.output_path = None
        self.video_info = None
        self.is_image = False
        self.is_gif = False
        self.file_label.setText(self.t("drop_empty"))
        self._set_drop_zone_property("hasFile", False)
        self.clear_btn.setVisible(False)
        self.info_label.setText("")
        self.hint_label.setText("")
        self.eta_label.setText("")
        self.progress_bar.setValue(0)
        self.run_btn.setEnabled(False)
        self.open_folder_btn.setVisible(False)
        self.play_btn.setVisible(False)
        self.audio_title.setVisible(True)
        self.audio_card.setVisible(True)
        self.fps_title.setVisible(True)
        self.fps_card.setVisible(True)
        self.scale_2x.setVisible(True)
        self.scale_3x.setVisible(True)
        self.scale_4x.setVisible(False)
        if not self.scale_2x.isChecked() and not self.scale_3x.isChecked():
            self.scale_2x.setChecked(True)
        self._set_controls_busy(False)

    def _update_scale_options(self):
        """Foto: sabit 4x. Video/GIF: 2x / 3x."""
        photo = self.is_image
        self.scale_2x.setVisible(not photo)
        self.scale_3x.setVisible(not photo)
        self.scale_4x.setVisible(photo)
        if photo:
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
        if not self.video_info:
            return
        quality_key = "quality" if self.model_4k.isChecked() else "fast"
        scale = self._selected_scale()
        seconds = estimate_seconds(self.video_info, quality_key)
        text = f"{self.t('eta_prefix')} {format_duration(seconds)}"

        if (
            not self.is_image
            and quality_key == "fast"
            and scale == 3
            and low_bitrate_risk(self.video_info)
        ):
            text += self.t("warn_bitrate")
        self.hint_label.setText(text)

    def _selected_scale(self):
        if self.is_image:
            return 4
        return 3 if self.scale_3x.isChecked() else 2

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
        """Uretim sirasinda tercihleri kilitle; bitince dosya tipine gore ac."""
        self.setAcceptDrops(not busy)
        self.clear_btn.setEnabled(not busy and bool(self.input_path))

        if busy:
            for w in self._preference_widgets():
                w.setEnabled(False)
            self.audio_card.setEnabled(False)
            self.fps_card.setEnabled(False)
            return

        # --- Kilit ac ---
        has_file = bool(self.input_path)
        photo = has_file and self.is_image
        gif = has_file and self.is_gif
        show_av = has_file and not photo and not gif
        show_fps = has_file and not photo

        self.browse_btn.setEnabled(True)
        self.lang_btn.setEnabled(True)
        self.theme_btn.setEnabled(True)

        self.model_hd.setEnabled(has_file)
        self.model_4k.setEnabled(has_file)

        self._update_scale_options()
        self.scale_2x.setEnabled(has_file and not photo)
        self.scale_3x.setEnabled(has_file and not photo)
        self.scale_4x.setEnabled(photo)

        self.audio_card.setEnabled(show_av)
        for btn in (self.audio_off, self.audio_auto, self.audio_25, self.audio_50, self.audio_100):
            btn.setEnabled(show_av)

        self.fps_card.setEnabled(show_fps)
        for btn in (self.fps_original, self.fps_30, self.fps_60):
            btn.setEnabled(show_fps)

    # --- Isleme ---

    def start_processing(self):
        scale = self._selected_scale()
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
        self.worker.warning.connect(self.on_warning)
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

    def on_warning(self, message):
        QMessageBox.warning(self, self.t("warning_title"), message)

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
