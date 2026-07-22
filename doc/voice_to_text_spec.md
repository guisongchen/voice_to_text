# Voice-to-Text Input Tool - Requirements Specification

## 1. Overview

| Attribute | Value |
|-----------|-------|
| Project Name | Voice-to-Text Input Tool |
| Target Platform | Ubuntu Linux |
| Core Function | System-wide voice input triggered by desktop shortcut or Bluetooth remote, with automatic text insertion at cursor position |

---

## 2. Functional Requirements

### FR-01: Recording Control via Desktop Shortcut

| Attribute | Description |
|-----------|-------------|
| ID | FR-01 |
| Mode | Desktop shortcut toggle (Unix domain socket IPC) |
| Start Trigger | Command execution (desktop shortcut or LP998 Bluetooth button) |
| Stop Trigger | Same shortcut/button (toggle via socket `TOGGLE` command) |
| Scope | System-wide (works in any application) |

### FR-02: Speech-to-Text Conversion

| Attribute | Description |
|-----------|-------------|
| ID | FR-02 |
| Recognition Engine | Qwen3-ASR via ASRCore service (local deployment) |
| Input | Microphone audio (16kHz, mono, 16-bit PCM WAV) |
| Output | Transcribed text string |
| Language Support | Auto-detection (Chinese / English) |
| Network Dependency | None (fully offline) |
| IPC | HTTP-over-Unix-socket to ASRCore (`/tmp/asr_core.sock`) |

### FR-03: Text Insertion

| Attribute | Description |
|-----------|-------------|
| ID | FR-03 |
| Target Position | Cursor location in the currently focused application |
| Insertion Method | xdotool (short text) or clipboard paste via xclip/xsel (long text) |
| Compatibility | Any application that accepts text input |

### FR-04: Speaker Output Muting During Recording

| Attribute | Description |
|-----------|-------------|
| ID | FR-04 |
| Trigger | Recording starts |
| Action | Mute all audio output sinks |
| Scope | System-wide (speakers, headphones, Bluetooth headsets) |
| Backends | pactl (PulseAudio/PipeWire), wpctl (PipeWire), amixer (ALSA) |
| Restoration | Previous per-sink mute state restored when recording stops |
| Fallback | If no audio control utility is available, recording continues normally |

### FR-05: Recording Archive

| Attribute | Description |
|-----------|-------------|
| ID | FR-05 |
| Action | Each recording and its transcription are saved to `~/voice_recordings/` |
| Purpose | Future model fine-tuning data |
| Control | Configurable via `SAVE_RECORDINGS` in `config.py` (default: True) |

---

## 3. User Flow

```
┌─────────────────────────────────────────────┐
│  User is in any application                 │
│  (browser, editor, terminal, etc.)          │
└─────────────────────┬───────────────────────┘
                      ↓
         Press Alt+Shift+R (or LP998 button)
                      ↓
            ┌─────────────────┐
            │ Start Recording │  ← double beep, speakers muted
            └────────┬────────┘
                     ↓
              User speaks
                     ↓
        Press Alt+Shift+R (or LP998 button)
                     ↓
            ┌─────────────────┐
            │ Stop Recording  │  ← single beep, speakers restored
            └────────┬────────┘
                     ↓
        ASRCore transcription (Qwen3-ASR)
                     ↓
            ┌─────────────────┐
            │ Insert text at  │
            │ cursor position │
            └─────────────────┘
```

---

## 4. Technical Constraints

### 4.1 Environment Requirements

| Component | Requirement |
|-----------|-------------|
| Operating System | Ubuntu 24.04 |
| Desktop Environment | X11 |
| Text Insertion | `xdotool` (+ optional `xclip`/`xsel` for long text) |
| Audio Recording | PyAudio + PortAudio |
| Audio Control | `pactl`, `wpctl`, or `amixer` (optional) |
| ASR Service | ASRCore daemon (`/tmp/asr_core.sock`) |
| Bluetooth (optional) | UGREEN LP998 touch ring via evdev |

### 4.2 ASR Model

| Attribute | Description |
|-----------|-------------|
| Deployment | Local only, managed by ASRCore |
| Default Model | Qwen3-ASR-1.7B |
| Alternative | qwen3-asr-0.6b |

### 4.3 Daemon Lifecycle

| Attribute | Description |
|-----------|-------------|
| Idle Timeout | 1800 seconds (30 minutes) |
| IPC | Unix domain socket at `/tmp/voice_to_text.sock` |
| State Machine | IDLE → RECORDING → TRANSCRIBING → IDLE |
| Bounce Guard | 200ms minimum between state transitions |

---

## 5. Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC-01 | Recording starts within 200ms of command execution |
| AC-02 | Recording stops on second shortcut press |
| AC-03 | Speech is transcribed to text without network connection |
| AC-04 | Transcribed text is inserted at the current cursor position |
| AC-05 | Works across different applications (browser, text editor, terminal) |
| AC-06 | Speaker outputs are muted while recording and restored when recording stops |
| AC-07 | Recording continues normally when audio control utilities are unavailable |
| AC-08 | Daemon exits cleanly after 30 minutes of inactivity |
| AC-09 | Graceful shutdown restores speaker state and salvages in-flight transcription |
