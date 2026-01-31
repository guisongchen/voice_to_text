# Voice-to-Text Input Tool - Requirements Specification

## 1. Overview

| Attribute | Value |
|-----------|-------|
| Project Name | Voice-to-Text Input Tool |
| Target Platform | Ubuntu Linux |
| Core Function | System-wide voice input triggered by desktop shortcut or fixed duration, with automatic text insertion at cursor position |

---

## 2. Functional Requirements

### FR-01: Recording Control via Desktop Shortcut or Fixed Duration

| Attribute | Description |
|-----------|-------------|
| ID | FR-01 |
| Modes | 1. Desktop shortcut toggle (PID file + SIGUSR1) 2. Fixed duration recording |
| Start Trigger | Command execution (desktop shortcut) or timer |
| Stop Trigger | SIGUSR1 signal (toggle) or timer expiration |
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

---

## 3. User Flow

**Note**: Original hotkey mode has been removed. Current implementation uses desktop shortcut toggle or fixed duration recording.

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
