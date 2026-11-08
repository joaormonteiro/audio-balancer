"""Image provider: real app icons for QML (image://appicon/<process name>)."""
from PySide6.QtCore import QFileInfo, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPixmap
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtWidgets import QFileIconProvider

SIZE = 96


def _placeholder(name: str) -> QPixmap:
    """Rounded colored tile with the app's initial, for apps without a known exe."""
    hue = (sum(ord(c) for c in name) * 47) % 360
    pm = QPixmap(SIZE, SIZE)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, SIZE, SIZE)
    g.setColorAt(0, QColor.fromHsl(hue, 190, 150))
    g.setColorAt(1, QColor.fromHsl((hue + 30) % 360, 200, 105))
    p.setBrush(g)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(4, 4, SIZE - 8, SIZE - 8), 22, 22)
    p.setPen(QColor("white"))
    f = QFont("Segoe UI", 38)
    f.setWeight(QFont.DemiBold)
    p.setFont(f)
    p.drawText(QRectF(0, 0, SIZE, SIZE), Qt.AlignCenter, (name[:1] or "?").upper())
    p.end()
    return pm


class AppIconProvider(QQuickImageProvider):
    def __init__(self, path_for):
        super().__init__(QQuickImageProvider.Pixmap)
        self._path_for = path_for
        self._files = QFileIconProvider()
        self._cache = {}

    def requestPixmap(self, id, size, requested_size):
        name = id.split("?")[0].lower()
        path = self._path_for(name)
        key = (name, path)
        pm = self._cache.get(key)
        if pm is None:
            pm = None
            if path:
                icon = self._files.icon(QFileInfo(path))
                if not icon.isNull():
                    pm = icon.pixmap(QSize(SIZE, SIZE))
                    if pm.isNull():
                        pm = None
            if pm is None:
                pm = _placeholder(name)
            self._cache[key] = pm
        return pm
