"""Liquid-glass window (Qt Quick) plus system tray icon."""
import ctypes
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .i18n import t
from .ui_backend import Backend

APP_ID = "joaormonteiro.AudioBalancer"


def resource_dir() -> Path:
    """Folder holding qml/ and assets/, both in source and in the frozen exe."""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) / "audio_balancer" if base else Path(__file__).parent


def glass_supported() -> bool:
    """Acrylic backdrop needs Windows 11 22H2 (build 22621) or newer."""
    try:
        return sys.getwindowsversion().build >= 22621
    except Exception:
        return False


def apply_glass(window) -> None:
    """Dark title bar, acrylic blur behind the whole window."""
    try:
        hwnd = int(window.winId())
        dwm = ctypes.windll.dwmapi
        one, three, round_ = ctypes.c_int(1), ctypes.c_int(3), ctypes.c_int(2)
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(one), 4)     # dark mode
        dwm.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(round_), 4)  # rounded corners
        dwm.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(three), 4)   # acrylic backdrop
        margins = (ctypes.c_int * 4)(-1, -1, -1, -1)
        dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
    except Exception:
        pass


def run(engine, cfg, start_hidden=False, on_ready=None) -> int:
    try:  # makes Windows show OUR icon on the taskbar instead of python's
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass

    glass = glass_supported()
    if glass:
        QQuickWindow.setDefaultAlphaBuffer(True)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(t("title"))

    res = resource_dir()
    assets = res / "assets"
    app_icon = QIcon(QPixmap(str(assets / "icon.png")))
    app.setWindowIcon(app_icon)

    # usable screen height minus the title bar and a little breathing room
    max_height = app.primaryScreen().availableGeometry().height() - 48
    backend = Backend(
        engine, cfg, QUrl.fromLocalFile(str(assets) + "/").toString(), glass,
        start_hidden, max_height,
    )
    qml = QQmlApplicationEngine()
    qml.rootContext().setContextProperty("backend", backend)
    qml.load(QUrl.fromLocalFile(str(res / "qml" / "main.qml")))
    if not qml.rootObjects():
        return 1
    window = qml.rootObjects()[0]
    if glass:
        apply_glass(window)

    # ---- tray ----
    tray = QSystemTrayIcon(app_icon, app)
    tray.setToolTip(t("title"))
    menu = QMenu()
    open_act = QAction(t("tray_open"), menu)
    open_act.triggered.connect(backend.showRequested.emit)
    enabled_act = QAction(t("tray_enabled"), menu, checkable=True)
    enabled_act.setChecked(engine.enabled)
    enabled_act.triggered.connect(lambda checked: setattr(backend, "enabled", checked))
    quit_act = QAction(t("tray_quit"), menu)
    quit_act.triggered.connect(backend.quitRequested.emit)
    menu.addActions([open_act, enabled_act])
    menu.addSeparator()
    menu.addAction(quit_act)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: backend.showRequested.emit()
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick)
        else None
    )
    tray.show()

    idle_icon = QIcon(QPixmap(str(assets / "tray_idle.png")))
    talk_icon = QIcon(QPixmap(str(assets / "tray_talk.png")))

    def sync_tray():
        enabled_act.setChecked(engine.enabled)
        tray.setIcon(talk_icon if backend.kind == "talking" else idle_icon)

    backend.statusChanged.connect(sync_tray)
    backend.enabledChanged.connect(sync_tray)
    sync_tray()

    def quit_app():
        tray.hide()
        engine.stop()
        app.quit()

    backend.quitRequested.connect(quit_app)
    if on_ready:  # test hook: lets scripts inspect the window before the loop starts
        on_ready(app, window, quit_app)
    return app.exec()
