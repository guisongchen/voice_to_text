# Voice-to-Text Input Tool

System-wide voice input for Linux. Press a shortcut, speak, press again — transcribed text appears at your cursor.

## Features

- **System-wide** — works in any application (browser, editor, terminal)
- **Lightweight daemon** — no ML imports; heavy ASR work lives in [ASRCore](../asr_core)
- **Shared ASRCore** — model lifecycle managed by the central ASR service
- **Web dashboard** — provided by ASRCore at http://localhost:8125
- **Fully offline** — ASRCore loads models from local storage, no network needed
- **Bluetooth support** — compatible with UGREEN LP998 touch ring
- **Safe IPC** — Unix domain socket communication
- **Speaker-aware recording** — automatically mutes speakers while recording to prevent audio feedback

## Requirements

- Python 3.10+
- Ubuntu/Linux with X11
- xdotool (`sudo apt install xdotool`)
- PortAudio (`sudo apt install portaudio19-dev`)
- ALSA utils (`sudo apt install alsa-utils`) — beeps are played with `aplay`
- PulseAudio / PipeWire / ALSA audio control (`pactl`, `wpctl`, or `amixer`; usually pre-installed)
- [ASRCore](../asr_core) installed as a local dependency

> GPU/CUDA are only required by ASRCore; this daemon itself is CPU-only.

## Installation

```bash
git clone <repo-url>
cd voice_to_text

# Install dependencies
uv sync
uv pip install -e .
```

ASRCore owns the model files. See the [ASRCore README](../asr_core/README.md) for model setup.

## Quick Start

### Start services

```bash
# Enable the systemd user services
systemctl --user enable --now asr-core
systemctl --user enable --now voice-to-text
systemctl --user enable --now lp998-listener
```

Or use the convenience script:

```bash
./restart-services.sh
```

### Web dashboard

ASRCore hosts the management UI at http://localhost:8125:

- Monitor ASRCore model status
- Load/unload models
- Start/stop/restart services
- View live logs

### Local vs Cloud ASR backends

The daemon supports two transcription backends, switched by `VTT_ASR_MODE`:

| Mode | `VTT_ASR_MODE` | Transcription path | Requirements |
|---|---|---|---|
| Local (default) | `asrcore` | This daemon → ASRCore (Unix socket) → local Qwen3-ASR on GPU | NVIDIA GPU, model files, `asr-core` service |
| Cloud | `cloud` | This daemon → DashScope `qwen3-asr-flash` (billed per token) | `DASHSCOPE_API_KEY`, network. No GPU, no model files, no `asr-core` service |

Recording, beeps, OSD, and text insertion are identical in both modes; only
the transcription backend differs. Recordings are always archived locally
to `~/voice_recordings/`.

**Privacy note:** in cloud mode, audio leaves the machine. Use local mode
for sensitive content.

#### Switching (systemd deployment)

Use the toggle script — it rewrites the systemd user override and restarts
the service:

```bash
scripts/switch-asr-mode.sh cloud   # switch to cloud (DashScope)
scripts/switch-asr-mode.sh local   # switch to local (ASRCore + GPU model)
scripts/switch-asr-mode.sh status  # show current mode
```

The script manages `~/.config/systemd/user/voice-to-text.service.d/cloud-asr.conf`.
The API key is only read from `~/.bashrc` or preserved in that override —
it is never written to any repository file. (Do **not** put the key in
`services/voice-to-text.service` itself; that file is tracked by git.)

Manual equivalent:

```bash
systemctl --user edit voice-to-text   # add Environment=VTT_ASR_MODE=cloud (or asrcore)
systemctl --user restart voice-to-text
```

#### Manual (non-systemd) runs

```bash
export VTT_ASR_MODE=cloud        # default: asrcore
export DASHSCOPE_API_KEY=sk-...  # required in cloud mode
.venv/bin/python3 -m voice_to_text
```

#### Deploying on a GPU-less machine

Install both repos as usual, then set `VTT_ASR_MODE=cloud` and
`DASHSCOPE_API_KEY` (env or systemd override). You can skip the
`asr-core` systemd service entirely — the daemon talks to DashScope
directly.

#### ASRCore's own backend switch

Independently, ASRCore can itself proxy to DashScope (`ASR_BACKEND=cloud`
or `[cloud] backend = "cloud"` in `asr_core.toml` — see the ASRCore README).
That keeps the Unix-socket API for other ASRCore clients on a GPU-less
machine, at the cost of still running the ASRCore process. For voice input
alone, `VTT_ASR_MODE=cloud` is the lighter option.

### Keyboard Shortcut (GNOME)

```bash
# Set up the shortcut
dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/name "'voice_to_text'"
dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/command "'/home/$USER/projects/voice_to_text/scripts/voice-to-text-t'"
dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/binding "'<Shift><Alt>r'"
dconf write /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings "['/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/']"
```

**Usage:**
- Press `Alt+Shift+R` to start recording (hear double beep)
- Speak
- Press `Alt+Shift+R` again to stop, transcribe, and insert text (hear single beep)

### Speaker mute behavior

While recording, the daemon automatically mutes all audio outputs (`pactl`, `wpctl`, or `amixer`) to prevent music, notifications, or other sounds from leaking into the microphone. The previous mute state is restored when recording stops. If no audio control tool is available, recording still works normally.

This behavior is controlled by `MUTE_SPEAKERS_DURING_RECORDING` in `src/voice_to_text/config.py` (default: `True`).

### Visual OSD (GNOME Shell extension)

In addition to the audio beeps, the daemon emits a session D-Bus signal
(`dev.voice_to_text.Recorder.StateChanged`, payload `started`/`stopped`) on every
recording toggle. The bundled GNOME Shell extension `voice-to-text-osd@ccc`
(source in `gnome-extension/`) listens for it and shows a large centered OSD
icon (red mic = start, green stop = end), which also works over fullscreen
windows. GNOME's built-in microphone privacy indicator covers the persistent
"currently recording" state in the top bar.

Install (once):

```bash
mkdir -p ~/.local/share/gnome-shell/extensions
ln -sfn "$PWD/gnome-extension/voice-to-text-osd@ccc" \
        ~/.local/share/gnome-shell/extensions/voice-to-text-osd@ccc
gnome-extensions enable voice-to-text-osd@ccc
# Wayland: log out and back in once so GNOME Shell discovers the extension
```

The extension is optional: with no listener on the bus the signal emission is
a harmless no-op.

### Bluetooth / LP998 Touch Ring

The LP998 listener is managed by systemd:

```bash
systemctl --user enable --now lp998-listener
```

## Project Structure

```
voice_to_text/
├── src/voice_to_text/       # Python package
│   ├── cli.py               # CLI entry point
│   ├── config.py            # Constants
│   ├── recorder.py          # AudioRecorder (no ML imports)
│   ├── audio_control.py     # Speaker mute/restore during recording
│   ├── inserter.py          # xdotool text insertion
│   ├── cloud_asr.py         # CloudASRClient — direct DashScope mode (VTT_ASR_MODE=cloud)
│   ├── service.py           # Persistent daemon with socket IPC
│   └── toggle.py            # Start/stop toggle logic
├── scripts/                 # Runnable entry points
│   ├── voice-to-text-t      # Toggle (keyboard shortcut target)
│   ├── lp998_listener.py    # LP998 touch zone listener
│   ├── beep_start.wav       # Start-recording beep
│   ├── beep_finish.wav      # Stop-recording beep
│   └── switch-asr-mode.sh   # Toggle local/cloud ASR backend + restart service
├── services/                # systemd unit files
├── doc/                     # Documentation
│   └── voice_to_text_spec.md
├── restart-services.sh      # Convenience wrapper around systemctl
├── pyproject.toml
└── README.md
```

## CLI

```bash
voice-to-text                 # Start daemon (used by systemd)
voice-to-text --keep-audio    # Preserve audio files in /tmp/
voice-to-text -m Qwen3-ASR-1.7B  # Request a specific ASRCore model
```

By default the daemon asks ASRCore to use whichever model is already loaded, falling back to `qwen3-asr-0.6b` if none is loaded.

### GPU memory lifecycle

The ASR model stays loaded in ASRCore (holding VRAM) after transcription. To prevent VRAM leakage, the `voice-to-text.service` unit declares:

```ini
ExecStopPost=-/usr/bin/curl -sf --max-time 10 --unix-socket /tmp/asr_core.sock -X POST http://localhost/unload
```

systemd runs this **on every stop path** — `systemctl --user stop`, idle-timeout self-exit, or a crash/`kill -9` — so the ASR model is always unloaded and VRAM freed when the daemon goes down. The leading `-` ignores failures (e.g. ASRCore not running), and `/unload` is idempotent. The ASRCore daemon itself keeps running; only the model is unloaded, and it lazy-loads again on the next transcription.

## Troubleshooting

### Text not appearing
- Ensure xdotool is installed: `sudo apt install xdotool`
- Click in the target text field before pressing the shortcut
- Check the log: `journalctl --user -fu voice-to-text`

### Recording won't start
```bash
# Clean up stale state
rm -f /tmp/voice_to_text.sock /tmp/asr_core.sock
# Check for stuck processes
pgrep -af voice.to.text
pgrep -af asr_core
```

### Model loading fails
Model files are owned by ASRCore. Ensure the model is available in ASRCore's model path and that ASRCore is running:

```bash
systemctl --user status asr-core
journalctl --user -fu asr-core
```

### No beep sound (recording works, but no audio cue)
Beeps are played via `aplay`, which targets PipeWire's **default sink**. If the
default sink points at the wrong output (e.g. after an OS upgrade flipped a USB
dongle from analog to its digital `iec958` profile), playback "succeeds" silently.

Check and fix:
```bash
pactl get-default-sink          # must be the device your speakers are on
pactl list short sinks
pactl set-default-sink <name>
```

On this machine the intended routing is:
- **Output** → GPU HDMI (monitor speakers); Bluetooth A2DP takes over
  automatically when a headset connects (WirePlumber stock behavior)
- **Input** → UGREEN USB dongle, pinned to input-only so its (unusable)
  output can never be selected:
  `pactl set-card-profile alsa_card.usb-JinAudio_UGREEN_USB_MIC-... input:analog-stereo`

WirePlumber persists these choices across reboots.

### Speakers not muted or not restored after recording
- Ensure one of `pactl`, `wpctl`, or `amixer` is installed and on your `$PATH`
- Check the log: `journalctl --user -fu voice-to-text`
- If the daemon was killed with `kill -9`, mute state may not be restored; use `pactl set-sink-mute @DEFAULT_SINK@ 0` to unmute manually
- Disable the feature by setting `MUTE_SPEAKERS_DURING_RECORDING = False` in `src/voice_to_text/config.py`

### Debug mode
```bash
voice-to-text --keep-audio    # Preserve audio files in /tmp/
```
