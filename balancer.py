"""Audio balancer: abaixa musica e jogo quando alguem fala na call.

Uso:
    python balancer.py          roda o balanceador
    python balancer.py --list   lista apps com audio e o nivel de cada um
"""
import atexit
import json
import sys
import time
from pathlib import Path

from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioMeterInformation

CONFIG = Path(__file__).with_name("config.json")


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


def list_mode():
    for _ in range(10):
        rows = [(proc_name(s), peak(s)) for s in AudioUtilities.GetAllSessions()]
        print("  ".join(f"{n}={p:.3f}" for n, p in rows))
        time.sleep(0.5)


class Tracked:
    """Estado de um app que pode ser abaixado."""

    def __init__(self, session, duck):
        self.session = session
        self.duck = duck
        self.mult = 1.0
        vol = session.SimpleAudioVolume
        self.base = vol.GetMasterVolume()
        self.last_applied = self.base

    def update(self, target_mult, step):
        vol = self.session.SimpleAudioVolume
        try:
            current = vol.GetMasterVolume()
            # Se o usuario mexeu no volume na mao, reaprende o volume base.
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


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    voice_procs = {p.lower() for p in cfg["voice"]["processes"]}
    ignore = {p.lower() for p in cfg["ignore"]} | voice_procs
    rule_map = {}
    for rule in cfg["rules"]:
        for p in rule["processes"]:
            rule_map[p.lower()] = rule["duck"]
    default_duck = cfg.get("default_duck")
    poll = cfg["poll_ms"] / 1000
    threshold = cfg["voice"]["threshold"]
    min_speech = cfg["voice"]["min_speech_ms"] / 1000
    hold = cfg["voice"]["hold_ms"] / 1000
    down_step = poll / (cfg["fade_down_ms"] / 1000)
    up_step = poll / (cfg["fade_up_ms"] / 1000)

    tracked = {}
    atexit.register(lambda: [t.restore() for t in tracked.values()])

    talking = False
    above_since = None
    last_above = 0.0
    last_refresh = 0.0
    print("Rodando. Ctrl+C pra parar (volumes sao restaurados).")

    while True:
        now = time.monotonic()

        if now - last_refresh > 1.0:
            last_refresh = now
            sessions = AudioUtilities.GetAllSessions()
            seen = set()
            voice_sessions = []
            for s in sessions:
                name = proc_name(s)
                key = sid(s)
                if name in voice_procs:
                    voice_sessions.append(s)
                    continue
                if name in ignore:
                    continue
                duck = rule_map.get(name, default_duck)
                if duck is None:
                    continue
                seen.add(key)
                if key not in tracked:
                    tracked[key] = Tracked(s, duck)
                    print(f"+ {name} (duck {int(duck * 100)}%)")
                else:
                    tracked[key].session = s
            for key in [k for k in tracked if k not in seen]:
                del tracked[key]

        level = max((peak(s) for s in voice_sessions), default=0.0)
        if level > threshold:
            last_above = now
            if above_since is None:
                above_since = now
            if not talking and now - above_since >= min_speech:
                talking = True
                print("fala detectada: abaixando")
        else:
            above_since = None
            if talking and now - last_above > hold:
                talking = False
                print("silencio: voltando")

        for t in tracked.values():
            target = (1.0 - t.duck) if talking else 1.0
            t.update(target, down_step if talking else up_step)

        time.sleep(poll)


if __name__ == "__main__":
    try:
        if "--list" in sys.argv:
            list_mode()
        else:
            main()
    except KeyboardInterrupt:
        pass
