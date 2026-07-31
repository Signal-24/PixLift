"""Ozel Qt widget'lari."""

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
)
from PySide6.QtWidgets import QWidget


class AnimatedProgressBar(QWidget):
    """Renkli, kayan gradyanli ilerleme cubugu - islemin gorsel olarak 'canli' hissettirmesi icin."""

    WAVE_COLORS = [QColor("#FBBF24"), QColor("#F97316"), QColor("#FDE68A"), QColor("#FBBF24")]

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
