"""Vektorel ikonlar - QPainter ile cizilir, harici SVG/dosya bagimliligi yok.

Her fonksiyon bir QIcon dondurur; renk parametresi tema (koyu/acik) ile
uyumlu calismasini saglar.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF


def _blank_pixmap(size):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    return pm


def _stroke_painter(pixmap, color, width_frac=0.11):
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(color)
    pen.setWidthF(pixmap.width() * width_frac)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    return painter


def x_icon(color, size=18):
    pm = _blank_pixmap(size)
    p = _stroke_painter(pm, color, 0.12)
    m = size * 0.28
    p.drawLine(QPointF(m, m), QPointF(size - m, size - m))
    p.drawLine(QPointF(size - m, m), QPointF(m, size - m))
    p.end()
    return QIcon(pm)


def sun_icon(color, size=18):
    pm = _blank_pixmap(size)
    p = _stroke_painter(pm, color, 0.09)
    c = size / 2
    r = size * 0.20
    p.drawEllipse(QPointF(c, c), r, r)
    import math

    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        x1 = c + math.cos(rad) * (r + size * 0.10)
        y1 = c + math.sin(rad) * (r + size * 0.10)
        x2 = c + math.cos(rad) * (r + size * 0.22)
        y2 = c + math.sin(rad) * (r + size * 0.22)
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
    p.end()
    return QIcon(pm)


def moon_icon(color, size=18):
    pm = _blank_pixmap(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    big = QPainterPath()
    big.addEllipse(QRectF(size * 0.14, size * 0.14, size * 0.64, size * 0.64))
    small = QPainterPath()
    small.addEllipse(QRectF(size * 0.30, size * 0.08, size * 0.64, size * 0.64))
    crescent = big.subtracted(small)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPath(crescent)
    p.end()
    return QIcon(pm)


def play_icon(color, size=18):
    pm = _blank_pixmap(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    poly = QPolygonF(
        [QPointF(size * 0.30, size * 0.20), QPointF(size * 0.30, size * 0.80), QPointF(size * 0.82, size * 0.5)]
    )
    p.drawPolygon(poly)
    p.end()
    return QIcon(pm)


def stop_icon(color, size=18):
    pm = _blank_pixmap(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawRoundedRect(QRectF(size * 0.24, size * 0.24, size * 0.52, size * 0.52), size * 0.08, size * 0.08)
    p.end()
    return QIcon(pm)


def folder_icon(color, size=18):
    pm = _blank_pixmap(size)
    p = _stroke_painter(pm, color, 0.09)
    path = QPainterPath()
    points = [
        (0.12, 0.30), (0.12, 0.78), (0.88, 0.78), (0.88, 0.34),
        (0.46, 0.34), (0.37, 0.22), (0.12, 0.22),
    ]
    path.moveTo(points[0][0] * size, points[0][1] * size)
    for x, y in points[1:]:
        path.lineTo(x * size, y * size)
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def upload_icon(color, size=44):
    pm = _blank_pixmap(size)
    p = _stroke_painter(pm, color, 0.055)
    cx = size * 0.5
    p.drawLine(QPointF(cx, size * 0.70), QPointF(cx, size * 0.20))
    p.drawLine(QPointF(cx, size * 0.20), QPointF(cx - size * 0.17, size * 0.38))
    p.drawLine(QPointF(cx, size * 0.20), QPointF(cx + size * 0.17, size * 0.38))
    p.drawLine(QPointF(size * 0.22, size * 0.82), QPointF(size * 0.78, size * 0.82))
    p.end()
    return QIcon(pm)


def resize_icon(color, size=16):
    pm = _blank_pixmap(size)
    p = _stroke_painter(pm, color, 0.13)
    p.drawLine(QPointF(size * 0.35, size * 0.65), QPointF(size * 0.75, size * 0.25))
    p.drawLine(QPointF(size * 0.75, size * 0.25), QPointF(size * 0.75, size * 0.45))
    p.drawLine(QPointF(size * 0.75, size * 0.25), QPointF(size * 0.55, size * 0.25))
    p.drawLine(QPointF(size * 0.65, size * 0.35), QPointF(size * 0.25, size * 0.75))
    p.drawLine(QPointF(size * 0.25, size * 0.75), QPointF(size * 0.25, size * 0.55))
    p.drawLine(QPointF(size * 0.25, size * 0.75), QPointF(size * 0.45, size * 0.75))
    p.end()
    return QIcon(pm)


def spark_icon(color, size=16):
    pm = _blank_pixmap(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    poly = QPolygonF(
        [
            QPointF(size * 0.5, size * 0.04),
            QPointF(size * 0.60, size * 0.40),
            QPointF(size * 0.96, size * 0.5),
            QPointF(size * 0.60, size * 0.60),
            QPointF(size * 0.5, size * 0.96),
            QPointF(size * 0.40, size * 0.60),
            QPointF(size * 0.04, size * 0.5),
            QPointF(size * 0.40, size * 0.40),
        ]
    )
    p.drawPolygon(poly)
    p.end()
    return QIcon(pm)


def speaker_icon(color, size=16):
    pm = _blank_pixmap(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    body = QPolygonF(
        [
            QPointF(size * 0.10, size * 0.38), QPointF(size * 0.32, size * 0.38),
            QPointF(size * 0.54, size * 0.18), QPointF(size * 0.54, size * 0.82),
            QPointF(size * 0.32, size * 0.62), QPointF(size * 0.10, size * 0.62),
        ]
    )
    p.drawPolygon(body)
    pen = QPen(color)
    pen.setWidthF(size * 0.11)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(size * 0.58, size * 0.28, size * 0.26, size * 0.44), -55 * 16, 110 * 16)
    p.end()
    return QIcon(pm)


def clock_icon(color, size=16):
    pm = _blank_pixmap(size)
    p = _stroke_painter(pm, color, 0.11)
    c = size / 2
    r = size * 0.38
    p.drawEllipse(QPointF(c, c), r, r)
    p.drawLine(QPointF(c, c), QPointF(c, c - r * 0.55))
    p.drawLine(QPointF(c, c), QPointF(c + r * 0.45, c))
    p.end()
    return QIcon(pm)


def logo_pixmap(accent_color, fg_color, size=34):
    pm = _blank_pixmap(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(accent_color)
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.30, size * 0.30)
    pen = QPen(fg_color)
    pen.setWidthF(size * 0.11)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.drawLine(QPointF(size * 0.32, size * 0.68), QPointF(size * 0.68, size * 0.32))
    p.drawLine(QPointF(size * 0.68, size * 0.32), QPointF(size * 0.68, size * 0.50))
    p.drawLine(QPointF(size * 0.68, size * 0.32), QPointF(size * 0.50, size * 0.32))
    p.end()
    return pm
