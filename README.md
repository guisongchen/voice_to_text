# Audio Recorder

A simple Python CLI tool to record audio from your microphone and save it as a WAV file.

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

2. Install Python dependencies with uv:
   ```bash
   uv sync
   ```

## Usage

### Basic recording (10 seconds, default settings):
```bash
uv run audio_recorder.py
```

### Custom duration:
```bash
uv run audio_recorder.py -d 30  # Record for 30 seconds
```

### Specify output filename:
```bash
uv run audio_recorder.py -o my_recording.wav
```

### Mono recording:
```bash
uv run audio_recorder.py -c 1  # 1 channel (mono)
```

### Custom sample rate:
```bash
uv run audio_recorder.py -r 48000  # 48kHz sample rate
```

### List available audio devices:
```bash
uv run audio_recorder.py --list-devices
```

### Combined options:
```bash
uv run audio_recorder.py -d 60 -o interview.wav -r 44100 -c 2
```

## Options

- `-d, --duration`: Recording duration in seconds (default: 10)
- `-o, --output`: Output filename (default: recording_TIMESTAMP.wav)
- `-r, --rate`: Sample rate in Hz (default: 44100)
- `-c, --channels`: Number of channels - 1=mono, 2=stereo (default: 2)
- `--list-devices`: List available audio input devices

## Features

- Records audio from default microphone
- Saves as WAV file
- Progress indicator during recording
- Automatic timestamped filenames
- Configurable sample rate and channels
- Keyboard interrupt support (Ctrl+C)
