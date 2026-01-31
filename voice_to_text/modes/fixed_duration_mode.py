"""
Fixed duration mode: Record for specified duration.
"""

import time
from .base_mode import BaseMode


class FixedDurationMode(BaseMode):
    """Fixed duration mode: Record for specified duration."""

    def __init__(self, audio_service, text_inserter,
                 audio_feedback, transcriber, config):
        """Initialize fixed duration mode."""
        super().__init__(audio_service, text_inserter,
                        audio_feedback, transcriber, config)
        self.duration = config.get('duration', 10)

    def run(self):
        """Run fixed duration recording."""
        print("\n" + "=" * 60)
        print(f"✓ Ready! Recording will start in 2 seconds ({self.duration}s duration)")
        print("=" * 60)

        # Setup signal handlers
        self._setup_signal_handlers()

        try:
            time.sleep(2)  # Give user time to focus the target window
            self._start_recording()
            time.sleep(self.duration)
            self._stop_recording()
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopping recording...")
            if self.is_recording:
                self.is_recording = False
                time.sleep(0.5)  # Give recording thread time to finish
                self._stop_recording()
        except Exception as e:
            print(f"\n✗ Error: {e}", flush=True)
            return 1
        finally:
            self.cleanup()

        return 0

    def start(self):
        """Start fixed duration recording."""
        # Already handled in run()
        pass

    def stop(self):
        """Stop fixed duration recording."""
        self.should_exit = True
        if self.is_recording:
            self._stop_recording()