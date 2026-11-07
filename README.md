# audio-balancer

A small Windows background tool that automatically balances game and music volume against voice chat.

When friends start talking on Discord, the music and the game get quieter so the conversation comes through. When the call goes quiet, everything fades back to your normal volume.

## How it works

- **Per-app volume control:** uses the Windows Core Audio API (WASAPI) through [pycaw](https://github.com/AndreMiras/pycaw) to change the volume of individual apps, exactly like the Windows Volume Mixer.
- **Multi-device:** scans every active output device (monitor, speakers, TV, Bluetooth), so the voice app and the music can play on different outputs.
- **Speech detection:** reads the output peak meter of the voice app (Discord by default). Since Discord only plays other people's voices to your headphones, a level above the threshold means someone is talking.
- **Ducking with smooth fades:** fast fade down when speech starts, slow fade up after a hold time of silence, so the volume does not flutter between sentences.
- **Short sounds are ignored:** a minimum speech duration filters out join/leave and notification sounds.
- **Respects manual changes:** if you change an app's volume yourself while the tool is running, it learns the new base volume.
- **Restores on exit:** volumes go back to normal when you stop the program.

## Setup

Requires Windows and Python 3.10+.

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Usage

```bash
# run the balancer
.venv\Scripts\python balancer.py

# list apps currently producing audio, with their live level
.venv\Scripts\python balancer.py --list
```

## Configuration

Everything lives in `config.json`:

| Key | Meaning |
| --- | --- |
| `voice.processes` | Apps that carry the call audio (e.g. `discord.exe`). Never ducked. |
| `voice.threshold` | Peak level (0 to 1) above which someone counts as speaking. |
| `voice.min_speech_ms` | Minimum sound duration to count as speech. |
| `voice.hold_ms` | Silence required before volumes come back. |
| `rules` | Groups of apps with their own duck amount (`0.75` = reduce by 75%). |
| `default_duck` | Duck amount for any app audio session not matched by a rule (games, etc.). `null` leaves unmatched apps alone. |
| `ignore` | Process names to never touch. |
| `fade_down_ms` / `fade_up_ms` | Fade durations. |
| `poll_ms` | How often the audio level is checked. |

Adding a new app is just adding its process name to a rule, for example another browser or a different music player. Use `--list` to find the exact process name.

## Limitations

- Browsers expose one audio session for all tabs, so a YouTube tab is ducked together with every other tab playing sound.
- If the voice app's output level is very low, lower `voice.threshold`.
