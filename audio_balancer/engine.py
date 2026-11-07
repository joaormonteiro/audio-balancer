"""Audio engine: detects speech in the call app and ducks music and games."""
import threading
import time
from collections import deque

import comtypes
from pycaw.constants import DEVICE_STATE, EDataFlow
from pycaw.pycaw import (
    AudioSession,
    AudioUtilities,
    IAudioMeterInformation,
    IAudioSessionControl2,
)

from . import config as cfgmod

LEAK_WINDOW = 8.0     # seconds of history used to estimate the leak
LEAK_QUANTILE = 0.2   # low percentile: speech only ever adds level
LEAK_MARGIN = 1.15    # safety margin over the estimated leak
LEAK_MIN_SAMPLES = 20


def get_all_sessions():
    """Audio sessions on EVERY active output device (monitor, speakers, TV...)."""
    sessions = []
    devices = AudioUtilities.GetAllDevices(
        EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value
    )
    for dev in devices:
        try:
            mgr = dev.AudioSessionManager
            enum = mgr.GetSessionEnumerator()
            for i in range(enum.GetCount()):
                ctl = enum.GetSession(i)
                if ctl is None:
                    continue
                ctl2 = ctl.QueryInterface(IAudioSessionControl2)
                if ctl2 is not None:
                    s = AudioSession(ctl2)
                    s.device_name = dev.FriendlyName
                    sessions.append(s)
        except Exception:
            continue
    return sessions


def proc_name(session):
    try:
        return session.Process.name().lower() if session.Process else "systemsounds"
    except Exception:
        return "?"


def peak(session):
    try:
        meter = session._ctl.QueryInterface(IAudioMeterInformation)
        return meter.GetPeakValue()
    except Exception:
        return 0.0


def sid(session):
    try:
        return session.InstanceIdentifier
    except Exception:
        return str(session.ProcessId)


class Tracked:
    """State of one app whose volume can be lowered."""

    def __init__(self, session, duck):
        self.session = session
        self.duck = duck
        self.mult = 1.0
        self.base = session.SimpleAudioVolume.GetMasterVolume()
        self.last_applied = self.base

    def update(self, target_mult, step):
        vol = self.session.SimpleAudioVolume
        try:
            current = vol.GetMasterVolume()
            # If the user changed the volume by hand, relearn the base volume.
            if abs(current - self.last_applied) > 0.02:
                self.base = min(1.0, current / max(self.mult, 0.05))
            if self.mult < target_mult:
                self.mult = min(target_mult, self.mult + step)
            else:
                self.mult = max(target_mult, self.mult - step)
            new = self.base * self.mult
            vol.SetMasterVolume(new, None)
            self.last_applied = new
        except Exception:
            pass

    def restore(self):
        try:
            self.session.SimpleAudioVolume.SetMasterVolume(self.base, None)
        except Exception:
            pass


class Engine:
    """Runs in a background thread. Reads `cfg` live, so the UI can change it."""

    def __init__(self, cfg, log=None, debug=False):
        self.cfg = cfg
        self.log = log or (lambda msg: None)
        self.debug = debug
        self.enabled = bool(cfg.get("enabled", True))
        # Live state, read by the UI.
        self.talking = False
        self.level = 0.0
        self.leak_ratio = 0.22
        self.apps = []  # [(process name, peak)] of every app producing sound
        self._halt = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._halt.set()
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

    def _loop(self, tracked):
        ratios = deque()
        voice_sessions, others = [], []
        talking = False
        above_since = None
        last_above = 0.0
        last_refresh = -10.0
        last_print = 0.0

        while not self._halt.is_set():
            cfg = self.cfg
            poll = cfg["poll_ms"] / 1000
            now = time.monotonic()

            # 1) Refresh the session list once per second.
            if now - last_refresh > 1.0:
                last_refresh = now
                voice_proc = cfg["voice_app"].lower()
                music = {p.lower() for p in cfg["music_apps"]}
                ignore = {p.lower() for p in cfg["ignore"]}
                seen, names = set(), {}
                voice_sessions, others = [], []
                for s in get_all_sessions():
                    name = proc_name(s)
                    p = peak(s)
                    if name != "systemsounds":
                        names[name] = max(names.get(name, 0.0), p)
                    if name == voice_proc:
                        voice_sessions.append(s)
                        continue
                    if name != "systemsounds":
                        others.append(s)
                    if name in ignore or name in ("systemsounds", "?"):
                        continue
                    duck = cfg["duck_music"] if name in music else cfg["duck_other"]
                    if duck <= 0:
                        continue
                    key = sid(s)
                    seen.add(key)
                    if key not in tracked:
                        tracked[key] = Tracked(s, duck)
                        self.log(f"+ {name} (duck {int(duck * 100)}%)")
                    else:
                        tracked[key].session = s
                        tracked[key].duck = duck
                for key in [k for k in tracked if k not in seen]:
                    del tracked[key]
                self.apps = sorted(names.items())

            # 2) Paused: give volumes back and idle.
            if not self.enabled:
                if tracked:
                    for t in tracked.values():
                        t.restore()
                    tracked.clear()
                    last_refresh = -10.0
                talking = self.talking = False
                self.level = 0.0
                ratios.clear()
                self._halt.wait(0.2)
                continue

            # 3) Speech detection. The call app's meter "leaks" a fraction of
            # what other apps play on the same device (post volume), so
            # voice = call level minus the expected leak.
            mix = {}
            for o in others:
                try:
                    eff = peak(o) * o.SimpleAudioVolume.GetMasterVolume()
                except Exception:
                    eff = 0.0
                mix[o.device_name] = mix.get(o.device_name, 0.0) + eff

            # The leak ratio drifts (song, TV volume...), so estimate it
            # continuously: speech only adds level, so the lowest ratios in
            # the window reveal the real leak.
            for s in voice_sessions:
                m = mix.get(s.device_name, 0.0)
                r = peak(s)
                if m > 0.05 and r > 0:
                    ratios.append((now, r / m))
            while ratios and now - ratios[0][0] > LEAK_WINDOW:
                ratios.popleft()
            if len(ratios) >= LEAK_MIN_SAMPLES:
                vals = sorted(v for _, v in ratios)
                self.leak_ratio = vals[int(len(vals) * LEAK_QUANTILE)]

            level, top = 0.0, None
            for s in voice_sessions:
                raw = peak(s)
                m = mix.get(s.device_name, 0.0)
                lvl = max(0.0, raw - LEAK_MARGIN * self.leak_ratio * m)
                if m > 0.05 and len(ratios) < LEAK_MIN_SAMPLES:
                    lvl = 0.0  # still learning the leak: do not decide yet
                if lvl >= level:
                    level, top = lvl, s
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
            self.talking = talking

            if self.debug and now - last_print >= 0.5:
                last_print = now
                self.log(
                    f"level={level:.3f} threshold={threshold:.3f} "
                    f"leak={self.leak_ratio:.2f} talking={talking}"
                )

            # 4) Fade volumes toward their targets.
            down = poll / (cfg["fade_down_ms"] / 1000)
            up = poll / (cfg["fade_up_ms"] / 1000)
            for t in tracked.values():
                target = (1.0 - t.duck) if talking else 1.0
                t.update(target, down if talking else up)

            self._halt.wait(poll)
