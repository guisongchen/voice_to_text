"""
PID file mode: Use PID file + SIGUSR1 signal for stopping.
"""

import signal
import time
import os
from pathlib import Path
from .base_mode import BaseMode

from ..core.config import PID_FILE_PATH


class PidFileMode(BaseMode):
    """PID file mode: Use PID file + SIGUSR1 signal for stopping."""

    def __init__(self, audio_service, text_inserter,
                 audio_feedback, transcriber, config):
        """Initialize PID file mode."""
        super().__init__(audio_service, text_inserter,
                        audio_feedback, transcriber, config)
        self.pidfile = Path(PID_FILE_PATH)

    def run(self):
        """Run PID file mode recording."""
        print("\n" + "=" * 60)
        print("✓ Ready! Recording will start in 2 seconds")
        print("  Send SIGUSR1 or run toggle script again to stop")
        print("=" * 60)

        # Setup signal handlers
        self._setup_signal_handlers()
        signal.signal(signal.SIGUSR1, self._sigusr1_handler)

        try:
            print("\nStarting recording in 2 seconds...")
            print("Run the same command again (or send SIGUSR1) to stop recording")
            time.sleep(2)

            # Write PID file
            self.pidfile.write_text(str(os.getpid()))

            self._start_recording()

            # Wait for signal to stop
            while not self.stop_signal_received and not self.should_exit:
                time.sleep(0.1)

            # Stop recording and transcribe
            if self.is_recording:
                self._stop_recording()

            # Clean up PID file
            if self.pidfile.exists():
                self.pidfile.unlink()

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
        """Start PID file mode recording."""
        # Already handled in run()
        pass

    def stop(self):
        """Stop PID file mode recording."""
        self.should_exit = True
        if self.is_recording:
            self._stop_recording()

    def cleanup(self):
        """Clean up resources including PID file."""
        super().cleanup()
        # Clean up PID file if it exists
        if self.pidfile.exists():
            try:
                self.pidfile.unlink()
            except Exception:
                pass