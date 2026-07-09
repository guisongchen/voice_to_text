# Voice-to-Text Input Tool - Requirements Specification

## 1. Overview

| Attribute | Value |
|-----------|-------|
| Project Name | Voice-to-Text Input Tool |
| Target Platform | Ubuntu Linux |
| Core Function | System-wide voice input triggered by desktop shortcut, with automatic text insertion at cursor position |

---

## 2. Functional Requirements

### FR-01: Recording Control via Desktop Shortcut

| Attribute | Description |
|-----------|-------------|
| ID | FR-01 |
| Mode | Desktop shortcut toggle (PID file + SIGUSR1) |
| Start Trigger | Command execution (desktop shortcut) |
| Stop Trigger | SIGUSR1 signal (toggle) |
| Scope | System-wide (works in any application) |

### FR-02: Speech-to-Text Conversion

| Attribute | Description |
|-----------|-------------|
| ID | FR-02 |
| Recognition Engine | OpenAI Whisper (local deployment) |
| Input | Microphone audio stream |
| Output | Transcribed text string |
| Language Support | Auto-detection (Chinese / English) |
| Network Dependency | None (fully offline) |

### FR-03: Text Insertion

| Attribute | Description |
|-----------|-------------|
| ID | FR-03 |
| Target Position | Cursor location in the currently focused application |
| Insertion Method | xdotool (simulated keyboard input) |
| Compatibility | Any application that accepts text input |

### FR-04: Speaker Output Muting During Recording

| Attribute | Description |
|-----------|-------------|
| ID | FR-04 |
| Trigger | Recording starts |
| Action | Mute all audio output sinks |
| Scope | System-wide (speakers, headphones, Bluetooth headsets) |
| Restoration | Previous mute state restored when recording stops |
| Fallback | If no audio control utility is available, recording continues normally |

---

## 3. User Flow

**Note**: Original hotkey mode has been removed. Current implementation uses desktop shortcut toggle only.

```
┌─────────────────────────────────────────────┐
│  User is in any application                 │
│  (browser, editor, terminal, etc.)          │
└─────────────────────┬───────────────────────┘
                      ↓
            Press Alt+R
                      ↓
            ┌─────────────────┐
            │ Start Recording │
            └────────┬────────┘
                     ↓
              User speaks
                     ↓
             Press Alt+R
                     ↓
            ┌─────────────────┐
            │ Stop Recording  │
            └────────┬────────┘
                     ↓
         Local Whisper transcription
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
| Text Insertion | `xdotool` |
| Hotkey Listener | Desktop shortcuts |

### 4.2 Whisper Model

| Attribute | Description |
|-----------|-------------|
| Deployment | Local only |
| Recommended Model Size | `medium` |

---

## 5. Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC-01 | Recording starts within 200ms of command execution |
| AC-02 | Recording stops after specified duration or SIGUSR1 signal |
| AC-03 | Speech is transcribed to text without network connection |
| AC-04 | Transcribed text is inserted at the current cursor position |
| AC-05 | Works across different applications (browser, text editor, terminal) |
| AC-06 | Speaker outputs are muted while recording and restored when recording stops |
| AC-07 | Recording continues normally when audio control utilities are unavailable |
