"""
Unified CLI tool for recording audio and automatically transcribing it.
Updated to use new AudioService instead of AudioRecorder.
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

from ..core.audio_service import AudioService
from ..transcribe import AudioTranscriber
from ..core.config import SAMPLE_RATE, CHANNELS


def main():
    parser = argparse.ArgumentParser(
        description="Record audio from microphone and automatically transcribe it",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Record 10 seconds and transcribe (default)
  record

  # Record for 30 seconds
  record -d 30

  # Record with custom filename
  record -o interview.wav

  # Use smaller model for faster transcription
  record -m tiny -d 5

  # Delete audio file after transcription
  record --delete-audio

  # Transcribe existing file without recording
  record --transcribe-only recording.wav

  # List available audio devices
  record --list-devices

Recording Options:
  -d, --duration     Recording duration in seconds (default: 10)
  -o, --output       Output filename (default: recording_TIMESTAMP.wav)

Transcription Options:
  -m, --model        Whisper model: tiny/base/small/medium/large (default: small)
  --delete-audio     Delete audio file after transcription
  --no-transcribe    Record only, skip transcription

Other Options:
  --transcribe-only  Transcribe existing file without recording
  --list-devices     List available audio input devices
        """
    )

    # Recording options
    parser.add_argument(
        '-d', '--duration',
        type=int,
        default=10,
        help='Recording duration in seconds (default: 10)'
    )
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
    parser.add_argument(
        '--list-devices',
        action='store_true',
        help='List available audio input devices and exit'
    )

    args = parser.parse_args()

    # List devices mode
    if args.list_devices:
        recorder = AudioService(
            sample_rate=SAMPLE_RATE,
            channels=CHANNELS
        )
        try:
            recorder.list_devices()
        finally:
            recorder.cleanup()
        return

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

    # Record + Transcribe mode (default)
    try:
        # Step 1: Record audio
        print("=" * 60)
        print("STEP 1: Recording Audio")
        print("=" * 60)

        recorder = AudioService(
            sample_rate=SAMPLE_RATE,
            channels=CHANNELS
        )

        try:
            audio_file = recorder.record(args.duration, args.output)
        finally:
            recorder.cleanup()

        # Step 2: Transcribe (unless --no-transcribe)
        if args.no_transcribe:
            print(f"\n✓ Recording complete!")
            print(f"  Audio file: {audio_file}")
            return

        print("\n" + "=" * 60)
        print("STEP 2: Transcribing Audio")
        print("=" * 60)

        transcriber = AudioTranscriber(model_size=args.model)
        text_file = transcriber.transcribe_file(audio_file, force=True)

        # Display results
        print("\n" + "=" * 60)
        print("✓ Complete!")
        print("=" * 60)
        print(f"Audio file: {audio_file}")
        print(f"Text file:  {text_file}")

        # Show transcription preview
        text_content = Path(text_file).read_text(encoding='utf-8')
        preview = text_content[:200] + "..." if len(text_content) > 200 else text_content
        print(f"\nTranscription preview:")
        print(f"  {preview}")

        # Delete audio if requested
        if args.delete_audio:
            Path(audio_file).unlink()
            print(f"\n✓ Audio file deleted: {audio_file}")
            print(f"  Text file kept: {text_file}")

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()