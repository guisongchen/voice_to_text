"""
Configuration constants for voice-to-text service.
"""


# Audio configuration
SAMPLE_RATE = 44100
CHANNELS = 2
CHUNK_SIZE = 1024
# FORMAT will be set dynamically when pyaudio is imported

# PipeWire noise prevention
WARMUP_CHUNKS = 3  # ~70ms - just enough to stabilize
COOLDOWN_CHUNKS = 2  # ~50ms - just for clean closure

# Beep configuration
START_BEEP_FREQ = 880  # Hz (A5 note)
FINISH_BEEP_FREQ = 660  # Hz (E5 note)
BEEP_DURATION = 0.2  # seconds
START_BEEP_DURATION = 0.08  # seconds for double beep
FINISH_BEEP_DURATION = 0.1  # seconds for single beep
BEEP_AMPLITUDE = 0.3  # 30% volume to prevent clipping
FADE_SAMPLES = int(SAMPLE_RATE * 0.01)  # 10ms fade

# Timeout configuration
RECORDING_THREAD_TIMEOUT = 3.0  # seconds
QUEUE_TIMEOUT = 1.0  # seconds
XDOTOOL_TIMEOUT = 10  # seconds


# Path configuration
PID_FILE_PATH = '/tmp/voice_to_text.pid'

# Minimum recording duration
MIN_DURATION_DEFAULT = 0.5  # seconds

# Model configuration
MODEL_SIZE_DEFAULT = 'medium'
MODEL_CHOICES = ['tiny', 'base', 'small', 'medium', 'large']

# Default recording duration
DEFAULT_RECORDING_DURATION = 10  # seconds

