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

Usage Modes:

  FIXED DURATION MODE:
    Record for a specified duration and auto-transcribe
    Usage: voice-to-text --record-once -d 5

  PID FILE MODE (toggle script):
    Record until SIGUSR1 signal received, useful for desktop shortcuts
    Usage: voice-to-text --record-once --use-pidfile

Examples:
  # Record for 5 seconds and transcribe
  voice-to-text --record-once -d 5

  # Use PID file mode with toggle script
  ./voice_to_text_toggle.sh

  # Use faster model
  voice-to-text --record-once --model small

  # Keep audio files for debugging
  voice-to-text --record-once --keep-audio

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
        '-d', '--duration',
        type=float,
        help='Fixed recording duration in seconds (required for fixed duration mode)'
    )
    parser.add_argument(
        '--min-duration',
        type=float,
        default=0.5,
        help='Minimum recording duration in seconds (default: 0.5)'
    )
    parser.add_argument(
        '--keep-audio',
        action='store_true',
        help='Keep audio files instead of deleting them (for debugging)'
    )
    parser.add_argument(
        '--record-once',
        action='store_true',
        help='Record once and exit (required; use with --use-pidfile or -d for duration)'
    )
    parser.add_argument(
        '--use-pidfile',
        action='store_true',
        help='Use PID file + SIGUSR1 for stopping (toggle script mode)'
    )

    args = parser.parse_args()

    # Require --record-once since hotkey mode is removed
    if not args.record_once:
        parser.error("Please specify --record-once to use fixed duration or PID file mode")

    # Run the service
    service = VoiceToTextService(
        model_size=args.model,
        min_duration=args.min_duration,
        keep_audio=args.keep_audio,
        duration=args.duration,
        no_hotkey=args.record_once,
        wait_for_key=False,
        use_pidfile=args.use_pidfile
    )

    return service.run()


if __name__ == "__main__":
    sys.exit(main())