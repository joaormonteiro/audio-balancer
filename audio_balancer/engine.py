"""Audio engine: detects speech in the call app and ducks music and games.

Built to be cheap while a game is running: COM interfaces are cached, the device
list is only re-read now and then, nothing is polled when there is no call or
the app is paused, and volumes are only written when they actually change.
"""
import threading
import time
from collections import deque

import comtypes
import psutil
from pycaw.constants import DEVICE_STATE, EDataFlow
from pycaw.pycaw import (
    IAudioMeterInformation,
    IAudioSessionControl2,
    IAudioSessionManager2,
    ISimpleAudioVolume,
)
from pycaw.utils import CLSID_MMDeviceEnumerator, IMMDeviceEnumerator

from . import config as cfgmod

LEAK_WINDOW = 8.0     # seconds of history used to estimate the leak
LEAK_QUANTILE = 0.2   # low percentile: speech only ever adds level
LEAK_MARGIN = 1.15    # safety margin over the estimated leak
LEAK_MIN_SAMPLES = 20

DEVICE_REFRESH = 10.0  # seconds between re-reading the list of output devices
IDLE_POLL = 0.25       # poll interval when there is nothing to listen to


class Names:
    """pid -> (process name, exe path), cached so psutil is rarely touched."""

    def __init__(self):
        self._c = {}

    def lookup(self, pid, want_exe=False):
        ent = self._c.get(pid)
        if ent is None:
            if pid == 0:
                ent = ["systemsounds", "", True]
            else:
                try:
                    ent = [psutil.Process(pid).name().lower(), "", False]
                except Exception:
                    ent = ["?", "", True]
            self._c[pid] = ent
        if want_exe and not ent[2]:
            ent[2] = True
            try:
                ent[1] = psutil.Process(pid).exe()
            except Exception:
                pass
        return ent[0], ent[1]

    def prune(self, alive):
        for pid in [p for p in self._c if p not in alive]:
            del self._c[pid]


class Sess:
    """One audio session with lazily cached COM interfaces."""

    __slots__ = ("ctl", "device", "key", "pid", "name", "_meter", "_vol")

    def __init__(self, ctl, device, key, pid, name):
        self.ctl, self.device, self.key = ctl, device, key
        self.pid, self.name = pid, name
        self._meter = None
        self._vol = None

    def peak(self):
        try:
            if self._meter is None:
                self._meter = self.ctl.QueryInterface(IAudioMeterInformation)
            return self._meter.GetPeakValue()
        except Exception:
            self._meter = None
            return 0.0

    def get_volume(self):
        try:
            if self._vol is None:
                self._vol = self.ctl.QueryInterface(ISimpleAudioVolume)
            return self._vol.GetMasterVolume()
        except Exception:
            self._vol = None
            return None

    def set_volume(self, v):
        try:
            if self._vol is None:
                self._vol = self.ctl.QueryInterface(ISimpleAudioVolume)
            self._vol.SetMasterVolume(max(0.0, min(1.0, v)), None)
        except Exception:
            self._vol = None


class Tracked:
    """State of one app whose volume can be lowered."""

    def __init__(self, sess, duck):
        self.sess = sess
        self.duck = duck
        self.mult = 1.0
        cur = sess.get_volume()
        self.base = 1.0 if cur is None else cur
        self.last_applied = self.base
        self._next_check = 0.0

    def update(self, target, step, now):
        ramping = self.mult != target
        if not ramping and now < self._next_check:
            return  # steady state: no COM calls at all
        if now >= self._next_check:
            self._next_check = now + 0.5
            cur = self.sess.get_volume()
            # If the user changed the volume by hand, relearn the base volume.
            if cur is not None and abs(cur - self.last_applied) > 0.02:
                self.base = min(1.0, cur / max(self.mult, 0.05))
                self.last_applied = cur
        if ramping:
            if self.mult < target:
                self.mult = min(target, self.mult + step)
            else:
                self.mult = max(target, self.mult - step)
            new = self.base * self.mult
            self.sess.set_volume(new)
            self.last_applied = new

    def restore(self):
        self.sess.set_volume(self.base)


def snapshot():
    """One-shot list of (process, device id, peak) for --list and --selftest."""
    eng = Engine({"enabled": False, "voice_app": "", "music_apps": [], "ignore": [],
                  "duck_music": 0, "duck_other": 0, "poll_ms": 50})
    comtypes.CoInitialize()
    try:
        eng._scan(time.monotonic(), False)
        return [(s.name, s.device, s.peak()) for s in eng._sessions.values()]
    finally:
        comtypes.CoUninitialize()


class Engine:
    """Runs in a background thread. Reads `cfg` live, so the UI can change it."""

    def __init__(self, cfg, log=None, debug=False):
        self.cfg = cfg
        self.log = log or (lambda msg: None)
        self.debug = debug
        self._wake = threading.Event()
        self._enabled = bool(cfg.get("enabled", True))
        # Set by the UI while its window is open (needs the app list + icons).
        self.want_apps = False
        # Live state, read by the UI.
        self.talking = False
        self.level = 0.0
        self.leak_ratio = 0.22
        self.on_state = None  # called from the engine thread when `talking` flips
        self.apps = []        # [(process name, peak)] of every app producing sound
        self.exe_paths = {}   # process name -> exe path (for icons)
        self._halt = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._names = Names()
        self._mgrs = None
        self._mgr_t = 0.0
        self._sessions = {}

    # `enabled` wakes the loop so pausing/resuming feels instant.
    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, v):
        self._enabled = bool(v)
        self._wake.set()

    def start(self):
        self._thread.start()

    def stop(self):
        self._halt.set()
        self._wake.set()
        self._thread.join(timeout=3)

    def _run(self):
        comtypes.CoInitialize()
        tracked = {}
        try:
            self._loop(tracked)
        finally:
            for t in tracked.values():
                t.restore()
            comtypes.CoUninitialize()

    # ---------- audio session discovery ----------
    def _managers(self, now):
        if self._mgrs is not None and now - self._mgr_t < DEVICE_REFRESH:
            return self._mgrs
        mgrs = []
        try:
            enum = comtypes.CoCreateInstance(
                CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, comtypes.CLSCTX_INPROC_SERVER
            )
            coll = enum.EnumAudioEndpoints(EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value)
            for i in range(coll.GetCount()):
                try:
                    dev = coll.Item(i)
                    iface = dev.Activate(IAudioSessionManager2._iid_, comtypes.CLSCTX_ALL, None)
                    mgrs.append((dev.GetId(), iface.QueryInterface(IAudioSessionManager2)))
                except Exception:
                    continue
        except Exception:
            pass
        self._mgrs, self._mgr_t = mgrs, now
        return mgrs

    def _scan(self, now, want_exe):
        found = {}
        for dev_id, mgr in self._managers(now):
            try:
                enum = mgr.GetSessionEnumerator()
                for i in range(enum.GetCount()):
                    ctl = enum.GetSession(i)
                    if ctl is None:
                        continue
                    ctl2 = ctl.QueryInterface(IAudioSessionControl2)
                    if ctl2 is None:
                        continue
                    key = ctl2.GetSessionInstanceIdentifier()
                    s = self._sessions.get(key)
                    if s is None:
                        pid = ctl2.GetProcessId()
                        name, _ = self._names.lookup(pid)
                        s = Sess(ctl2, dev_id, key, pid, name)
                    found[key] = s
            except Exception:
                self._mgr_t = 0.0  # a device probably went away: re-read the list
        self._sessions = found
        self._names.prune({s.pid for s in found.values()})
        if want_exe:
            for s in found.values():
                name, exe = self._names.lookup(s.pid, True)
                if exe and name not in self.exe_paths:
                    self.exe_paths[name] = exe
        return found

    # ---------- main loop ----------
    def _loop(self, tracked):
        ratios = deque()
        voice, others = [], []
        talking = False
        above_since = None
        last_above = 0.0
        last_refresh = -100.0
        last_print = 0.0

        while not self._halt.is_set():
            cfg = self.cfg
            now = time.monotonic()
            enabled = self._enabled

            # Paused and nobody looking at the window: do absolutely nothing.
            if not enabled and not self.want_apps:
                if tracked:
                    for t in tracked.values():
                        t.restore()
                    tracked.clear()
                talking = self.talking = False
                self.level = 0.0
                ratios.clear()
                voice, others = [], []
                last_refresh = -100.0
                self._wake.wait(2.0)
                self._wake.clear()
                continue

            # 1) Refresh the session list (rarely when idle).
            active = enabled and bool(voice)
            every = 1.0 if (self.want_apps or active) else (2.0 if enabled else 3.0)
            if now - last_refresh >= every:
                last_refresh = now
                found = self._scan(now, self.want_apps)
                voice_proc = cfg["voice_app"].lower()
                music = {p.lower() for p in cfg["music_apps"]}
                ignore = {p.lower() for p in cfg["ignore"]}
                voice, others = [], []
                seen = set()
                for s in found.values():
                    if s.name == voice_proc:
                        voice.append(s)
                        continue
                    if s.name != "systemsounds":
                        others.append(s)
                    if not enabled or s.name in ignore or s.name in ("systemsounds", "?"):
                        continue
                    duck = cfg["duck_music"] if s.name in music else cfg["duck_other"]
                    if duck <= 0:
                        continue
                    seen.add(s.key)
                    t = tracked.get(s.key)
                    if t is None:
                        tracked[s.key] = Tracked(s, duck)
                        self.log(f"+ {s.name} (duck {int(duck * 100)}%)")
                    else:
                        t.sess = s
                        t.duck = duck
                for key in [k for k in tracked if k not in seen]:
                    del tracked[key]
                if self.want_apps:
                    names = {}
                    for s in found.values():
                        if s.name != "systemsounds":
                            names[s.name] = max(names.get(s.name, 0.0), s.peak())
                    self.apps = sorted(names.items())
                active = enabled and bool(voice)

            # 2) Paused with the window open: keep volumes normal, idle slowly.
            if not enabled:
                if tracked:
                    for t in tracked.values():
                        t.restore()
                    tracked.clear()
                talking = self.talking = False
                self.level = 0.0
                ratios.clear()
                self._wake.wait(0.5)
                self._wake.clear()
                continue

            # 3) Speech detection. The call app's meter "leaks" a fraction of
            # what other apps play on the same device (post volume), so
            # voice = call level minus the expected leak.
            level = 0.0
            if voice:
                mix = {}
                for o in others:
                    t = tracked.get(o.key)
                    vol = t.last_applied if t is not None else o.get_volume()
                    eff = o.peak() * (1.0 if vol is None else vol)
                    mix[o.device] = mix.get(o.device, 0.0) + eff

                # The leak ratio drifts (song, TV volume...), so estimate it
                # continuously: speech only adds level, so the lowest ratios
                # in the window reveal the real leak.
                raws = [(v, v.peak()) for v in voice]
                for v, r in raws:
                    m = mix.get(v.device, 0.0)
                    if m > 0.05 and r > 0:
                        ratios.append((now, r / m))
                while ratios and now - ratios[0][0] > LEAK_WINDOW:
                    ratios.popleft()
                if len(ratios) >= LEAK_MIN_SAMPLES:
                    vals = sorted(x for _, x in ratios)
                    self.leak_ratio = vals[int(len(vals) * LEAK_QUANTILE)]

                for v, r in raws:
                    m = mix.get(v.device, 0.0)
                    lvl = max(0.0, r - LEAK_MARGIN * self.leak_ratio * m)
                    if m > 0.05 and len(ratios) < LEAK_MIN_SAMPLES:
                        lvl = 0.0  # still learning the leak: do not decide yet
                    level = max(level, lvl)
            self.level = level

            threshold = cfgmod.threshold(cfg)
            min_speech = cfg["min_speech_ms"] / 1000
            hold = cfg["hold_ms"] / 1000
            if level > threshold:
                last_above = now
                if above_since is None:
                    above_since = now
                if not talking and now - above_since >= min_speech:
                    talking = True
                    self.log(f"speech detected (level {level:.3f}): lowering")
            else:
                above_since = None
                if talking and now - last_above > hold:
                    talking = False
                    self.log("quiet: restoring")
            if not voice:
                talking = False
            if talking != self.talking:
                self.talking = talking
                if self.on_state is not None:
                    self.on_state(talking)

            if self.debug and now - last_print >= 0.5:
                last_print = now
                self.log(
                    f"level={level:.3f} threshold={threshold:.3f} "
                    f"leak={self.leak_ratio:.2f} talking={talking}"
                )

            # 4) Fade volumes toward their targets.
            poll = cfg["poll_ms"] / 1000
            down = poll / (cfg["fade_down_ms"] / 1000)
            up = poll / (cfg["fade_up_ms"] / 1000)
            fading = False
            for t in tracked.values():
                target = (1.0 - t.duck) if talking else 1.0
                t.update(target, down if talking else up, now)
                if t.mult != target:
                    fading = True

            # Poll fast only while there is a call to listen to (or a fade).
            wait = poll if (voice or fading) else IDLE_POLL
            self._wake.wait(wait)
            self._wake.clear()
