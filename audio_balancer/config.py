"""User settings, stored in %APPDATA%\\audio-balancer\\config.json."""
import json
import os
from pathlib import Path

DEFAULTS = {
    "voice_app": "discord.exe",
    "music_apps": [
        "spotify.exe",
        "chrome.exe",
        "msedge.exe",
        "firefox.exe",
        "brave.exe",
        "vlc.exe",
    ],
    "duck_music": 0.75,   # how much the music drops while someone talks
    "duck_other": 0.40,   # how much everything else (games...) drops
    "sensitivity": 3.0,   # 1 (needs loud voice) to 10 (very sensitive)
    "hold_ms": 1200,      # silence needed before volumes come back
    "min_speech_ms": 150,
    "fade_down_ms": 150,
    "fade_up_ms": 800,
    "poll_ms": 50,
    "ignore": ["audiodg.exe", "explorer.exe"],
    "app_paths": {},       # process name -> exe path, remembered for icons
    "enabled": True,
    "autostart": False,
    "start_minimized": False,
}


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "audio-balancer"


def config_path() -> Path:
    return config_dir() / "config.json"


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
        if isinstance(data, dict):
            cfg.update({k: v for k, v in data.items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return cfg


def save(cfg: dict) -> None:
    try:
        config_dir().mkdir(parents=True, exist_ok=True)
        config_path().write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except OSError:
        pass


def threshold(cfg: dict) -> float:
    """Voice threshold derived from the 1..10 sensitivity slider."""
    return 0.06 / max(0.5, float(cfg["sensitivity"]))
