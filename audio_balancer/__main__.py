"""Entry point.

    python -m audio_balancer             opens the window (default)
    python -m audio_balancer --minimized starts hidden in the tray
    python -m audio_balancer --cli       console mode, no window
    python -m audio_balancer --debug     console mode with live levels
    python -m audio_balancer --list      list apps producing sound
"""
import ctypes
import sys
import time

from . import config as cfgmod
from .engine import Engine, snapshot


def single_instance() -> bool:
    """False if another copy is already running."""
    try:
        ctypes.windll.kernel32.CreateMutexW(None, False, "AudioBalancerSingleton")
        return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return True


def list_mode():
    for _ in range(10):
        rows = snapshot()
        print("  ".join(f"{n}@{d[-8:]}={p:.3f}" for n, d, p in rows))
        time.sleep(0.5)


def selftest(path: str):
    """Writes the detected audio apps to a JSON file (works in the no-console exe)."""
    import json

    out = {"ok": False, "apps": [], "error": None}
    try:
        for name, device, level in snapshot():
            out["apps"].append({"name": name, "device": device[-12:], "peak": round(level, 3)})
        out["ok"] = True
    except Exception as exc:  # report instead of crashing
        out["error"] = repr(exc)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


def cli(debug: bool):
    cfg = cfgmod.load()
    cfg["enabled"] = True
    engine = Engine(cfg, log=print, debug=debug)
    engine.start()
    print("Running. Ctrl+C to stop (volumes are restored).")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    engine.stop()


def gui(start_hidden: bool):
    from .gui import run
    from .i18n import t

    if not single_instance():
        try:
            ctypes.windll.user32.MessageBoxW(0, t("running"), t("title"), 0x40)
        except Exception:
            print(t("running"))
        return
    cfg = cfgmod.load()
    engine = Engine(cfg)
    engine.start()
    try:
        run(engine, cfg, start_hidden=start_hidden or cfg["start_minimized"])
    finally:
        engine.stop()


def lower_priority():
    """Stay out of the game's way: run below normal priority."""
    try:
        import psutil

        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass


def main():
    args = sys.argv[1:]
    lower_priority()
    if "--selftest" in args:
        i = args.index("--selftest")
        selftest(args[i + 1] if i + 1 < len(args) else "selftest.json")
    elif "--ui" in args:
        from .gui import run_window

        sys.exit(run_window())
    elif "--list" in args:
        list_mode()
    elif "--cli" in args or "--debug" in args:
        cli("--debug" in args)
    else:
        gui("--minimized" in args)


if __name__ == "__main__":
    main()
