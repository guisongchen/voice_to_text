# Audio Recorder

A Python CLI tool to record audio from your microphone and transcribe it to text using OpenAI's Whisper.

## Features

- 🎤 Record audio from microphone and save as WAV files
- 📝 Transcribe audio files to text using Whisper AI
- ⚙️ Configurable sample rate, channels, and recording duration
- 🎯 Multiple Whisper model sizes for speed/accuracy tradeoff
- 📦 Batch transcription support

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

### Recording Audio

#### Basic recording (10 seconds, default settings):
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

### Transcribing Audio

#### Transcribe a single file:
```bash
uv run transcribe.py recording.wav
```

#### Transcribe all WAV files in current directory:
```bash
uv run transcribe.py --all
```

#### Use different Whisper model sizes:
```bash
# Faster, less accurate
uv run transcribe.py -m tiny recording.wav

# Better accuracy (default)
uv run transcribe.py -m small recording.wav

# Best accuracy, slower
uv run transcribe.py -m medium recording.wav
```

#### Custom output filename:
```bash
uv run transcribe.py -o transcript.txt recording.wav
```

#### Force overwrite existing transcriptions:
```bash
uv run transcribe.py --force --all
```

## Options

### Audio Recorder

- `-d, --duration`: Recording duration in seconds (default: 10)
- `-o, --output`: Output filename (default: recording_TIMESTAMP.wav)
- `-r, --rate`: Sample rate in Hz (default: 44100)
- `-c, --channels`: Number of channels - 1=mono, 2=stereo (default: 2)
- `--list-devices`: List available audio input devices

### Transcriber

- `audio_file`: Audio file to transcribe (positional argument)
- `-a, --all`: Transcribe all WAV files in directory
- `-d, --directory`: Specify directory for batch transcription
- `-p, --pattern`: File pattern to match (default: *.wav)
- `-m, --model`: Whisper model size - tiny, base, small, medium, large (default: small)
- `-o, --output`: Custom output file path (single file only)
- `--force`: Overwrite existing transcription files

### Whisper Model Sizes

| Model  | Speed    | Accuracy | RAM Usage |
|--------|----------|----------|-----------|
| tiny   | Fastest  | Low      | ~1 GB     |
| base   | Fast     | Good     | ~1 GB     |
| small  | Balanced | Better   | ~2 GB     |
| medium | Slow     | High     | ~5 GB     |
| large  | Slowest  | Best     | ~10 GB    |

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

## Example Workflow

```bash
# 1. Record a 30-second audio clip
uv run audio_recorder.py -d 30 -o meeting.wav

# 2. Transcribe it to text
uv run transcribe.py meeting.wav

# 3. View the transcription
cat meeting.txt
```
