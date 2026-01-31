# Copilot Instructions for Audio Recorder

## Project Overview

A Python CLI application with two main scripts:
- `audio_recorder.py`: Records audio from microphone and saves as WAV files
- `transcribe.py`: Transcribes audio files to text using OpenAI's Whisper model

Both scripts are standalone executables with their own CLI interfaces.

## Architecture

**Two-script structure:**
- `audio_recorder.py` (~135 lines): AudioRecorder class, PyAudio operations, WAV file writing
- `transcribe.py` (~220 lines): AudioTranscriber class, Whisper model loading, batch processing
- Both use class-based architecture with main() CLI entry points
- Scripts are independent - can use separately or together

**Key components:**
- PyAudio for audio stream management (recording)
- Whisper for speech-to-text transcription
- Standard library `wave` module for WAV file I/O
- No external configuration files or state persistence

**Data flow:**
1. Record: microphone → PyAudio → WAV file
2. Transcribe: WAV file → Whisper model → text file

## Package Management

This project uses **uv** (not pip/poetry/pipenv) for all Python dependency management.

**Setup:**
```bash
uv sync              # Install dependencies
```

**Running the application:**
```bash
uv run audio_recorder.py [options]   # Record audio
uv run transcribe.py [options]       # Transcribe audio
```

**Adding dependencies:**
```bash
uv add <package>     # Never use pip install
```

## System Dependencies

**PyAudio** requires the PortAudio system library. On new development machines:

```bash
# Ubuntu/Debian
sudo apt-get install portaudio19-dev

# macOS
brew install portaudio

# Fedora
sudo dnf install portaudio-devel
```

**Whisper** requires NVIDIA GPU with CUDA:
- The transcription script uses GPU acceleration (`device="cuda"`)
- Requires NVIDIA drivers and CUDA toolkit installed
- Verify with: `nvidia-smi`
- PyTorch with CUDA support is installed via openai-whisper dependency

**Optional - ffmpeg** for non-WAV audio formats:

```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg
```

## Key Conventions

### Output File Naming
- Audio files: `recording_YYYYMMDD_HHMMSS.wav`
- Transcriptions: `recording_YYYYMMDD_HHMMSS.txt` (matches audio filename)
- Timestamp format: `datetime.now().strftime("%Y%m%d_%H%M%S")`
- Both WAV and TXT files are gitignored (see `.gitignore`)

### Audio Configuration Defaults
- Sample rate: 44100 Hz (CD quality)
- Channels: 2 (stereo)
- Format: 16-bit PCM (`pyaudio.paInt16`)
- Chunk size: 1024 frames

These are configurable via CLI flags but should remain consistent defaults.

### Whisper Model Selection
- Default: `small` (good balance of speed/accuracy)
- GPU acceleration: All models use CUDA for faster processing
- Model files download automatically on first use (~100MB-3GB)
- Models cached in `~/.cache/whisper/`
- Larger models = better accuracy but slower (though GPU helps significantly)

**Model recommendations:**
- Development/testing: `tiny` or `base` (fast iteration)
- Production: `small` or `medium` (good quality)
- Best quality needed: `large` (slow even on GPU, high VRAM usage ~10GB)

**GPU Usage:**
- Hard-coded to use CUDA (`device="cuda"`)
- Displays GPU name on model load
- ~5-10x faster than CPU transcription
- VRAM usage varies by model size

### Resource Cleanup
The `AudioRecorder` class uses `pyaudio.PyAudio()` which must be terminated. Always use the try-finally pattern in `main()` to ensure `recorder.close()` is called.

## Testing the Application

There are no automated tests. To verify functionality:

**Test recording:**
```bash
# List available input devices
uv run audio_recorder.py --list-devices

# Quick 3-second test recording
uv run audio_recorder.py -d 3

# Verify the WAV file was created
ls -lh recording_*.wav
```

**Test transcription:**
```bash
# Transcribe a test recording with tiny model (fast)
uv run transcribe.py -m tiny recording_20260131_110558.wav

# Check the transcription
cat recording_20260131_110558.txt
```

**Test batch transcription:**
```bash
# Transcribe all WAV files
uv run transcribe.py --all

# Verify txt files were created
ls -lh *.txt
```

## Common Development Tasks

**Adding CLI arguments to recorder:**
- Add to argparse in `audio_recorder.py` main() function
- Pass through to `AudioRecorder.__init__()` or `recorder.record()`

**Adding CLI arguments to transcriber:**
- Add to argparse in `transcribe.py` main() function
- Pass through to `AudioTranscriber.__init__()` or `transcriber.transcribe_file()`

**Changing audio format:**
- Modify class-level defaults in `AudioRecorder.__init__()`
- Update argparse help text to reflect new defaults

**Changing transcription output format:**
- Modify `AudioTranscriber.transcribe_file()` method
- Currently saves `result["text"]` - Whisper also provides timestamps in result

**Debugging audio issues:**
- Use `--list-devices` to verify microphone detection
- Check system audio permissions (especially on macOS)
- PyAudio errors typically indicate missing PortAudio or permission issues

**Debugging transcription issues:**
- Test with `tiny` model first (faster debugging)
- Whisper downloads models on first run - check internet connection
- Check disk space for model cache (~/.cache/whisper/)
- For non-WAV formats, verify ffmpeg is installed
