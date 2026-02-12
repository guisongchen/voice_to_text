"""
Configuration constants for voice-to-text service.
"""


# Audio configuration
SAMPLE_RATE = 44100  # High quality for better beep audibility
CHANNELS = 2
CHUNK_SIZE = 1024
# FORMAT will be set dynamically when pyaudio is imported

# PipeWire noise prevention
WARMUP_CHUNKS = 0  # Disabled to prevent cutting off start of speech
COOLDOWN_CHUNKS = 0  # Disabled for faster response time

# Beep configuration
START_BEEP_FREQ = 784  # Hz (G5 note)
FINISH_BEEP_FREQ = 523  # Hz (C5 note)
START_BEEP_DURATION = 0.24  # seconds - balance between speed and audibility
FINISH_BEEP_DURATION = 0.12  # seconds - balance between speed and audibility
START_BEEP_AMPLITUDE = 1.0  # volume for start
FINISH_BEEP_AMPLITUDE = 1.0  # volume for finish
FADE_SAMPLES = int(SAMPLE_RATE * 0.01)  # 10ms fade

# Timeout configuration
XDOTOOL_TIMEOUT = 10  # seconds


# Path configuration
SOCKET_PATH = '/tmp/voice_to_text.sock'

# Model configuration
MODEL_SIZE_DEFAULT = 'medium'
MODEL_CHOICES = ['tiny', 'base', 'small', 'medium', 'large']

# Language configuration - languages supported for transcription
# Empty list means no restriction (auto-detect all languages)
# Use language codes: 'en' (English), 'zh' (Chinese), 'es' (Spanish), etc.
SUPPORTED_LANGUAGES = ['en', 'zh']  # English and Chinese only
FALLBACK_LANGUAGE = 'en'  # Default language if detected language is not supported

# Chinese output preference: 'simplified' or 'traditional'
CHINESE_VARIANT = 'simplified'  # Force Simplified Chinese output
