"""Window + system tray interface."""
import queue

import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw

from . import autostart
from . import config as cfgmod
from .i18n import t

ACCENT = "#2fa572"
TALK = "#e0a030"
OFF = "#8a8a8a"

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


def make_icon(size=64, color=ACCENT):
    """A simple speaker-with-waves icon, drawn at runtime (no image files)."""
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=s // 5, fill=(24, 28, 34, 255))
    u = s / 16
    d.polygon(
        [(3 * u, 6 * u), (6 * u, 6 * u), (9.5 * u, 3 * u), (9.5 * u, 13 * u),
         (6 * u, 10 * u), (3 * u, 10 * u)],
        fill=color,
    )
    for r in (3.2, 5.6):
        box = (9.5 * u - r * u, 8 * u - r * u, 9.5 * u + r * u, 8 * u + r * u)
        d.arc(box, -50, 50, fill=color, width=int(u * 0.9))
    return img.resize((size, size), Image.LANCZOS)


class App(ctk.CTk):
    def __init__(self, engine, cfg, start_hidden=False):
        super().__init__()
        self.engine = engine
        self.cfg = cfg
        self.q = queue.Queue()
        self._app_key = None

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("green")
        self.title(t("title"))
        self.geometry("460x640")
        self.minsize(420, 600)
        icon = make_icon(64)
        try:
            from PIL import ImageTk
            self._tk_icon = ImageTk.PhotoImage(icon)
            self.iconphoto(True, self._tk_icon)
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self.hide)

        self._build()
        self._fit_height()
        self._start_tray(icon)
        self.after(100, self._tick)
        if start_hidden:
            self.after(50, self.withdraw)

    def _fit_height(self):
        """Size the window to its content, but never taller than the screen."""
        self.update_idletasks()
        try:
            scale = self._get_window_scaling()
        except Exception:
            scale = 1.0
        want = self.winfo_reqheight() / scale
        room = (self.winfo_screenheight() - 90) / scale
        h = int(max(520, min(want + 4, room)))
        self.geometry(f"460x{h}")
        self.minsize(420, min(h, 520))

    # ---------- layout ----------
    def _build(self):
        pad = {"padx": 20}
        ctk.CTkLabel(self, text=t("title"), font=ctk.CTkFont(size=24, weight="bold")).pack(
            anchor="w", pady=(14, 0), **pad
        )
        ctk.CTkLabel(self, text=t("subtitle"), text_color=("gray35", "gray65")).pack(
            anchor="w", pady=(0, 8), **pad
        )

        card = ctk.CTkFrame(self, corner_radius=12)
        card.pack(fill="x", pady=(0, 10), **pad)
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(8, 4))
        self.dot = ctk.CTkLabel(top, text="●", font=ctk.CTkFont(size=18), text_color=OFF)
        self.dot.pack(side="left")
        self.status = ctk.CTkLabel(top, text="", anchor="w", wraplength=300, justify="left")
        self.status.pack(side="left", padx=8, fill="x", expand=True)
        self.enable_var = ctk.BooleanVar(value=self.engine.enabled)
        ctk.CTkSwitch(
            top, text=t("enabled"), variable=self.enable_var, command=self._toggle_enabled
        ).pack(side="right")
        self.meter = ctk.CTkProgressBar(card, height=8)
        self.meter.set(0)
        self.meter.pack(fill="x", padx=14, pady=(0, 10))

        ctk.CTkLabel(self, text=t("voice_app"), font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", **pad
        )
        self.voice_box = ctk.CTkComboBox(
            self, values=KNOWN_CALL_APPS, command=self._set_voice_app
        )
        self.voice_box.set(self.cfg["voice_app"])
        self.voice_box.pack(fill="x", pady=(2, 10), **pad)
        self.voice_box.bind("<Return>", lambda e: self._set_voice_app(self.voice_box.get()))

        ctk.CTkLabel(self, text=t("music_apps"), font=ctk.CTkFont(weight="bold")).pack(
            anchor="w", **pad
        )
        ctk.CTkLabel(
            self, text=t("music_hint"), wraplength=410, justify="left",
            text_color=("gray35", "gray65"), font=ctk.CTkFont(size=12),
        ).pack(anchor="w", **pad)
        holder = ctk.CTkFrame(self, height=90, fg_color="transparent")
        holder.pack(fill="x", pady=(4, 10), **pad)
        holder.pack_propagate(False)  # keep the list a fixed height
        self.music_frame = ctk.CTkScrollableFrame(holder)
        self.music_frame.pack(fill="both", expand=True)
        self.music_vars = {}

        self.duck_music = self._slider(
            t("duck_music"), 0, 100, self.cfg["duck_music"] * 100, "duck_music", pct=True
        )
        self.duck_other = self._slider(
            t("duck_other"), 0, 100, self.cfg["duck_other"] * 100, "duck_other", pct=True
        )
        self.sens = self._slider(
            t("sensitivity"), 1, 10, self.cfg["sensitivity"], "sensitivity", pct=False
        )

        self.auto_var = ctk.BooleanVar(value=autostart.is_enabled())
        ctk.CTkCheckBox(
            self, text=t("autostart"), variable=self.auto_var, command=self._toggle_autostart
        ).pack(anchor="w", pady=(8, 4), **pad)
        self.min_var = ctk.BooleanVar(value=self.cfg["start_minimized"])
        ctk.CTkCheckBox(
            self, text=t("minimized"), variable=self.min_var, command=self._toggle_minimized
        ).pack(anchor="w", pady=(0, 10), **pad)

    def _slider(self, label, lo, hi, value, key, pct):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(2, 4))
        head = ctk.CTkFrame(row, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text=label).pack(side="left")
        val = ctk.CTkLabel(head, text="", font=ctk.CTkFont(weight="bold"))
        val.pack(side="right")

        def show(v):
            val.configure(text=f"{int(round(v))}%" if pct else f"{v:.1f}")

        def changed(v):
            show(v)
            self.cfg[key] = v / 100 if pct else float(v)
            cfgmod.save(self.cfg)

        s = ctk.CTkSlider(row, from_=lo, to=hi, command=changed)
        s.set(value)
        s.pack(fill="x", pady=(2, 0))
        show(value)
        return s

    # ---------- actions ----------
    def _toggle_enabled(self):
        self.engine.enabled = self.enable_var.get()
        self.cfg["enabled"] = self.engine.enabled
        cfgmod.save(self.cfg)

    def _set_voice_app(self, value):
        name = value.strip().lower()
        if not name:
            return
        if not name.endswith(".exe"):
            name += ".exe"
        self.cfg["voice_app"] = name
        self.voice_box.set(name)
        cfgmod.save(self.cfg)

    def _toggle_music(self, name):
        apps = [a.lower() for a in self.cfg["music_apps"]]
        if self.music_vars[name].get():
            if name not in apps:
                apps.append(name)
        else:
            apps = [a for a in apps if a != name]
        self.cfg["music_apps"] = apps
        cfgmod.save(self.cfg)

    def _toggle_autostart(self):
        try:
            autostart.set_enabled(self.auto_var.get())
        except OSError:
            self.auto_var.set(autostart.is_enabled())
        self.cfg["autostart"] = self.auto_var.get()
        cfgmod.save(self.cfg)

    def _toggle_minimized(self):
        self.cfg["start_minimized"] = self.min_var.get()
        cfgmod.save(self.cfg)

    def _refresh_apps(self):
        ignore = {p.lower() for p in self.cfg["ignore"]} | {"?", self.cfg["voice_app"].lower()}
        names = {n for n, _ in self.engine.apps} | {a.lower() for a in self.cfg["music_apps"]}
        names = sorted(n for n in names if n not in ignore)
        key = (tuple(names), tuple(sorted(a.lower() for a in self.cfg["music_apps"])))
        if key == self._app_key:
            return
        self._app_key = key
        for w in self.music_frame.winfo_children():
            w.destroy()
        self.music_vars = {}
        selected = {a.lower() for a in self.cfg["music_apps"]}
        playing = {n for n, p in self.engine.apps if p > 0.001}
        if not names:
            ctk.CTkLabel(self.music_frame, text=t("no_apps")).pack(anchor="w")
        for n in names:
            var = ctk.BooleanVar(value=n in selected)
            self.music_vars[n] = var
            label = n + ("  ♪" if n in playing else "")
            ctk.CTkCheckBox(
                self.music_frame, text=label, variable=var,
                command=lambda n=n: self._toggle_music(n),
            ).pack(anchor="w", pady=2)
        # Keep the voice dropdown suggestions up to date.
        self.voice_box.configure(
            values=sorted(set(KNOWN_CALL_APPS) | {n for n, _ in self.engine.apps if n != "?"})
        )

    # ---------- tray ----------
    def _start_tray(self, icon):
        menu = pystray.Menu(
            pystray.MenuItem(t("tray_open"), lambda: self.q.put(self.show), default=True),
            pystray.MenuItem(
                t("tray_enabled"),
                lambda: self.q.put(self._tray_toggle),
                checked=lambda item: self.engine.enabled,
            ),
            pystray.MenuItem(t("tray_quit"), lambda: self.q.put(self.quit_app)),
        )
        self.tray = pystray.Icon("audio-balancer", icon, t("title"), menu)
        self.tray.run_detached()

    def _tray_toggle(self):
        self.enable_var.set(not self.engine.enabled)
        self._toggle_enabled()

    def show(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def hide(self):
        self.withdraw()

    def quit_app(self):
        try:
            self.tray.stop()
        except Exception:
            pass
        self.engine.stop()
        self.destroy()

    # ---------- live updates ----------
    def _tick(self):
        while True:
            try:
                self.q.get_nowait()()
            except queue.Empty:
                break
        e = self.engine
        if not e.enabled:
            text, color, lvl = t("status_off"), OFF, 0.0
        elif e.talking:
            text, color, lvl = t("status_talking"), TALK, min(1.0, e.level * 3)
        else:
            text, color, lvl = t("status_idle"), ACCENT, min(1.0, e.level * 3)
        self.status.configure(text=text)
        self.dot.configure(text_color=color)
        self.meter.configure(progress_color=color)
        self.meter.set(lvl)
        if self.winfo_viewable():
            self._refresh_apps()
        self.after(100, self._tick)
