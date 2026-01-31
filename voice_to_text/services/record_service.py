"""
Record service for recording audio and saving transcription to file.
"""

import sys
from pathlib import Path

from .dependency_container import DependencyContainer


class RecordService:
    """Record service for saving transcription to file."""

    def __init__(self, output=None, model_size='small', delete_audio=False, no_transcribe=False):
        """
        Initialize record service.

        Args:
            output: Output audio filename (optional)
            model_size: Whisper model size
            delete_audio: Delete audio file after transcription
            no_transcribe: Skip transcription, just save audio
        """
        self.config = {
            'model_size': model_size,
            'keep_audio': not delete_audio,  # Map delete_audio to keep_audio
            'delete_audio': delete_audio,
            'no_transcribe': no_transcribe,
            'output_audio_path': output,
            'use_pidfile': True  # Always use PID file mode
        }

        self.dependency_container = None
        self.mode = None

    def initialize(self):
        """Initialize all components."""
        print("=" * 60)
        print("Record Tool - Save Transcription to File")
        print("=" * 60)

        # Create dependency container
        self.dependency_container = DependencyContainer(self.config)

        # No need to check xdotool for record mode (text insertion not required)
        # But we still need it for dependency container compatibility
        step = 1
        total_steps = 1

        # Pre-load Whisper model (will be loaded lazily by dependency container)
        print(f"\n[{step}/{total_steps}] Loading Whisper model '{self.config['model_size']}'...")
        print("  (This may take 5-10 seconds on first run)")
        # Model will be loaded when accessed via property
        _ = self.dependency_container.transcriber  # Trigger loading

        # Show configuration info
        if self.config.get('output_audio_path'):
            print(f"\nOutput audio file: {self.config['output_audio_path']}")
        if self.config.get('no_transcribe'):
            print("Mode: Record only (no transcription)")
        elif self.config.get('delete_audio'):
            print("Mode: Transcribe and delete audio file")
        else:
            print("Mode: Transcribe and keep audio file")

        # Create the appropriate mode
        self.mode = self.dependency_container.create_record_mode()

        return True

    def run(self):
        """Main entry point - run the selected mode."""
        if not self.initialize():
            return 1

        try:
            return self.mode.run()
        except Exception as e:
            print(f"\n✗ Error: {e}", file=sys.stderr)
            return 1
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up all resources."""
        if self.dependency_container:
            self.dependency_container.cleanup()