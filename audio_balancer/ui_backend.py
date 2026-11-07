"""Bridge between the audio engine / settings and the QML interface."""
from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from . import autostart
from . import config as cfgmod
from .i18n import STRINGS, LANG

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
    showRequested = Signal()
    quitRequested = Signal()

    def __init__(self, engine, cfg, assets_url, glass, start_hidden, max_height=760, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._cfg = cfg
        self._assets = assets_url
        self._glass = glass
        self._start_hidden = start_hidden
        self._max_height = float(max_height)
        self._kind = "idle"
        self._level = 0.0
        self._apps = []
        self._playing = []
        self._choices = list(KNOWN_CALL_APPS)
        self._autostart = autostart.is_enabled()
        self._tick_n = 0
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ---------- constants for QML ----------
    @Property("QVariantMap", constant=True)
    def tr(self):
        return STRINGS.get(LANG, STRINGS["en"])

    @Property(str, constant=True)
    def assets(self):
        return self._assets

    @Property(bool, constant=True)
    def glass(self):
        return self._glass

    @Property(float, constant=True)
    def maxHeight(self):
        return self._max_height

    @Property(bool, constant=True)
    def startHidden(self):
        return self._start_hidden

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

    @Property("QVariantList", notify=playingChanged)
    def playing(self):
        return self._playing

    @Property("QVariantList", notify=voiceChanged)
    def voiceChoices(self):
        return self._choices

    # ---------- settings ----------
    def _get_enabled(self):
        return self._engine.enabled

    def _set_enabled(self, v):
        self._engine.enabled = bool(v)
        self._cfg["enabled"] = bool(v)
        cfgmod.save(self._cfg)
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
        cfgmod.save(self._cfg)
        self.voiceChanged.emit()
        self._rebuild_apps()

    voiceApp = Property(str, _get_voice, _set_voice, notify=voiceChanged)

    def _num(key, scale, sig):  # noqa: N805 - small factory for slider properties
        def get(self):
            return float(self._cfg[key]) * scale

        def set_(self, v):
            self._cfg[key] = float(v) / scale
            cfgmod.save(self._cfg)
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
        cfgmod.save(self._cfg)
        self.settingsChanged.emit()

    autostart = Property(bool, _get_autostart, _set_autostart, notify=settingsChanged)

    def _get_min(self):
        return bool(self._cfg["start_minimized"])

    def _set_min(self, v):
        self._cfg["start_minimized"] = bool(v)
        cfgmod.save(self._cfg)
        self.settingsChanged.emit()

    startMinimized = Property(bool, _get_min, _set_min, notify=settingsChanged)

    # ---------- slots ----------
    @Slot(str, bool)
    def setMusicApp(self, name, on):
        apps = [a.lower() for a in self._cfg["music_apps"]]
        if on and name not in apps:
            apps.append(name)
        if not on:
            apps = [a for a in apps if a != name]
        self._cfg["music_apps"] = apps
        cfgmod.save(self._cfg)
        self._rebuild_apps()

    @Slot()
    def quit(self):
        self.quitRequested.emit()

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

    def _tick(self):
        e = self._engine
        if not e.enabled:
            kind, level = "off", 0.0
        elif e.talking:
            kind, level = "talking", min(1.0, e.level * 3)
        else:
            kind, level = "idle", min(1.0, e.level * 3)
        if kind != self._kind:
            self._kind = kind
            self.statusChanged.emit()
        if abs(level - self._level) > 0.005:
            self._level = level
            self.levelChanged.emit()
        self._tick_n += 1
        if self._tick_n % 10 == 1:
            self._rebuild_apps()
            playing = sorted(n for n, p in e.apps if p > 0.001)
            if playing != self._playing:
                self._playing = playing
                self.playingChanged.emit()

    @property
    def kind_value(self):
        return self._kind
