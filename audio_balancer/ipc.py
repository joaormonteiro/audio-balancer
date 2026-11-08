"""Tiny local IPC between the tray process (engine) and the window process.

The window runs in its own process so that closing it gives every byte of Qt
Quick back; the always-on tray process stays small. Both ends talk over a
localhost socket protected by a random per-launch key.
"""
import os
import secrets
import sys
import threading
from multiprocessing.connection import Client, Listener

ENV_PORT = "AB_PORT"
ENV_KEY = "AB_KEY"


class Server:
    """Lives in the tray process and exposes the engine to the window process."""

    def __init__(self, engine, cfg, save, on_quit, on_enabled):
        self.engine, self.cfg = engine, cfg
        self._save, self._on_quit, self._on_enabled = save, on_quit, on_enabled
        self.raise_flag = False
        self.key = secrets.token_bytes(16)
        self._listener = Listener(("127.0.0.1", 0), authkey=self.key)
        self.port = self._listener.address[1]
        threading.Thread(target=self._accept, daemon=True).start()

    def env(self):
        return {ENV_PORT: str(self.port), ENV_KEY: self.key.hex()}

    def _accept(self):
        while True:
            try:
                conn = self._listener.accept()
            except Exception:
                continue
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn):
        try:
            while True:
                conn.send(self._handle(conn.recv()))
        except (EOFError, OSError):
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass
            self.engine.want_apps = False  # the window is gone: stop listing apps

    def _handle(self, m):
        e, cmd = self.engine, m.get("cmd")
        if cmd == "get":
            r = {
                "enabled": e.enabled,
                "talking": e.talking,
                "level": e.level,
                "apps": list(e.apps),
                "exe_paths": dict(e.exe_paths),
                "raise": self.raise_flag,
            }
            self.raise_flag = False
            return r
        if cmd == "enabled":
            e.enabled = bool(m["value"])
            self.cfg["enabled"] = e.enabled
            self._save()
            self._on_enabled(e.enabled)
        elif cmd == "want_apps":
            e.want_apps = bool(m["value"])
        elif cmd == "cfg":
            self.cfg.update(m["cfg"])
            self._save()
        elif cmd == "quit":
            self._on_quit()
        return {"ok": True}


class RemoteEngine:
    """Looks like an Engine to the UI backend, but talks to the tray process."""

    def __init__(self, port, key):
        self._c = Client(("127.0.0.1", port), authkey=key)
        self._enabled = True
        self._want_apps = False
        self.talking = False
        self.level = 0.0
        self.apps = []
        self.exe_paths = {}
        self.raise_requested = False

    @classmethod
    def from_env(cls):
        return cls(int(os.environ[ENV_PORT]), bytes.fromhex(os.environ[ENV_KEY]))

    def _call(self, **msg):
        self._c.send(msg)
        return self._c.recv()

    def refresh(self):
        r = self._call(cmd="get")
        self._enabled = r["enabled"]
        self.talking, self.level = r["talking"], r["level"]
        self.apps, self.exe_paths = r["apps"], r["exe_paths"]
        if r["raise"]:
            self.raise_requested = True

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, v):
        self._enabled = bool(v)
        self._call(cmd="enabled", value=self._enabled)

    @property
    def want_apps(self):
        return self._want_apps

    @want_apps.setter
    def want_apps(self, v):
        self._want_apps = bool(v)
        self._call(cmd="want_apps", value=self._want_apps)

    def push_cfg(self, cfg):
        self._call(cmd="cfg", cfg=cfg)

    def request_quit(self):
        self._call(cmd="quit")


def ui_command():
    """Command line that starts the window process."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--ui"]
    return [sys.executable, "-m", "audio_balancer", "--ui"]
