import argparse

from .config import MODEL_SIZE_DEFAULT, MODEL_CHOICES
from .service import VoiceToTextService


def main():
    parser = argparse.ArgumentParser(
        description="Voice-to-Text Input Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Usage:
  voice-to-text                    # Start recording
  voice-to-text --keep-audio       # Keep audio files for debugging

Available model:
  qwen3-asr-0.6b (default)

Toggle Script:
  Run scripts/voice-to-text-t to start/stop recording via socket.
"""
    )
    parser.add_argument(
        '-m', '--model',
        type=str, default=MODEL_SIZE_DEFAULT, choices=MODEL_CHOICES,
        help=f'ASR model (default: {MODEL_SIZE_DEFAULT})'
    )
    parser.add_argument(
        '--keep-audio', action='store_true',
        help='Keep audio files for debugging'
    )
    args = parser.parse_args()

    service = VoiceToTextService(model_size=args.model, keep_audio=args.keep_audio)
    try:
        return service.run()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return 1
    finally:
        service.cleanup()
