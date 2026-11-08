"""Bridge between the audio engine / settings and the QML interface.

Created when the window opens and destroyed when it closes, so a tray-only
session keeps no UI state or timers alive.
"""
from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot
from PySide6.QtGui import QFontDatabase

from . import autostart
from . import config as cfgmod
from .i18n import LANG, STRINGS

KNOWN_CALL_APPS = [
    "discord.exe",
    "teamspeak.exe",
    "ts3client_win64.exe",
    "mumble.exe",
    "telegram.exe",
    "ms-teams.exe",
    "zoom.exe",
    "whatsapp.exe",
]


class Backend(QObject):
    statusChanged = Signal()
    levelChanged = Signal()
    enabledChanged = Signal()
    appsChanged = Signal()
    playingChanged = Signal()
    voiceChanged = Signal()
    settingsChanged = Signal()
    iconsChanged = Signal()
    activeChanged = Signal()
    quitRequested = Signal()
    closing = Signal()
    raiseRequested = Signal()

    def __init__(self, engine, cfg, assets_url, max_height=740, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._cfg = cfg
        self._assets = assets_url
        self._max_height = float(max_height)
        self._kind = "idle"
        self._level = 0.0
        self._apps = []
        self._playing = []
        self._choices = list(KNOWN_CALL_APPS)
        self._autostart = autostart.is_enabled()
        self._icon_version = 0
        self._known_paths = len(self._cfg.get("app_paths", {}))
        self._active = True
        self._tick_n = 0
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)
        engine.want_apps = True
        self._timer.start()
        self._tick()

    def _save(self):
        """Persist locally and hand the new settings to the tray process (it owns the engine)."""
        cfgmod.save(self._cfg)
        push = getattr(self._engine, "push_cfg", None)
        if push:
            try:
                push(self._cfg)
            except (OSError, EOFError):
                pass

    def shutdown(self):
        """Called when the window closes: stop polling and let the engine idle."""
        self._timer.stop()
        self._engine.want_apps = False

    # ---------- constants for QML ----------
    @Property("QVariantMap", constant=True)
    def tr(self):
        return STRINGS.get(LANG, STRINGS["en"])

    @Property(str, constant=True)
    def assets(self):
        return self._assets

    @Property(str, constant=True)
    def iconFont(self):
        families = set(QFontDatabase.families())
        for name in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
            if name in families:
                return name
        return "Segoe UI Symbol"

    @Property(float, constant=True)
    def maxHeight(self):
        return self._max_height

    # ---------- live state ----------
    @Property(str, notify=statusChanged)
    def kind(self):
        return self._kind

    @Property(float, notify=levelChanged)
    def level(self):
        return self._level

    @Property("QVariantList", notify=appsChanged)
    def musicApps(self):
        return self._apps

    @Property(int, notify=appsChanged)
    def musicCount(self):
        return sum(1 for a in self._apps if a["selected"])

    @Property("QVariantList", notify=playingChanged)
    def playing(self):
        return self._playing

    @Property("QVariantList", notify=voiceChanged)
    def voiceChoices(self):
        return self._choices

    @Property(int, notify=iconsChanged)
    def iconVersion(self):
        return self._icon_version

    def _get_active(self):
        return self._active

    def _set_active(self, v):
        v = bool(v)
        if v == self._active:
            return
        self._active = v
        # A minimized window needs no refreshes at all.
        if v:
            self._engine.want_apps = True
            self._timer.start()
        else:
            self._timer.stop()
            self._engine.want_apps = False
        self.activeChanged.emit()

    active = Property(bool, _get_active, _set_active, notify=activeChanged)

    # ---------- settings ----------
    def _get_enabled(self):
        return self._engine.enabled

    def _set_enabled(self, v):
        self._engine.enabled = bool(v)
        self._cfg["enabled"] = bool(v)
        self._save()
        self.enabledChanged.emit()
        self._tick()

    enabled = Property(bool, _get_enabled, _set_enabled, notify=enabledChanged)

    def _get_voice(self):
        return self._cfg["voice_app"]

    def _set_voice(self, v):
        name = str(v).strip().lower()
        if not name:
            return
        if not name.endswith(".exe"):
            name += ".exe"
        if name == self._cfg["voice_app"]:
            return
        self._cfg["voice_app"] = name
        self._save()
        self.voiceChanged.emit()
        self._rebuild_apps()

    voiceApp = Property(str, _get_voice, _set_voice, notify=voiceChanged)

    def _num(key, scale, sig):  # noqa: N805 - small factory for slider properties
        def get(self):
            return float(self._cfg[key]) * scale

        def set_(self, v):
            self._cfg[key] = float(v) / scale
            self._save()
            self.settingsChanged.emit()

        return Property(float, get, set_, notify=sig)

    duckMusic = _num("duck_music", 100.0, settingsChanged)
    duckOther = _num("duck_other", 100.0, settingsChanged)
    sensitivity = _num("sensitivity", 1.0, settingsChanged)

    def _get_autostart(self):
        return self._autostart

    def _set_autostart(self, v):
        try:
            autostart.set_enabled(bool(v))
        except OSError:
            pass
        self._autostart = autostart.is_enabled()
        self._cfg["autostart"] = self._autostart
        self._save()
        self.settingsChanged.emit()

    autostart = Property(bool, _get_autostart, _set_autostart, notify=settingsChanged)

    def _get_min(self):
        return bool(self._cfg["start_minimized"])

    def _set_min(self, v):
        self._cfg["start_minimized"] = bool(v)
        self._save()
        self.settingsChanged.emit()

    startMinimized = Property(bool, _get_min, _set_min, notify=settingsChanged)

    # ---------- slots ----------
    @Slot(str)
    def toggleMusic(self, name):
        apps = [a.lower() for a in self._cfg["music_apps"]]
        if name in apps:
            apps = [a for a in apps if a != name]
        else:
            apps.append(name)
        self._cfg["music_apps"] = apps
        self._save()
        self._rebuild_apps()

    @Slot()
    def quit(self):
        req = getattr(self._engine, "request_quit", None)
        if req:
            try:
                req()
            except (OSError, EOFError):
                pass
        self.quitRequested.emit()

    @Slot()
    def windowClosing(self):
        self.closing.emit()

    # ---------- helpers used by the icon provider ----------
    def icon_path(self, name):
        return self._engine.exe_paths.get(name) or self._cfg.get("app_paths", {}).get(name, "")

    # ---------- internals ----------
    def _rebuild_apps(self):
        ignore = {p.lower() for p in self._cfg["ignore"]} | {"?", self._cfg["voice_app"].lower()}
        selected = {a.lower() for a in self._cfg["music_apps"]}
        names = {n for n, _ in self._engine.apps} | selected
        rows = [
            {"name": n, "selected": n in selected}
            for n in sorted(names)
            if n not in ignore
        ]
        if rows != self._apps:
            self._apps = rows
            self.appsChanged.emit()
        choices = sorted(
            set(KNOWN_CALL_APPS) | {n for n, _ in self._engine.apps if n != "?"}
        )
        if choices != self._choices:
            self._choices = choices
            self.voiceChanged.emit()
        # Remember exe paths so icons still show for apps that are not running.
        paths = self._cfg.setdefault("app_paths", {})
        added = False
        for name, path in self._engine.exe_paths.items():
            if paths.get(name) != path:
                paths[name] = path
                added = True
        if added:
            self._save()
        if len(paths) != self._known_paths or added:
            self._known_paths = len(paths)
            self._icon_version += 1
            self.iconsChanged.emit()

    def _tick(self):
        e = self._engine
        refresh = getattr(e, "refresh", None)
        if refresh:
            try:
                refresh()
            except (OSError, EOFError):  # tray process went away
                self._timer.stop()
                self.quitRequested.emit()
                return
            if getattr(e, "raise_requested", False):
                e.raise_requested = False
                self.raiseRequested.emit()
        if not e.enabled:
            kind, level = "off", 0.0
        elif e.talking:
            kind, level = "talking", min(1.0, e.level * 3)
        else:
            kind, level = "idle", min(1.0, e.level * 3)
        if kind != self._kind:
            self._kind = kind
            self.statusChanged.emit()
        if abs(level - self._level) > 0.01:
            self._level = level
            self.levelChanged.emit()
        self._tick_n += 1
        if self._tick_n % 10 == 1:
            self._rebuild_apps()
            playing = sorted(n for n, p in e.apps if p > 0.001)
            if playing != self._playing:
                self._playing = playing
                self.playingChanged.emit()
