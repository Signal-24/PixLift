"""Qt stylesheet uretimi (koyu/acik tema)."""

from PySide6.QtGui import QColor

from .settings import ACCENT

PALETTES = {
    "dark": {
        "bg": "#1e1f22",
        "card": "#2a2c30",
        "border": "rgba(251, 191, 36, 0.35)",
        "disabled_bg": "#3a3d42",
        "text": "#e8e8e8",
        "muted": "#9aa0a6",
        "accent_hover": "#fcd34d",
        "accent_pressed": "#d97706",
        "input_bg": "#26282c",
        "chip_text": "#2b1400",
    },
    "light": {
        "bg": "#f3f5f7",
        "card": "#ffffff",
        "border": "rgba(180, 83, 9, 0.35)",
        "disabled_bg": "#dde1e6",
        "text": "#1f2124",
        "muted": "#5f6368",
        "accent_hover": "#d97706",
        "accent_pressed": "#92400e",
        "input_bg": "#ffffff",
        "chip_text": "#2b1400",
    },
}


def icon_color(theme):
    return QColor(PALETTES[theme]["text"])


def muted_icon_color(theme):
    return QColor(PALETTES[theme]["muted"])


def accent_color(theme):
    return QColor(ACCENT[theme])


def build_stylesheet(theme):
    accent = ACCENT[theme]
    c = PALETTES[theme]

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
        border-radius: 12px;
        padding: 26px;
        background: {c['card']};
        color: {c['muted']};
        font-size: 13px;
    }}
    QLabel#dropZone[hasFile="true"] {{
        border: 1px solid {accent};
        background: {c['input_bg']};
        color: {c['text']};
        font-weight: 600;
    }}
    QFrame#dropZoneFrame {{
        background: transparent;
        border: none;
    }}
    QFrame#dropZoneFrame[dragOver="true"] QLabel#dropZone {{
        border-color: {accent};
        background: {c['input_bg']};
    }}
    QPushButton#clearFileButton {{
        background: transparent;
        border: none;
        color: {c['muted']};
        font-size: 18px;
        font-weight: 700;
        padding: 0;
        margin: 6px;
        min-width: 28px;
        max-width: 28px;
        min-height: 28px;
        max-height: 28px;
        border-radius: 14px;
    }}
    QPushButton#clearFileButton:hover {{
        background: {c['input_bg']};
        color: {c['text']};
    }}
    QLabel#dropZone[dragOver="true"] {{
        border-color: {accent};
        background: {c['input_bg']};
    }}
    QFrame#card {{
        background: {c['card']};
        border: 1px solid {c['border']};
        border-radius: 12px;
        padding: 8px;
    }}
    QLabel#sectionTitle {{
        color: {c['muted']};
        font-weight: 700;
        font-size: 11px;
        padding-left: 2px;
    }}
    QRadioButton#choiceChip {{
        padding: 5px 10px;
        spacing: 0px;
        border-radius: 8px;
        border: 1px solid transparent;
        background: {c['input_bg']};
        color: {c['text']};
        font-weight: 600;
    }}
    QRadioButton#choiceChip::indicator {{
        width: 0px;
        height: 0px;
    }}
    QRadioButton#choiceChip:hover {{
        border-color: {c['border']};
        color: {c['text']};
    }}
    QRadioButton#choiceChip:checked {{
        background: {accent};
        color: {c['chip_text']};
        border-color: {accent};
    }}
    QRadioButton#choiceChip:disabled {{
        color: {c['muted']};
        background: {c['disabled_bg']};
        border-color: transparent;
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
        color: {c['chip_text']};
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
    QListWidget#queueList {{
        background: {c['card']};
        border: 1px solid {c['border']};
        border-radius: 10px;
        padding: 4px;
    }}
    QListWidget#queueList::item {{
        padding: 3px 4px;
        color: {c['text']};
    }}
    """
