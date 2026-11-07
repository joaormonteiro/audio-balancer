"""Builds dist/AudioBalancer.exe (single file, no console window).

    python tools/make_assets.py   # only when the icon/backdrop design changes
    python build.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
PKG = ROOT / "audio_balancer"
SEP = ";" if sys.platform == "win32" else ":"


def main():
    subprocess.check_call(
        [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm", "--clean", "--onefile", "--noconsole",
            "--name", "AudioBalancer",
            "--icon", str(PKG / "assets" / "icon.ico"),
            "--add-data", f"{PKG / 'qml'}{SEP}audio_balancer/qml",
            "--add-data", f"{PKG / 'assets'}{SEP}audio_balancer/assets",
            "--hidden-import", "comtypes.stream",
            "--exclude-module", "tkinter",
            "--exclude-module", "PySide6.QtWebEngineCore",
            "--exclude-module", "PySide6.QtPdf",
            "--exclude-module", "PySide6.QtSql",
            "--exclude-module", "PySide6.QtTest",
            str(ROOT / "run.py"),
        ],
        cwd=ROOT,
    )
    print("Done:", ROOT / "dist" / "AudioBalancer.exe")


if __name__ == "__main__":
    main()
