"""
CLI interface for voice-to-text service.
"""

import argparse
import sys

from ..services.voice_to_text_service import VoiceToTextService




def main():
    parser = argparse.ArgumentParser(
        description="Voice-to-Text Input Tool - Record audio and transcribe to text",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
System Requirements:
  1. xdotool must be installed:
     sudo apt install xdotool

  2. NVIDIA GPU with CUDA for Whisper transcription (optional, works on CPU)

Usage:
  # Start recording (waits for SIGUSR1 to stop)
  voice-to-text

  # Use faster model
  voice-to-text --model small

  # Keep audio files for debugging
  voice-to-text --keep-audio

Desktop Shortcut Setup (GNOME):
  1. Open Settings > Keyboard > Keyboard Shortcuts
  2. Click "+" to add custom shortcut
  3. Name: "Voice to Text"
  4. Command: /full/path/to/voice_to_text_toggle.sh
  5. Set shortcut: Alt+R
  6. Press Alt+R to start, Alt+R again to stop!
        """
    )

    parser.add_argument(
        '-m', '--model',
        type=str,
        default='medium',
        choices=['tiny', 'base', 'small', 'medium', 'large'],
        help='Whisper model size (default: medium per spec)'
    )
    parser.add_argument(
        '--keep-audio',
        action='store_true',
        help='Keep audio files instead of deleting them (for debugging)'
    )

    args = parser.parse_args()

    # Run the service (always uses PID file mode)
    service = VoiceToTextService(
        model_size=args.model,
        keep_audio=args.keep_audio
    )

    return service.run()


if __name__ == "__main__":
    sys.exit(main())