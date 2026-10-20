import argparse
import warnings

from .config import MODEL_SIZE_DEFAULT, MODEL_CHOICES
from .service import VoiceToTextService


def main():
    # Suppress FP16 warning that may propagate from ASRCore's model layer.
    warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")

    parser = argparse.ArgumentParser(
        description="Voice-to-Text Input Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Usage:
  voice-to-text                    # Start recording
  voice-to-text --keep-audio       # Keep audio files for debugging

Available models:
  qwen3-asr-0.6b
  Qwen3-ASR-1.7B

When no model is specified, voice_to_text uses whichever model
ASRCore already has loaded, falling back to {MODEL_SIZE_DEFAULT}
if none is loaded.

Toggle Script:
  Run scripts/voice-to-text-t to start/stop recording via socket.
"""
    )
    parser.add_argument(
        '-m', '--model',
        type=str, default=None, choices=MODEL_CHOICES,
        help=f'ASR model (default: use currently loaded ASRCore model, else {MODEL_SIZE_DEFAULT})'
    )
    parser.add_argument(
        '--keep-audio', action='store_true',
        help='Keep audio files for debugging'
    )
    parser.add_argument(
        '--start-recording', action='store_true',
        help='Begin recording immediately (used by toggle for cold-start)'
    )
    args = parser.parse_args()

    service = VoiceToTextService(model_size=args.model, keep_audio=args.keep_audio)
    try:
        return service.run(start_recording=args.start_recording)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return 1
    finally:
        service.cleanup()
