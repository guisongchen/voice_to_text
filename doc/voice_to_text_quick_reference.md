# Voice-to-Text Tool - Quick Reference Guide

## 🔒 Secure Mode (Recommended)

**No special permissions needed!** Use `--record-once` mode with desktop shortcuts.

### Quick Setup (5 minutes)

1. **Install xdotool**:
   ```bash
   sudo apt install xdotool
   ```

2. **Test the command**:
   ```bash
   cd /home/YOUR_USERNAME/vibe_projects/audio_recorder
   uv run voice-to-text --record-once -d 5
   # Speak after 2 seconds, text will be inserted!
   ```

3. **Create GNOME Keyboard Shortcut**:
   - Open **Settings → Keyboard → Keyboard Shortcuts**
   - Click **"+"** to add custom shortcut
   - **Name**: Voice to Text
   - **Command**: 
     ```
     /usr/bin/bash -c "cd /home/YOUR_USERNAME/vibe_projects/audio_recorder && /home/YOUR_USERNAME/.local/bin/uv run voice-to-text --record-once -d 5"
     ```
   - **Shortcut**: Press `Alt+R`
   - Done!

4. **Use it**: Press `Alt+R` anywhere, speak for 5 seconds, text appears!

---

## Setup Checklist

### For Secure Mode (Recommended)

1. **Install xdotool**:
   ```bash
   sudo apt install xdotool
   ```

2. **Install Python dependencies**:
   ```bash
   cd /path/to/audio_recorder
   uv sync
   ```

3. **Set up desktop shortcut** (see above)

**No special permissions needed!** ✅ More secure, easier to set up.


## Usage

### Secure Mode (Recommended)
```bash
# Single recording (5 seconds)
uv run voice-to-text --record-once -d 5

# After 2 seconds: speak
# Text automatically inserted at cursor!
```


### Common Options
```bash
# Use faster model (less accurate, but quicker)
uv run voice-to-text --model small

# Use tiny model (fastest)
uv run voice-to-text --model tiny

# Use large model (best accuracy, slowest)
uv run voice-to-text --model large

# Keep audio files for debugging
uv run voice-to-text --keep-audio

# Set minimum recording duration (ignore very short recordings)
uv run voice-to-text --min-duration 1.0
```

## Troubleshooting





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
uv run voice-to-text --model small
```

**For important documents (default):**
```bash
uv run voice-to-text --model medium
```

**For professional transcription:**
```bash
uv run voice-to-text --model large
```

**For debugging issues:**
```bash
uv run voice-to-text --keep-audio --min-duration 0.1
```

## Technical Details

### How It Works

1. **Audio Recording**: PyAudio records from default microphone with PipeWire noise prevention
2. **Transcription**: OpenAI Whisper (local, offline) transcribes speech
3. **Text Insertion**: `xdotool` simulates keyboard typing to insert text at cursor position

### System Requirements

- **OS**: Ubuntu 24.04+ (Wayland)
- **GPU**: NVIDIA GPU with CUDA support (optional, works on CPU)
- **RAM**: 4-12GB depending on model size
- **Permissions**: No special permissions needed (uses xdotool for text insertion)
- **Network**: Not required during use (only for initial model download)

### Files Created

- Temporary audio files in `/tmp/voice_to_text_*.wav` (auto-deleted unless `--keep-audio`)
- Whisper model cache in `~/.cache/whisper/`

## Acceptance Criteria (from Spec)

- ✅ AC-01: Recording starts within 200ms of command execution
- ✅ AC-02: Recording stops after specified duration or SIGUSR1 signal
- ✅ AC-03: Speech transcribed without network connection (fully offline)
- ✅ AC-04: Transcribed text inserted at current cursor position
- ✅ AC-05: Works across different applications (browser, text editor, terminal)

## Known Limitations

1. **Wayland Only**: Designed for Ubuntu 24.04+ with Wayland
2. **GPU Required**: CUDA-capable NVIDIA GPU needed for transcription
3. **Single Language**: Best results when speaking one language per recording
4. **Input Latency**: Transcription takes a few seconds after recording stops

## Support

For issues or questions:
1. Check this troubleshooting guide first
2. Verify all setup steps completed
3. Test with `--record-once -d 5` to verify basic functionality
4. Try `--keep-audio` to debug recording issues
5. Check xdotool installation: `xdotool type "test"`
