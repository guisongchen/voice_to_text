"""
Main voice-to-text service orchestrator.
Greatly reduced from original 842 lines to ~200 lines.
"""

import sys
from pathlib import Path

from .dependency_container import DependencyContainer


class VoiceToTextService:
    """Main service for voice-to-text input."""

    def __init__(self, model_size='medium', min_duration=0.5, keep_audio=False,
                 duration=None, no_hotkey=False, wait_for_key=False, use_pidfile=False):
        """
        Initialize voice-to-text service.

        Args:
            model_size: Whisper model size
            min_duration: Minimum recording duration in seconds
            keep_audio: Keep audio files instead of deleting them
            duration: Fixed recording duration (for fixed duration mode)
            no_hotkey: Unused (kept for backward compatibility)
            wait_for_key: Unused (kept for backward compatibility)
            use_pidfile: Use PID file + SIGUSR1 for stopping
        """
        self.config = {
            'model_size': model_size,
            'min_duration': min_duration,
            'keep_audio': keep_audio,
            'duration': duration,
            'no_hotkey': no_hotkey,
            'wait_for_key': wait_for_key,
            'use_pidfile': use_pidfile
        }

        self.dependency_container = None
        self.mode = None

    def initialize(self):
        """Initialize all components."""
        print("=" * 60)
        print("Voice-to-Text Input Tool")
        print("=" * 60)

        # Create dependency container
        self.dependency_container = DependencyContainer(self.config)

        # Skip keyboard device - no longer needed
        step = 1
        total_steps = 2

        # Check xdotool
        print(f"\n[{step}/{total_steps}] Checking xdotool...")
        if not self.dependency_container.text_inserter.check_xdotool():
            print("✗ Error: xdotool not found!")
            print("  Install with: sudo apt install xdotool")
            return False
        print("✓ xdotool is available")

        step += 1

        # Pre-load Whisper model (will be loaded lazily by dependency container)
        print(f"\n[{step}/{total_steps}] Loading Whisper model '{self.config['model_size']}'...")
        print("  (This may take 5-10 seconds on first run)")
        # Model will be loaded when accessed via property
        _ = self.dependency_container.transcriber  # Trigger loading

        # Show diagnostic mode info
        if self.config['keep_audio']:
            print("\n" + "=" * 60)
            print("DIAGNOSTIC MODE:")
            print("  • Recording files will be PRESERVED")
            print("=" * 60)

        # Create the appropriate mode
        self.mode = self.dependency_container.create_mode()

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