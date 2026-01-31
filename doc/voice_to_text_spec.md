# Voice-to-Text Input Tool - Requirements Specification

## 1. Overview

| Attribute | Value |
|-----------|-------|
| Project Name | Voice-to-Text Input Tool |
| Target Platform | Ubuntu Linux |
| Core Function | System-wide voice input triggered by hotkey, with automatic text insertion at cursor position |

---

## 2. Functional Requirements

### FR-01: Global Hotkey Recording Control

| Attribute | Description |
|-----------|-------------|
| ID | FR-01 |
| Hotkey | `Alt + R` |
| Key Press | Start recording |
| Key Release | Stop recording |
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
| Insertion Method | Simulated keyboard input or clipboard paste |
| Compatibility | Any application that accepts text input |

---

## 3. User Flow

```
┌─────────────────────────────────────────────┐
│  User is in any application                 │
│  (browser, editor, terminal, etc.)          │
└─────────────────────┬───────────────────────┘
                      ↓
            Press Alt+R (hold down)
                      ↓
            ┌─────────────────┐
            │ Start Recording │
            └────────┬────────┘
                     ↓
              User speaks
                     ↓
             Release Alt+R
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
| Desktop Environment | Wayland (default) |
| Text Insertion | `ydotool` or `wtype` |
| Hotkey Listener | `evdev` (requires input group permission) |

### 4.2 Whisper Model

| Attribute | Description |
|-----------|-------------|
| Deployment | Local only |
| Recommended Model Size | `medium` |

---

## 5. Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC-01 | Pressing `Alt+R` starts audio recording within 200ms |
| AC-02 | Releasing `Alt+R` stops recording immediately |
| AC-03 | Speech is transcribed to text without network connection |
| AC-04 | Transcribed text is inserted at the current cursor position |
| AC-05 | Works across different applications (browser, text editor, terminal) |
