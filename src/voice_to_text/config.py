from pathlib import Path

# Audio settings
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024

# Socket IPC
SOCKET_PATH = '/tmp/voice_to_text.sock'

# Beep sounds
START_BEEP_FREQ = 784
FINISH_BEEP_FREQ = 523
START_BEEP_DURATION = 0.24
FINISH_BEEP_DURATION = 0.12

# Text insertion
XDOTOOL_TIMEOUT = 10
# Keystroke delay for the xdotool-type fallback path (used only when no
# clipboard tool is installed).  CJK input via xdotool remaps keycodes per
# character and races with the receiving app; a larger delay reduces
# dropped characters.  The primary clipboard path is unaffected.
XDOTOOL_TYPE_DELAY_MS = 30
# WM_CLASS values (lowercased) of terminal emulators where Ctrl+V is
# swallowed by the shell/readline (quoted-insert) and the emulator's paste
# shortcut is Ctrl+Shift+V instead.
TERMINAL_WM_CLASSES = {
    'gnome-terminal-server', 'gnome-terminal', 'org.gnome.terminal',
    'xterm', 'uxterm', 'kitty', 'alacritty', 'konsole', 'tilix',
    'terminator', 'wezterm', 'foot', 'st', 'urxvt', 'guake', 'tilda',
    'xfce4-terminal', 'lxterminal', 'mate-terminal', 'ptyxis', 'kgx',
}

# Model
MODEL_SIZE_DEFAULT = 'Qwen3-ASR-1.7B'
MODEL_CHOICES = ['qwen3-asr-0.6b', 'Qwen3-ASR-1.7B']

# Audio output control
MUTE_SPEAKERS_DURING_RECORDING = True

# Recording archive
SAVE_RECORDINGS = True  # Set False to disable archiving to ~/voice_recordings/

# Toggle
SOCKET_FILE = Path(SOCKET_PATH)
SCRIPT_DIR = Path(__file__).parent.parent.parent.resolve()
VENV_PYTHON = SCRIPT_DIR / ".venv" / "bin" / "python3"
LOG_FILE = Path("/tmp/voice_to_text.log")
STOP_TIMEOUT = 30.0
STARTUP_TIMEOUT = 5.0

# Persistent daemon
IDLE_TIMEOUT_SECONDS = 1800
IDLE_CHECK_INTERVAL = 60
MIN_TRANSITION_INTERVAL = 0.2
SHUTDOWN_TRANSCRIBE_GRACE = 15.0
MIN_RECORDING_DURATION = 0.5
