# Voice-to-Text Input Tool

A system-wide voice input tool for Linux that lets you record audio and insert transcribed text anywhere using a keyboard shortcut.

## Features

⌨️ **System-wide voice input** - Press Alt+R to record, press again to transcribe and insert text  
🎤 **One-command workflow** - Simple toggle script for start/stop  
📝 **Whisper AI transcription** - Accurate speech-to-text using OpenAI's Whisper  
🚀 **GPU-accelerated** - Fast transcription with CUDA support  
🔒 **Safe IPC** - Unix domain socket communication (no PID reuse vulnerabilities)  
🌏 **Multi-language support** - Chinese, English, and many more languages  

## Requirements

- Python 3.10+
- Ubuntu/Linux with X11
- NVIDIA GPU with CUDA (recommended for fast transcription)
- xdotool (for text insertion)
- System audio libraries (PortAudio)

## Installation

### 1. Install System Dependencies

```bash
# Install xdotool for text insertion
sudo apt install xdotool

# Install PortAudio for audio recording
sudo apt-get install portaudio19-dev
```

### 2. Verify CUDA Installation

```bash
nvidia-smi  # Should show your GPU
```

### 3. Install Python Package

```bash
# Clone the repository
git clone <your-repo-url>
cd voice_to_text

# Install with uv (recommended)
uv sync  
uv pip install .
```

## Quick Start

### Desktop Shortcut Setup (Recommended)

Set up a keyboard shortcut for hands-free voice input:

**For GNOME Desktop:**

1. Open **Settings** → **Keyboard** → **Keyboard Shortcuts**
2. Click **"+"** to add a custom shortcut
3. Set the following:
   - **Name**: `Voice to Text`
   - **Command**: `/full/path/to/voice_to_text_socket_toggle.py`
   - **Shortcut**: Press `Alt+R`

**Usage:**
- Press `Alt+R` to start recording
- Speak your text
- Press `Alt+R` again to stop, transcribe, and insert text at cursor


## How It Works

1. **Press shortcut** → Recording starts (you'll hear a beep)
2. **Speak your text** → Audio is being captured
3. **Press shortcut again** → Recording stops (you'll hear another beep)
4. **Transcription happens** → Whisper AI converts speech to text
5. **Text is inserted** → Transcribed text appears at your cursor position

## Configuration

### Model Sizes

Choose different Whisper models for speed vs. accuracy tradeoff:

```bash
# Faster but less accurate
voice-to-text --model small

# Default (balanced)
voice-to-text --model medium

# More accurate but slower
voice-to-text --model large
```

Model sizes: `tiny`, `base`, `small`, `medium`, `large`

### Keep Audio Files for Debugging

```bash
voice-to-text --keep-audio
```

Audio files are saved in `/tmp/` with timestamps.

## Technical Details

### Architecture

- **IPC Method**: Unix domain socket (`/tmp/voice_to_text.sock`)
- **Audio Format**: 44.1kHz, stereo, WAV
- **Transcription**: OpenAI Whisper (GPU-accelerated)
- **Text Insertion**: xdotool (X11)

### Safety Features

The tool uses Unix domain sockets for inter-process communication, which provides:

✅ No PID reuse vulnerabilities  
✅ Reliable message delivery with ACK  
✅ Atomic socket operations  
✅ Automatic cleanup of stale sockets  
✅ Better error handling  

See [SOCKET_MODE_MIGRATION.md](SOCKET_MODE_MIGRATION.md) for details.

## Project Structure

```
voice_to_text/
├── cli/
│   └── voice_to_text_cli.py      # CLI entry point
├── core/
│   ├── audio_feedback.py         # Audio beep feedback
│   ├── audio_service.py          # Recording functionality
│   ├── config.py                 # Configuration
│   └── text_inserter.py          # Text insertion via xdotool
├── modes/
│   ├── base_mode.py              # Base mode class
│   └── socket_mode.py            # Socket-based IPC mode
├── services/
│   ├── dependency_container.py   # Dependency injection
│   └── voice_to_text_service.py  # Main service orchestrator
└── transcribe.py                 # Whisper transcription
```

## Troubleshooting

### "xdotool not found"
```bash
sudo apt install xdotool
```

### "No CUDA device found"
The tool will fall back to CPU, but it will be slower. Install NVIDIA drivers and CUDA toolkit.

### "Permission denied" for socket
```bash
# Clean up stale socket file
rm /tmp/voice_to_text.sock
```

### Recording doesn't start
Check the log file:
```bash
tail -f /tmp/voice_to_text.log
```

### Text not inserting
- Make sure xdotool is installed
- Ensure the target window has focus
- Try clicking in the text field before using the shortcut

## Development

### Run Tests
```bash
pytest
```

### Install in Development Mode
```bash
pip install -e .
```

## FAQ

**Q: Does this work on Wayland?**  
A: Currently optimized for X11. Wayland support may require additional setup.

**Q: Can I use this without a GPU?**  
A: Yes, but transcription will be slower. The tool automatically falls back to CPU.

**Q: What languages are supported?**  
A: Whisper supports many languages including English, Chinese, Spanish, French, German, Japanese, Korean, and more.

**Q: Can I use a different keyboard shortcut?**  
A: Yes! Just set a different key combination when creating the desktop shortcut.

**Q: Where are the audio files stored?**  
A: By default in `/tmp/whisper_recording_*.wav` and deleted after transcription. Use `--keep-audio` to preserve them.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

[Your License Here]

## Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) for the transcription model
- xdotool for text insertion functionality
