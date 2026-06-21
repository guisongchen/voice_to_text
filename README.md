# Voice-to-Text Input Tool

System-wide voice input for Linux. Press a shortcut, speak, press again — transcribed text appears at your cursor.

## Features

- **System-wide** — works in any application (browser, editor, terminal)
- **Qwen3-ASR** — accurate multilingual transcription with GPU acceleration
- **Shared ASRCore** — model lifecycle managed by a central ASR service
- **Web dashboard** — manage services, load/unload models, view logs
- **Fully offline** — model loaded from local storage, no network needed
- **Bluetooth support** — compatible with UGREEN LP998 touch ring
- **Safe IPC** — Unix domain socket communication

## Requirements

- Python 3.10+
- Ubuntu/Linux with X11
- NVIDIA GPU with CUDA
- xdotool (`sudo apt install xdotool`)
- PortAudio (`sudo apt install portaudio19-dev`)
- [ASRCore](../asr_core) installed as a local dependency

## Installation

```bash
git clone <repo-url>
cd voice_to_text

# Install dependencies
uv sync
uv pip install -e .

# Copy the model to local storage (or symlink from ASRCore)
cp -rL ~/.cache/huggingface/hub/models--Qwen--Qwen3-ASR-0.6B/snapshots/*/ models/qwen3-asr-0.6b/
```

## Quick Start

### Start services

```bash
# Enable all related systemd user services
systemctl --user enable --now asr-core
systemctl --user enable --now voice-to-text
systemctl --user enable --now lp998-listener
systemctl --user enable --now voice-to-text-dashboard
```

Or use the convenience script:

```bash
./restart-services.sh
```

### Web dashboard

Open http://localhost:8080 to:
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
│   ├── inserter.py          # xdotool text insertion
│   ├── service.py           # Main daemon with socket IPC
│   ├── toggle.py            # Start/stop toggle logic
│   └── dashboard/           # Web management console
│       ├── app.py           # FastAPI backend
│       ├── systemd.py       # systemd helpers
│       ├── static/
│       └── templates/
├── scripts/                 # Runnable entry points
│   ├── voice-to-text-t      # Toggle (keyboard shortcut target)
│   └── lp998_listener.py    # LP998 touch zone listener
├── services/                # systemd unit files
├── models/                  # Local model files (gitignored)
├── pyproject.toml
└── README.md
```

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
Ensure the model is available in `models/qwen3-asr-0.6b/` or in the shared ASRCore `models/` directory. ASRCore loads models from its own project tree.

### Debug mode
```bash
voice-to-text --keep-audio    # Preserve audio files in /tmp/
```
