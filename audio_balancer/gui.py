"""System tray + on-demand window.

While the app sits in the tray nothing from Qt Quick is loaded or running: the
window (and its QML engine, GPU resources and timers) is created when opened
and torn down when closed, so the tray session stays as light as possible.
"""
import ctypes
import gc
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import config as cfgmod
from . import ipc
from .i18n import t

APP_ID = "joaormonteiro.AudioBalancer"


def resource_dir() -> Path:
    """Folder holding qml/ and assets/, both in source and in the frozen exe."""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) / "audio_balancer" if base else Path(__file__).parent


def apply_caption(window) -> None:
    """Match the title bar to the system light/dark theme (Windows 11 look)."""
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication

        dark = QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        hwnd = int(window.winId())
        v = ctypes.c_int(1 if dark else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(v), 4)  # immersive dark mode
        m = ctypes.c_int(2)  # Mica backdrop on the title bar where supported
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(m), 4)
    except Exception:
        pass


def trim_memory() -> None:
    """Hand freed pages back to Windows so the tray session shows a small footprint."""
    gc.collect()
    try:
        ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
    except Exception:
        pass


class StateBridge(QObject):
    """Lets the engine thread tell the main thread that speech started/stopped."""

    changed = Signal(bool)
    quit_requested = Signal()
    enabled_changed = Signal(bool)


class Shell:
    def __init__(self, app, engine, cfg):
        self.app, self.engine, self.cfg = app, engine, cfg
        self.res = resource_dir()
        self.assets = self.res / "assets"
        self.proc = None
        self.bridge = StateBridge()  # IPC threads reach the Qt thread through signals
        self.server = ipc.Server(
            engine, cfg, lambda: cfgmod.save(cfg),
            on_quit=self.bridge.quit_requested.emit,
            on_enabled=self.bridge.enabled_changed.emit,
        )
        self.bridge.quit_requested.connect(self.quit)
        self.bridge.enabled_changed.connect(self._sync_enabled)

        self.app_icon = QIcon(QPixmap(str(self.assets / "icon.png")))
        self.idle_icon = QIcon(QPixmap(str(self.assets / "tray_idle.png")))
        self.talk_icon = QIcon(QPixmap(str(self.assets / "tray_talk.png")))
        app.setWindowIcon(self.app_icon)

        self.tray = QSystemTrayIcon(self.idle_icon, app)
        self.tray.setToolTip(t("title"))
        self.menu = QMenu()
        open_act = QAction(t("tray_open"), self.menu)
        open_act.triggered.connect(self.show_window)
        self.enabled_act = QAction(t("tray_enabled"), self.menu, checkable=True)
        self.enabled_act.setChecked(engine.enabled)
        self.enabled_act.triggered.connect(self.set_enabled)
        quit_act = QAction(t("tray_quit"), self.menu)
        quit_act.triggered.connect(self.quit)
        self.menu.addActions([open_act, self.enabled_act])
        self.menu.addSeparator()
        self.menu.addAction(quit_act)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._tray_clicked)
        self.tray.show()

        self.bridge.changed.connect(self.on_talking)
        engine.on_state = self.bridge.changed.emit

    # ---------- tray ----------
    def _tray_clicked(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window()

    @Slot(bool)
    def on_talking(self, talking):
        self.tray.setIcon(self.talk_icon if talking else self.idle_icon)

    def set_enabled(self, on):
        self.engine.enabled = bool(on)
        self.cfg["enabled"] = bool(on)
        cfgmod.save(self.cfg)
        self.enabled_act.setChecked(bool(on))
        if not on:
            self.tray.setIcon(self.idle_icon)

    # ---------- window process ----------
    def show_window(self):
        """The window is its own process: closing it returns all of its memory."""
        if self.proc is not None and self.proc.poll() is None:
            self.server.raise_flag = True  # already open: ask it to come to the front
            return
        env = dict(os.environ, **self.server.env())
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(ipc.ui_command(), env=env, creationflags=flags)

    def _sync_enabled(self, on):
        self.enabled_act.setChecked(bool(on))
        if not on:
            self.tray.setIcon(self.idle_icon)

    def quit(self):
        self.tray.hide()
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
        self.engine.stop()
        self.app.quit()


def run(engine, cfg, start_hidden=False, on_ready=None) -> int:
    try:  # makes Windows show OUR icon on the taskbar instead of python's
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(t("title"))
    shell = Shell(app, engine, cfg)
    if not start_hidden:
        shell.show_window()
    else:
        QTimer.singleShot(500, trim_memory)
    if on_ready:  # test hook: lets scripts inspect the app before the loop starts
        on_ready(app, shell)
    return app.exec()


def run_window() -> int:
    """Window process: shows the UI and talks to the tray process over IPC."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass
    from PySide6.QtQml import QQmlApplicationEngine

    from . import config as cfgmod
    from .icons import AppIconProvider
    from .ui_backend import Backend

    remote = ipc.RemoteEngine.from_env()
    cfg = cfgmod.load()
    app = QApplication(sys.argv)
    app.setApplicationName(t("title"))
    res = resource_dir()
    assets = res / "assets"
    app.setWindowIcon(QIcon(QPixmap(str(assets / "icon.png"))))

    max_height = app.primaryScreen().availableGeometry().height() - 48
    backend = Backend(remote, cfg, QUrl.fromLocalFile(str(assets) + "/").toString(), max_height)
    qml = QQmlApplicationEngine()
    qml.addImageProvider("appicon", AppIconProvider(backend.icon_path))
    qml.rootContext().setContextProperty("backend", backend)
    qml.load(QUrl.fromLocalFile(str(res / "qml" / "main.qml")))
    if not qml.rootObjects():
        return 1
    window = qml.rootObjects()[0]
    apply_caption(window)
    backend.closing.connect(lambda: (backend.shutdown(), app.quit()))
    backend.quitRequested.connect(app.quit)

    def bring_front():
        window.show()
        window.raise_()
        window.requestActivate()

    backend.raiseRequested.connect(bring_front)
    code = app.exec()
    try:
        remote.want_apps = False
    except Exception:
        pass
    return code
