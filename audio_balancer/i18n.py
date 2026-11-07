"""Tiny translation helper: Portuguese or English, based on the Windows UI language."""
import ctypes

STRINGS = {
    "en": {
        "title": "Audio Balancer",
        "subtitle": "Lowers music and games while your friends talk",
        "enabled": "Enabled",
        "status_off": "Paused",
        "status_idle": "Listening... everyone is quiet",
        "status_talking": "Someone is talking: lowering music and games",
        "voice_app": "Call app (voice chat)",
        "music_apps": "Music apps",
        "music_hint": "Tick the apps that play your music. Everything else (games...) is lowered by the second slider.",
        "no_apps": "No app is playing sound right now.",
        "duck_music": "Lower music by",
        "duck_other": "Lower games and other apps by",
        "sensitivity": "Voice sensitivity",
        "autostart": "Start with Windows",
        "minimized": "Start minimized to the tray",
        "tray_open": "Open",
        "tray_enabled": "Enabled",
        "tray_quit": "Quit",
        "running": "Audio Balancer is already running (check the tray icon near the clock).",
        "quit_note": "Closing the window keeps it running in the tray. Use Quit in the tray menu to exit.",
    },
    "pt": {
        "title": "Audio Balancer",
        "subtitle": "Abaixa música e jogo enquanto seus amigos falam",
        "enabled": "Ativado",
        "status_off": "Pausado",
        "status_idle": "Escutando... todo mundo quieto",
        "status_talking": "Alguém está falando: abaixando música e jogo",
        "voice_app": "App da call (chat de voz)",
        "music_apps": "Apps de música",
        "music_hint": "Marque os apps que tocam sua música. Todo o resto (jogos...) abaixa conforme o segundo controle.",
        "no_apps": "Nenhum app está tocando som agora.",
        "duck_music": "Abaixar música em",
        "duck_other": "Abaixar jogos e outros apps em",
        "sensitivity": "Sensibilidade da voz",
        "autostart": "Iniciar com o Windows",
        "minimized": "Iniciar minimizado na bandeja",
        "tray_open": "Abrir",
        "tray_enabled": "Ativado",
        "tray_quit": "Sair",
        "running": "O Audio Balancer já está rodando (veja o ícone na bandeja, perto do relógio).",
        "quit_note": "Fechar a janela mantém o programa na bandeja. Use Sair no menu da bandeja para encerrar.",
    },
}


def _lang() -> str:
    try:
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
        return "pt" if lang_id == 0x16 else "en"
    except Exception:
        return "en"


LANG = _lang()


def t(key: str) -> str:
    return STRINGS[LANG].get(key) or STRINGS["en"][key]
