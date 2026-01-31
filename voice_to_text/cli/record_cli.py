"""
Unified CLI tool for recording audio and automatically transcribing it.
Updated to use RecordService with Alt+R stopping.
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

from ..services.record_service import RecordService
from ..transcribe import AudioTranscriber


def main():
    parser = argparse.ArgumentParser(
        description="Record audio from microphone and automatically transcribe it",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Record with Alt+R stopping and transcribe (default)
  record

  # Record with custom filename
  record -o interview.wav

  # Use smaller model for faster transcription
  record -m tiny

  # Delete audio file after transcription
  record --delete-audio

  # Record only, skip transcription
  record --no-transcribe

  # Transcribe existing file without recording
  record --transcribe-only recording.wav


Recording Options:
  -o, --output       Output audio filename (default: temporary file)
                     Press Alt+R (toggle script) to stop recording

Transcription Options:
  -m, --model        Whisper model: tiny/base/small/medium/large (default: small)
  --delete-audio     Delete audio file after transcription
  --no-transcribe    Record only, skip transcription

Other Options:
  --transcribe-only  Transcribe existing file without recording

Note: Uses same toggle script as voice-to-text (Alt+R desktop shortcut)
        """
    )

    # Recording options (duration is hardcoded to 10 seconds)
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Output filename (default: recording_TIMESTAMP.wav)'
    )

    # Transcription options
    parser.add_argument(
        '-m', '--model',
        type=str,
        default='small',
        choices=['tiny', 'base', 'small', 'medium', 'large'],
        help='Whisper model size (default: small)'
    )
    parser.add_argument(
        '--delete-audio',
        action='store_true',
        help='Delete audio file after successful transcription'
    )
    parser.add_argument(
        '--no-transcribe',
        action='store_true',
        help='Record only, skip transcription'
    )

    # Special modes
    parser.add_argument(
        '--transcribe-only',
        type=str,
        metavar='FILE',
        help='Transcribe existing audio file without recording'
    )

    args = parser.parse_args()


    # Transcribe-only mode
    if args.transcribe_only:
        audio_file = Path(args.transcribe_only)
        if not audio_file.exists():
            print(f"Error: File not found: {audio_file}", file=sys.stderr)
            sys.exit(1)

        print(f"Transcribing: {audio_file}")
        transcriber = AudioTranscriber(model_size=args.model)
        try:
            output_file = transcriber.transcribe_file(audio_file, force=True)
            print(f"\n✓ Transcription complete!")
            print(f"  Text file: {output_file}")
        except Exception as e:
            print(f"\n✗ Transcription failed: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # Record + Transcribe mode (default) using RecordService
    try:
        # Create and run RecordService
        service = RecordService(
            output=args.output,
            model_size=args.model,
            delete_audio=args.delete_audio,
            no_transcribe=args.no_transcribe
        )

        return service.run()

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()