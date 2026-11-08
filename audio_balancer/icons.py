"""Image provider: real app icons for QML (image://appicon/<process name>)."""
import glob
import os

from PySide6.QtCore import QFileInfo, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap
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


def _env(name):
    return os.environ.get(name, "")


# Where well-known apps usually live, for when they are not running right now
# (a running app gives us its exact path instead).
KNOWN_LOCATIONS = {
    "discord.exe": ["%LOCALAPPDATA%/Discord/app-*/Discord.exe", "%LOCALAPPDATA%/Discord/Update.exe"],
    "spotify.exe": ["%APPDATA%/Spotify/Spotify.exe", "%LOCALAPPDATA%/Microsoft/WindowsApps/Spotify.exe"],
    "chrome.exe": ["%PROGRAMFILES%/Google/Chrome/Application/chrome.exe", "%PROGRAMFILES(X86)%/Google/Chrome/Application/chrome.exe", "%LOCALAPPDATA%/Google/Chrome/Application/chrome.exe"],
    "msedge.exe": ["%PROGRAMFILES(X86)%/Microsoft/Edge/Application/msedge.exe", "%PROGRAMFILES%/Microsoft/Edge/Application/msedge.exe"],
    "firefox.exe": ["%PROGRAMFILES%/Mozilla Firefox/firefox.exe", "%PROGRAMFILES(X86)%/Mozilla Firefox/firefox.exe"],
    "brave.exe": ["%PROGRAMFILES%/BraveSoftware/Brave-Browser/Application/brave.exe", "%LOCALAPPDATA%/BraveSoftware/Brave-Browser/Application/brave.exe"],
    "vlc.exe": ["%PROGRAMFILES%/VideoLAN/VLC/vlc.exe", "%PROGRAMFILES(X86)%/VideoLAN/VLC/vlc.exe"],
    "teamspeak.exe": ["%PROGRAMFILES%/TeamSpeak 3 Client/ts3client_win64.exe"],
    "zoom.exe": ["%APPDATA%/Zoom/bin/Zoom.exe"],
    "telegram.exe": ["%APPDATA%/Telegram Desktop/Telegram.exe"],
}


def find_known(name: str) -> str:
    for pattern in KNOWN_LOCATIONS.get(name, []):
        for var in ("LOCALAPPDATA", "APPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            pattern = pattern.replace(f"%{var}%", _env(var))
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[-1]
    return ""


def _folder_icon(path: str):
    """Last resort: an .ico/.png sitting in the same folder as the exe."""
    folder = os.path.dirname(path)
    for pat in ("*.ico", "icon*.png", "*.png"):
        hits = sorted(glob.glob(os.path.join(folder, pat)))
        if hits:
            pm = QIcon(hits[0]).pixmap(QSize(SIZE, SIZE))
            if not pm.isNull():
                return pm
    return None


class AppIconProvider(QQuickImageProvider):
    def __init__(self, path_for):
        super().__init__(QQuickImageProvider.Pixmap)
        self._path_for = path_for
        self._files = QFileIconProvider()
        self._cache = {}

    def requestPixmap(self, id, size, requested_size):
        name = id.split("?")[0].lower()
        path = self._path_for(name) or find_known(name)
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
            if pm is None and path:
                pm = _folder_icon(path)
            if pm is None:
                pm = _placeholder(name)
            self._cache[key] = pm
        return pm
