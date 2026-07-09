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

Or restart them together:

```bash
systemctl --user restart asr-core voice-to-text lp998-listener
```

### Web dashboard

ASRCore hosts the management UI at http://localhost:8125:

- Monitor ASRCore model status
- Load/unload models
- Start/stop/restart services
- View live logs

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
│   ├── service.py           # Persistent daemon with socket IPC
│   └── toggle.py            # Start/stop toggle logic
├── scripts/                 # Runnable entry points
│   ├── voice-to-text-t      # Toggle (keyboard shortcut target)
│   ├── lp998_listener.py    # LP998 touch zone listener
│   ├── beep_start.wav       # Start-recording beep
│   └── beep_finish.wav      # Stop-recording beep
├── services/                # systemd unit files
├── doc/                     # Documentation
│   └── voice_to_text_spec.md
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

### Speakers not muted or not restored after recording
- Ensure one of `pactl`, `wpctl`, or `amixer` is installed and on your `$PATH`
- Check the log: `journalctl --user -fu voice-to-text`
- If the daemon was killed with `kill -9`, mute state may not be restored; use `pactl set-sink-mute @DEFAULT_SINK@ 0` to unmute manually
- Disable the feature by setting `MUTE_SPEAKERS_DURING_RECORDING = False` in `src/voice_to_text/config.py`

### Debug mode
```bash
voice-to-text --keep-audio    # Preserve audio files in /tmp/
```
