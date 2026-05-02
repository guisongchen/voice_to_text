import warnings
from pathlib import Path

# Audio settings
SAMPLE_RATE = 44100
CHANNELS = 2
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

# Model
MODEL_SIZE_DEFAULT = 'qwen3-asr-0.6b'
MODEL_CHOICES = ['qwen3-asr-0.6b']
MODEL_LOCAL_PATH = str(Path(__file__).parent.parent.parent / "models" / "qwen3-asr-0.6b")

# Toggle
SOCKET_FILE = Path("/tmp/voice_to_text.sock")
SCRIPT_DIR = Path(__file__).parent.parent.parent.resolve()
VENV_PYTHON = SCRIPT_DIR / ".venv" / "bin" / "python3"
LOG_FILE = Path("/tmp/voice_to_text.log")
STOP_TIMEOUT = 30.0
STARTUP_TIMEOUT = 5.0

warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")
