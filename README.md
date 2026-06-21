# Voice-to-Text Input Tool

System-wide voice input for Linux. Press a shortcut, speak, press again — transcribed text appears at your cursor.

## Features

- **System-wide** — works in any application (browser, editor, terminal)
- **Qwen3-ASR** — accurate multilingual transcription with GPU acceleration
- **Fully offline** — model loaded from local storage, no network needed
- **Bluetooth support** — compatible with UGREEN LP998 touch ring
- **Safe IPC** — Unix domain socket communication

## Requirements

- Python 3.10+
- Ubuntu/Linux with X11
- NVIDIA GPU with CUDA
- xdotool (`sudo apt install xdotool`)
- PortAudio (`sudo apt install portaudio19-dev`)

## Installation

```bash
git clone <repo-url>
cd voice_to_text

# Install dependencies
uv sync
uv pip install -e .

# Copy the model to local storage
cp -rL ~/.cache/huggingface/hub/models--Qwen--Qwen3-ASR-0.6B/snapshots/*/ models/qwen3-asr-0.6b/
```

## Quick Start

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

Enable systemd user services:

```bash
systemctl --user enable --now lp998-listener
```

## Project Structure

```
voice_to_text/
├── src/voice_to_text/       # Python package
│   ├── cli.py               # CLI entry point
│   ├── config.py            # Constants
│   ├── audio.py             # AudioRecorder, AudioPreprocessor, BeepPlayer
│   ├── transcriber.py       # Qwen3-ASR model wrapper
│   ├── inserter.py          # xdotool text insertion
│   ├── service.py           # Main service with socket IPC
│   └── toggle.py            # Start/stop toggle logic
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
- Check the log: `tail -f /tmp/voice_to_text.log`

### Recording won't start
```bash
# Clean up stale state
rm -f /tmp/voice_to_text.sock
# Check for stuck processes
pgrep -af voice.to.text
```

### Model loading fails
Ensure the model is copied to `models/qwen3-asr-0.6b/`. If missing, the daemon falls back to loading from HuggingFace cache (requires `HF_HUB_OFFLINE=1` to prevent network hangs).

### Debug mode
```bash
voice-to-text --keep-audio    # Preserve audio files in /tmp/
```
