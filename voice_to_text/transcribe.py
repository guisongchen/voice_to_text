#!/usr/bin/env python3
"""
Transcribe audio files to text using OpenAI's Whisper model.
"""
import whisper
import torch
import argparse
import sys
from pathlib import Path
import warnings
from voice_to_text.config import MODEL_SIZE_DEFAULT, MODEL_CHOICES

# Suppress FP16 warnings
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")


class AudioTranscriber:
    def __init__(self, model_size="medium"):
        """Initialize transcriber with specified Whisper model size.
        
        Args:
            model_size: One of 'tiny', 'base', 'small', 'medium', 'large'
        """
        print(f"Loading Whisper model '{model_size}' on GPU...")
        print("(First run will download model files)")
        self.model = whisper.load_model(model_size, device="cuda")
        
        # Display GPU info
        gpu_name = torch.cuda.get_device_name(0)
        print(f"Model loaded successfully on {gpu_name}!")
    
    def transcribe_file(self, audio_path, output_path=None, force=False):
        """Transcribe a single audio file.
        
        Args:
            audio_path: Path to audio file (WAV, MP3, etc.)
            output_path: Path to save transcription (default: same name as audio with .txt)
            force: Overwrite existing transcription file
        
        Returns:
            Path to transcription file
        """
        audio_path = Path(audio_path)
        
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Determine output path
        if output_path is None:
            output_path = audio_path.with_suffix('.txt')
        else:
            output_path = Path(output_path)
        
        # Check if transcription already exists
        if output_path.exists() and not force:
            print(f"Skipping {audio_path.name} (transcription already exists)")
            print(f"  Use --force to overwrite")
            return output_path
        
        print(f"\nTranscribing: {audio_path.name}")
        print("This may take a while...")
        
        try:
            # Auto-detect language and transcribe
            result = self.model.transcribe(
                str(audio_path), 
                verbose=False,
                language=None,  # Auto-detect language
                task='transcribe'  # Transcribe in original language(s)
            )
            text = result["text"].strip()
            detected_language = result.get("language", "unknown")
            
            # Save transcription
            output_path.write_text(text, encoding='utf-8')
            
            print(f"✓ Saved to: {output_path.name}")
            print(f"  Detected language: {detected_language}")
            print(f"  Text length: {len(text)} characters")
            
            return output_path
            
        except Exception as e:
            print(f"✗ Error transcribing {audio_path.name}: {e}", file=sys.stderr)
            raise
    
    def transcribe_directory(self, directory=None, pattern="*.wav", force=False):
        """Transcribe all audio files in a directory.
        
        Args:
            directory: Path to directory (default: current directory)
            pattern: File pattern to match (default: *.wav)
            force: Overwrite existing transcriptions
        
        Returns:
            List of transcription file paths
        """
        if directory is None:
            directory = Path.cwd()
        else:
            directory = Path(directory)
        
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")
        
        # Find all matching audio files
        audio_files = sorted(directory.glob(pattern))
        
        if not audio_files:
            print(f"No files matching '{pattern}' found in {directory}")
            return []
        
        print(f"Found {len(audio_files)} file(s) to transcribe")
        
        transcriptions = []
        for i, audio_file in enumerate(audio_files, 1):
            print(f"\n[{i}/{len(audio_files)}]", end=" ")
            try:
                output = self.transcribe_file(audio_file, force=force)
                transcriptions.append(output)
            except Exception as e:
                print(f"Failed to transcribe {audio_file.name}: {e}", file=sys.stderr)
                continue
        
        print(f"\n\nCompleted: {len(transcriptions)}/{len(audio_files)} files transcribed")
        return transcriptions


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe audio files to text using Whisper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Transcribe a single file
  uv run transcribe.py recording.wav
  
  # Transcribe all WAV files in current directory
  uv run transcribe.py --all
  
  # Use a different model size
  uv run transcribe.py -m base recording.wav
  
  # Specify output file
  uv run transcribe.py -o transcript.txt recording.wav
  
  # Overwrite existing transcriptions
  uv run transcribe.py --force --all

Model sizes (accuracy vs speed):
  tiny   - Fastest, least accurate (~1GB RAM)
  base   - Fast, reasonable accuracy
  small  - Good balance (default, ~2GB RAM)
  medium - High accuracy, slower (~5GB RAM)
  large  - Best accuracy, very slow (~10GB RAM)
        """
    )
    
    parser.add_argument(
        'audio_file',
        nargs='?',
        help='Audio file to transcribe (WAV, MP3, etc.)'
    )
    parser.add_argument(
        '-a', '--all',
        action='store_true',
        help='Transcribe all WAV files in current directory'
    )
    parser.add_argument(
        '-d', '--directory',
        type=str,
        help='Directory containing audio files (used with --all)'
    )
    parser.add_argument(
        '-p', '--pattern',
        type=str,
        default='*.wav',
        help='File pattern to match (default: *.wav)'
    )
    parser.add_argument(
        '-m', '--model',
        type=str,
        default=MODEL_SIZE_DEFAULT,
        choices=MODEL_CHOICES,
        help=f'Whisper model size (default: {MODEL_SIZE_DEFAULT})'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        help='Output file path (only for single file transcription)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite existing transcription files'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.all and not args.audio_file:
        parser.error("Provide an audio file or use --all to transcribe all files")
    
    if args.all and args.audio_file:
        parser.error("Cannot use --all with a specific audio file")
    
    if args.output and args.all:
        parser.error("Cannot use --output with --all (transcriptions are auto-named)")
    
    try:
        transcriber = AudioTranscriber(model_size=args.model)
        
        if args.all:
            transcriber.transcribe_directory(
                directory=args.directory,
                pattern=args.pattern,
                force=args.force
            )
        else:
            transcriber.transcribe_file(
                audio_path=args.audio_file,
                output_path=args.output,
                force=args.force
            )
            
    except KeyboardInterrupt:
        print("\n\nTranscription cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
