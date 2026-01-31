"""
Record PID file mode: Use PID file + SIGUSR1 signal for stopping, save transcription to file.
"""

import signal
import time
import os
from pathlib import Path
from .base_mode import BaseMode
from .pid_file_mode import PidFileMode

from ..core.config import PID_FILE_PATH


class RecordPidFileMode(PidFileMode):
    """Record PID file mode: Use PID file + SIGUSR1 signal for stopping, save transcription to file."""

    def __init__(self, audio_service, text_inserter,
                 audio_feedback, transcriber, config):
        """Initialize record PID file mode."""
        super().__init__(audio_service, text_inserter,
                        audio_feedback, transcriber, config)
        self.pidfile = Path(PID_FILE_PATH)

    def _stop_recording(self):
        """Stop audio recording and process for record mode."""
        if not self.is_recording:
            return

        self.is_recording = False
        duration = time.time() - self.recording_start_time

        print(f"\nStopped (duration: {duration:.1f}s)")

        # Stop recording
        audio_file = self.audio_service.stop_recording()

        # Play finish beep immediately
        self.audio_feedback.play_finish_beep()

        # Close output stream now that we're done with audio
        self.audio_feedback.close_output_stream()

        # Check minimum duration (hardcoded to 0.5 seconds)
        if duration < 0.5:
            print(f"  ⚠ Recording too short (< 0.5s), ignoring")
            self._cleanup_audio_file(audio_file)
            return

        # Rename audio file if output path specified
        if audio_file and self.config.get('output_audio_path'):
            audio_file = self._rename_audio_file(audio_file)

        # Save transcription to file (or skip if no_transcribe)
        self._save_transcription_to_file(audio_file)

    def run(self):
        """Run record PID file mode recording."""
        print("\n" + "=" * 60)
        print("✓ Ready! Recording will start in 2 seconds")
        print("  Press Alt+R (toggle script) to stop recording")
        print("=" * 60)

        # Setup signal handlers
        self._setup_signal_handlers()
        signal.signal(signal.SIGUSR1, self._sigusr1_handler)

        try:
            print("\nStarting recording in 2 seconds...")
            print("Press Alt+R (toggle script) to stop recording")
            time.sleep(2)

            # Write PID file
            self.pidfile.write_text(str(os.getpid()))

            self._start_recording()

            # Wait for signal to stop
            while not self.stop_signal_received and not self.should_exit:
                time.sleep(0.1)

            # Stop recording and process
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