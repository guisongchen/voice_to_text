# Audio Recorder with Whisper Transcription

A Python CLI tool to record audio from your microphone and transcribe it to text using OpenAI's Whisper.

**🚀 Main Tool: `record.py`** - Records audio and transcribes in one command (see [Quick Start](#-quick-start-with-recordpy-recommended))

**⌨️ NEW: `voice_to_text.py`** - System-wide voice input with Alt+R hotkey! (see [Voice-to-Text Input Tool](#%EF%B8%8F-voice-to-text-input-tool))

## Features

- ⌨️ **System-wide voice input**: Press Alt+R to record and insert text anywhere
- 🎤 **One-command workflow**: Record and transcribe with `record.py`
- 📝 Transcribe audio files to text using Whisper AI
- 🚀 GPU-accelerated transcription (CUDA required)
- 🌏 Supports multiple languages (Chinese, English, etc.)
- ⚙️ Configurable sample rate, channels, and recording duration
- 🎯 Multiple Whisper model sizes for speed/accuracy tradeoff
- 💾 Optional audio file deletion to save space
- 📦 Batch transcription support

## Requirements

- Python 3.10+
- NVIDIA GPU with CUDA support (for transcription)
- System audio libraries (PortAudio)
- **For voice-to-text**: Ubuntu 24.04+ with Wayland, ydotool, input group permissions

## Installation

1. Install system dependencies (for PyAudio):
   ```bash
   # Ubuntu/Debian
   sudo apt-get install portaudio19-dev
   
   # macOS
   brew install portaudio
   
   # Fedora
   sudo dnf install portaudio-devel
   ```

2. **For voice-to-text tool**, install xdotool (text insertion):
   ```bash
   sudo apt install xdotool
   ```

3. **OPTIONAL - For hotkey mode only**, add your user to the input group:
   ```bash
   sudo usermod -aG input $USER
   ```
   **Security Note**: This gives access to all input devices. **Skip this step** if using `--record-once` mode with desktop shortcuts (recommended).
   
   **Important**: If you do add yourself to input group, log out and log back in for changes to take effect!

4. Ensure NVIDIA GPU drivers and CUDA are installed:
   ```bash
   nvidia-smi  # Should show your GPU
   ```

5. Install Python dependencies with uv:
   ```bash
   uv sync
   ```

## Usage

### ⌨️ Voice-to-Text Input Tool

**NEW!** System-wide voice input with hotkey support. Press `Alt+R` to record speech, transcribe, and automatically insert text at your cursor position - works in any application!

**Two Modes Available:**
- **🔒 Secure Mode** (Recommended): `--record-once` with desktop shortcut - no special permissions needed
- **⚡ Hotkey Mode**: Continuous monitoring - requires input group access

#### Quick Start (Secure Mode - Recommended)

**Step 1: Test the tool**
```bash
# Record for 5 seconds, then transcribe and insert
uv run voice_to_text.py --record-once -d 5
```

**Step 2: Set up GNOME keyboard shortcut**
1. Open **Settings → Keyboard → Keyboard Shortcuts**
2. Scroll down and click **"+"** to add custom shortcut
3. **Name**: `Voice to Text`
4. **Command**: 
   ```
   /usr/bin/bash -c "cd /home/YOUR_USERNAME/vibe_projects/audio_recorder && /home/YOUR_USERNAME/.local/bin/uv run voice_to_text.py --record-once -d 5"
   ```
   (Replace `YOUR_USERNAME` with your actual username)
5. Click **Set Shortcut** and press `Alt+R`
6. Done! Now `Alt+R` works system-wide

**How to use:**
1. **Focus any application** (browser, editor, terminal, etc.)
2. **Press Alt+R** - Recording starts (2 audio beeps), tool counts down 5 seconds
3. **Speak clearly** - Your speech is being recorded
4. **Wait** - Transcription happens automatically (1 beep when done)
5. **Text appears** - Inserted at your cursor position!

**Note:** Audio feedback uses programmatic beeps (880Hz/660Hz tones) that work in all scenarios including desktop shortcuts.

#### Alternative: Hotkey Mode (Requires Input Group)

If you prefer continuous monitoring and have added yourself to the input group:

```bash
# Start the voice-to-text service
uv run voice_to_text.py
```

Once running:
1. **Press and hold Alt+R** - Recording starts (2 audio beeps)
2. **Speak clearly** - Your voice is being recorded
3. **Release Alt+R** - Recording stops (1 beep), transcription begins
4. **Text appears** - Inserted at your cursor position

**Security Warning**: This mode requires `input` group membership which grants access to all keyboard/mouse events.

#### Features

- 🌍 **System-wide**: Works in browser, text editor, terminal, any application
- 🔒 **Secure Option**: `--record-once` mode needs no special permissions
- 🔔 **Audio feedback**: Terminal beep when recording starts/finishes (bypasses PipeWire)
- ⌨️ **Direct insertion**: Uses xdotool to type text at cursor
- ⚡ **Fast**: Pre-loaded model, transcription starts immediately
- 🔒 **Private**: Fully offline, no internet required
- 🎯 **Accurate**: Uses OpenAI Whisper medium model by default
- 🌏 **Multilingual**: Auto-detects Chinese, English, and many other languages

#### Voice-to-Text Options

**Secure mode with different durations:**
```bash
# 3 second recording (quick notes)
uv run voice_to_text.py --record-once -d 3

# 10 second recording (longer input)
uv run voice_to_text.py --record-once -d 10

# Manual stop with Ctrl+C (variable length)
uv run voice_to_text.py --record-once
```

**Use a different Whisper model:**
```bash
# Faster transcription (less accurate)
uv run voice_to_text.py --record-once -d 5 --model small

# Best accuracy (slower)
uv run voice_to_text.py --record-once -d 5 --model large
```

**Keep audio files for debugging:**
```bash
uv run voice_to_text.py --record-once -d 5 --keep-audio
```

**For hotkey mode (requires input group):**
```bash
# Continuous monitoring with default settings
uv run voice_to_text.py

# With different model
uv run voice_to_text.py --model small
```

**List available keyboard devices (hotkey mode troubleshooting):**
```bash
uv run voice_to_text.py --list-keyboards
```

**Set minimum recording duration:**
```bash
uv run voice_to_text.py --min-duration 1.0  # Ignore recordings < 1 second
```

#### Troubleshooting

**"Permission denied" error (hotkey mode only):**
```bash
# Option 1: Use secure --record-once mode (RECOMMENDED)
uv run voice_to_text.py --record-once -d 5

# Option 2: Add yourself to input group (less secure)
sudo usermod -aG input $USER
# Then log out and log back in
```

**Desktop shortcut not working:**
- Ensure you used full absolute paths in the command
- Test the command in terminal first
- Check `~/.local/bin/uv` exists, or use `which uv` to find the path
- Make sure xdotool is installed: `sudo apt install xdotool`

**"xdotool not found" error:**
```bash
# Install xdotool
sudo apt install xdotool

# Test it works
xdotool type "test"
```

**Alt+R not detected (hotkey mode only):**
- Switch to `--record-once` mode with desktop shortcut (recommended)
- Check available keyboards with `--list-keyboards`
- Make sure you're in the input group
- Try restarting after adding to input group

**Text not inserting:**
- Verify xdotool works: `xdotool type "test"`
- Make sure the target application has focus and accepts text input
- Some applications may block automated input (security feature)
- Try clicking in the text field before pressing Alt+R

**Transcription quality issues:**
- Speak clearly and at normal pace
- Reduce background noise
- Use a better microphone
- Try a larger model: `--model medium` or `--model large`

**Audio beeps not audible:**
- Tool generates programmatic audio beeps (880Hz start, 660Hz finish)
- Check system volume settings
- Beeps work in all scenarios (terminal, desktop shortcuts)
- If beeps still too quiet, you can watch the console for status messages

**Audio feedback beeps causing noise/buzz:**
- The tool keeps output stream active during recording to prevent PipeWire noise
- If noise persists, may indicate audio driver issue
- Try `--keep-audio` to save recording and inspect with audio player

---

### 🚀 Quick Start with `record.py` (Recommended)

The easiest way to use this tool is with **`record.py`** - an integrated CLI that records and transcribes in one command:

**Basic usage (10 seconds):**
```bash
uv run record.py
```

**Record for 30 seconds:**
```bash
uv run record.py -d 30
```

**Use faster model:**
```bash
uv run record.py -d 15 -m tiny
```

**Delete audio after transcription (save space):**
```bash
uv run record.py --delete-audio
```

**Record only, skip transcription:**
```bash
uv run record.py --no-transcribe -d 60
```

**Transcribe existing file without recording:**
```bash
uv run record.py --transcribe-only existing.wav
```

**List available microphones:**
```bash
uv run record.py --list-devices
```

### 📋 Advanced: Separate Recording and Transcription

If you need more control, you can use the tools separately:

#### Recording Audio Only

Basic recording (10 seconds, default settings):
```bash
uv run audio_recorder.py
```

Custom duration:
```bash
uv run audio_recorder.py -d 30  # Record for 30 seconds
```

Specify output filename:
```bash
uv run audio_recorder.py -o my_recording.wav
```

Mono recording:
```bash
uv run audio_recorder.py -c 1  # 1 channel (mono)
```

Custom sample rate:
```bash
uv run audio_recorder.py -r 48000  # 48kHz sample rate
```

List available audio devices:
```bash
uv run audio_recorder.py --list-devices
```

Combined options:
```bash
uv run audio_recorder.py -d 60 -o interview.wav -r 44100 -c 2
```

#### Transcribing Audio Only

**Note:** Transcription requires an NVIDIA GPU with CUDA. The script will automatically use GPU acceleration for faster processing.

Transcribe a single file:
```bash
uv run transcribe.py recording.wav
```

Transcribe all WAV files in current directory:
```bash
uv run transcribe.py --all
```

Use different Whisper model sizes:
```bash
# Faster, less accurate
uv run transcribe.py -m tiny recording.wav

# Better accuracy (default)
uv run transcribe.py -m small recording.wav

# Best accuracy, slower
uv run transcribe.py -m medium recording.wav
```

Custom output filename:
```bash
uv run transcribe.py -o transcript.txt recording.wav
```

Force overwrite existing transcriptions:
```bash
uv run transcribe.py --force --all
```

## Options

### Integrated CLI (record.py)

**Recording Options:**
- `-d, --duration`: Recording duration in seconds (default: 10)
- `-o, --output`: Output filename (default: recording_TIMESTAMP.wav)
- `-r, --rate`: Sample rate in Hz (default: 44100)
- `-c, --channels`: Number of channels - 1=mono, 2=stereo (default: 2)

**Transcription Options:**
- `-m, --model`: Whisper model size - tiny, base, small, medium, large (default: small)
- `--delete-audio`: Delete audio file after successful transcription
- `--no-transcribe`: Record only, skip transcription

**Special Modes:**
- `--transcribe-only FILE`: Transcribe existing file without recording
- `--list-devices`: List available audio input devices

### Audio Recorder (audio_recorder.py)

- `-d, --duration`: Recording duration in seconds (default: 10)
- `-o, --output`: Output filename (default: recording_TIMESTAMP.wav)
- `-r, --rate`: Sample rate in Hz (default: 44100)
- `-c, --channels`: Number of channels - 1=mono, 2=stereo (default: 2)
- `--list-devices`: List available audio input devices

### Transcriber (transcribe.py)

- `audio_file`: Audio file to transcribe (positional argument)
- `-a, --all`: Transcribe all WAV files in directory
- `-d, --directory`: Specify directory for batch transcription
- `-p, --pattern`: File pattern to match (default: *.wav)
- `-m, --model`: Whisper model size - tiny, base, small, medium, large (default: small)
- `-o, --output`: Custom output file path (single file only)
- `--force`: Overwrite existing transcription files

### Whisper Model Sizes

All models use GPU acceleration (CUDA) for faster transcription.

| Model  | Speed    | Accuracy | VRAM Usage | Best For            |
|--------|----------|----------|------------|---------------------|
| tiny   | Fastest  | Low      | ~1 GB      | Quick tests         |
| base   | Fast     | Good     | ~1 GB      | Basic transcription |
| small  | Balanced | Better   | ~2 GB      | General use (default)|
| medium | Slow     | High     | ~5 GB      | High accuracy needs |
| large  | Slowest  | Best     | ~10 GB     | Professional quality|

## Features

- Records audio from default microphone
- Saves as WAV file
- Transcribes audio to text with Whisper AI
- Progress indicator during recording
- Automatic timestamped filenames
- Configurable sample rate and channels
- Batch transcription support
- Multiple Whisper models for speed/accuracy tradeoff
- Keyboard interrupt support (Ctrl+C)
- Smart skipping of already-transcribed files

## Example Workflows

### Quick voice note with transcription:
```bash
# Record 10 seconds and transcribe (keeps both files)
uv run record.py

# View the transcription
cat recording_*.txt
```

### Interview recording (save space):
```bash
# Record 30 minutes, transcribe, delete audio to save space
uv run record.py -d 1800 --delete-audio -o interview.wav

# Only the text file remains
cat interview.txt
```

### Batch transcription:
```bash
# Record multiple clips separately
uv run audio_recorder.py -d 30 -o clip1.wav
uv run audio_recorder.py -d 30 -o clip2.wav

# Transcribe all at once
uv run transcribe.py --all
```

### Re-transcribe with different model:
```bash
# First transcription with tiny model (fast)
uv run record.py -d 60 -m tiny -o meeting.wav

# Re-transcribe with better model for accuracy
uv run record.py --transcribe-only meeting.wav -m medium
```
