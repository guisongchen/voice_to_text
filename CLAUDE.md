# CLAUDE.md

This file provides guidance to Claude Code when working in the `voice_to_text` repository.

## Project Overview

`voice_to_text` is a system-wide voice input tool for Linux. Press a shortcut (or the LP998 Bluetooth button), speak, press again, and transcribed text is inserted at the cursor via `xdotool`.

The daemon no longer loads the ASR model itself. It delegates transcription to the shared **ASRCore** service (`/home/ccc/projects/asr_core`) over a Unix socket.

## Architecture

```
voice_to_text/
├── src/voice_to_text/
│   ├── cli.py              # CLI entry point
│   ├── service.py          # Persistent daemon: recording, IPC, ASRCore client
│   ├── recorder.py         # pyaudio-based audio recorder (no ML imports)
│   ├── inserter.py         # xdotool text insertion
│   ├── toggle.py           # Socket client that spawns the daemon on demand
│   ├── config.py           # Constants
│   └── dashboard/          # FastAPI + HTMX web management console
│       ├── app.py
│       ├── systemd.py
│       ├── static/
│       └── templates/
├── scripts/
│   ├── voice-to-text-t     # Keyboard shortcut target
│   └── lp998_listener.py   # UGREEN LP998 Bluetooth touch-ring listener
├── services/               # systemd user units
├── models/                 # Local model files (gitignored)
└── restart-services.sh     # Convenience wrapper around systemctl
```

## Environment

```bash
cd /home/ccc/projects/voice_to_text
uv sync
uv pip install -e .
```

`voice_to_text` depends on the local `asr-core` package:

```toml
asr-core @ file:///home/ccc/projects/asr_core
```

## Running

### systemd services (recommended)

```bash
systemctl --user enable --now asr-core
systemctl --user enable --now voice-to-text
systemctl --user enable --now lp998-listener
systemctl --user enable --now voice-to-text-dashboard
```

Or use `./restart-services.sh`.

### Manual

```bash
# Terminal 1: ensure ASRCore is running
.venv/bin/python3 -m voice_to_text

# Terminal 2: toggle recording
.venv/bin/python3 scripts/voice-to-text-t
```

## Web dashboard

Open http://localhost:8080 to:

- Monitor ASRCore model status
- Load/unload ASR models
- Start/stop/restart services
- View live logs from `journalctl`

## Key sockets

- `/tmp/asr_core.sock` — ASRCore HTTP-over-Unix-socket
- `/tmp/voice_to_text.sock` — voice-to-text daemon toggle command

## Important notes

- The daemon is lightweight now; heavy model loading happens in ASRCore.
- `voice-to-text` auto-starts ASRCore via `ASRCoreClient(auto_start=True)` if the socket is missing.
- `models/` is gitignored; keep the actual model in `voice_to_text/models/qwen3-asr-0.6b` or symlink it from ASRCore.
- The LP998 listener is the only hardware-specific component left.
- Use `journalctl --user -fu voice-to-text -u asr-core -u voice-to-text-dashboard` for live logs.
