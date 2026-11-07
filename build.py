"""Builds dist/AudioBalancer.exe (single file, no console window).

    python build.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def main():
    from audio_balancer.gui import make_icon

    ico = ROOT / "build" / "icon.ico"
    ico.parent.mkdir(exist_ok=True)
    make_icon(256).save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

    subprocess.check_call(
        [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm", "--clean", "--onefile", "--noconsole",
            "--name", "AudioBalancer",
            "--icon", str(ico),
            "--collect-all", "customtkinter",
            "--hidden-import", "comtypes.stream",
            "--hidden-import", "pystray._win32",
            str(ROOT / "run.py"),
        ],
        cwd=ROOT,
    )
    print("Done:", ROOT / "dist" / "AudioBalancer.exe")


if __name__ == "__main__":
    main()
