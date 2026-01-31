# Voice-to-Text Tool - Quick Reference Guide

## Setup Checklist

### 1. Install System Dependencies
```bash
# Install ydotool for text insertion (Wayland)
sudo apt install ydotool

# Install PortAudio for microphone recording
sudo apt-get install portaudio19-dev
```

### 2. Configure Permissions
```bash
# Add your user to the input group (required for keyboard access)
sudo usermod -aG input $USER

# IMPORTANT: Log out and log back in for this to take effect!
```

### 3. Start ydotool Daemon (if needed)
```bash
# Check if ydotool works
ydotool type "test"

# If it doesn't work, start the daemon
systemctl --user start ydotoold

# Optional: Enable auto-start on boot
systemctl --user enable ydotoold
```

### 4. Install Python Dependencies
```bash
cd /path/to/audio_recorder
uv sync
```

### 5. Verify Setup
```bash
# Check if you can list keyboard devices
uv run voice_to_text.py --list-keyboards

# If you see keyboards listed, you're ready!
# If you get permission errors, make sure you logged out/in after step 2
```

## Usage

### Basic Usage
```bash
# Start the voice-to-text service
uv run voice_to_text.py

# Once running:
# 1. Press and hold Alt+R
# 2. Speak clearly
# 3. Release Alt+R
# 4. Text appears at cursor!
```

### Common Options
```bash
# Use faster model (less accurate, but quicker)
uv run voice_to_text.py --model small

# Use tiny model (fastest)
uv run voice_to_text.py --model tiny

# Use large model (best accuracy, slowest)
uv run voice_to_text.py --model large

# Keep audio files for debugging
uv run voice_to_text.py --keep-audio

# Set minimum recording duration (ignore very short recordings)
uv run voice_to_text.py --min-duration 1.0
```

## Troubleshooting

### Issue: "Permission denied" when accessing keyboard
**Solution:**
```bash
# Make sure you're in the input group
groups | grep input

# If not listed, add yourself
sudo usermod -aG input $USER

# Then log out and log back in (REQUIRED!)
```

### Issue: "ydotool not found"
**Solution:**
```bash
# Install ydotool
sudo apt install ydotool

# Verify it's installed
which ydotool
```

### Issue: Text not inserting even though ydotool is installed
**Solution:**
```bash
# Start the ydotool daemon
systemctl --user start ydotoold

# Check status
systemctl --user status ydotoold

# If it fails, try running manually
ydotoold &

# Test if it works now
ydotool type "test"
```

### Issue: "No keyboard devices found"
**Possible causes:**
1. Not in input group (see first troubleshooting item)
2. Need to log out/in after adding to group
3. Running in a virtual machine or container without proper device access

### Issue: Whisper model fails to load
**Solutions:**
1. Check GPU is available: `nvidia-smi`
2. Check CUDA is installed
3. Try a smaller model: `--model small` or `--model tiny`
4. First run downloads model - ensure internet connection

### Issue: Recording quality is poor
**Solutions:**
1. Speak clearly and at normal pace
2. Reduce background noise
3. Use a better microphone
4. Increase minimum duration: `--min-duration 1.0`

### Issue: Transcription is slow
**Solutions:**
1. Use a smaller/faster model: `--model small` or `--model tiny`
2. Check GPU utilization: `nvidia-smi`
3. Shorter recordings transcribe faster

### Issue: Wrong language detected
**Note:** Whisper auto-detects language. For best results:
- Speak consistently in one language per recording
- Use larger models (medium/large) for better language detection
- Consider using language-specific models if needed

## Performance Tips

### Model Selection Guide

| Model  | Startup Time | Transcription Speed | Accuracy | Best For |
|--------|-------------|---------------------|----------|----------|
| tiny   | ~2 seconds  | Very fast           | Basic    | Quick tests, drafts |
| base   | ~3 seconds  | Fast                | Good     | Casual use |
| small  | ~4 seconds  | Balanced            | Better   | Daily use |
| medium | ~6 seconds  | Slower              | High     | Default, good balance |
| large  | ~10 seconds | Slowest             | Best     | Important transcriptions |

### Workflow Recommendations

**For quick notes and casual use:**
```bash
uv run voice_to_text.py --model small
```

**For important documents (default):**
```bash
uv run voice_to_text.py --model medium
```

**For professional transcription:**
```bash
uv run voice_to_text.py --model large
```

**For debugging issues:**
```bash
uv run voice_to_text.py --keep-audio --min-duration 0.1
```

## Technical Details

### How It Works

1. **Hotkey Detection**: Uses `evdev` to monitor keyboard events for Alt+R
2. **Audio Recording**: PyAudio records from default microphone
3. **Transcription**: OpenAI Whisper (local, offline) transcribes speech
4. **Text Insertion**: `ydotool` simulates keyboard typing to insert text

### System Requirements

- **OS**: Ubuntu 24.04+ (Wayland)
- **GPU**: NVIDIA GPU with CUDA support
- **RAM**: 4-12GB depending on model size
- **Permissions**: User must be in `input` group
- **Network**: Not required during use (only for initial model download)

### Files Created

- Temporary audio files in `/tmp/voice_to_text_*.wav` (auto-deleted unless `--keep-audio`)
- Whisper model cache in `~/.cache/whisper/`

## Acceptance Criteria (from Spec)

- ✅ AC-01: Recording starts within 200ms of Alt+R press
- ✅ AC-02: Recording stops immediately on Alt+R release
- ✅ AC-03: Speech transcribed without network connection (fully offline)
- ✅ AC-04: Transcribed text inserted at current cursor position
- ✅ AC-05: Works across different applications (browser, text editor, terminal)

## Known Limitations

1. **Wayland Only**: Designed for Ubuntu 24.04+ with Wayland
2. **GPU Required**: CUDA-capable NVIDIA GPU needed for transcription
3. **Single Language**: Best results when speaking one language per recording
4. **Input Latency**: Transcription takes a few seconds after recording stops
5. **Permission Requirements**: Needs input group membership and ydotool daemon

## Support

For issues or questions:
1. Check this troubleshooting guide first
2. Verify all setup steps completed
3. Test with `--list-keyboards` to check permissions
4. Try `--keep-audio` to debug recording issues
5. Check system logs: `journalctl --user -u ydotoold`
