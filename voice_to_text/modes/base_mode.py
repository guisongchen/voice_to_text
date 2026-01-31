"""
Abstract base class for all operation modes.
"""

from abc import ABC, abstractmethod
import signal
import time
from pathlib import Path


class BaseMode(ABC):
    """Abstract base class for all operation modes."""

    def __init__(self, audio_service, text_inserter,
                 audio_feedback, transcriber, config):
        """
        Initialize the mode with required components.

        Args:
            audio_service: AudioService instance for recording
            text_inserter: TextInserter instance for text insertion
            audio_feedback: AudioFeedback instance for beep generation
            transcriber: AudioTranscriber instance for transcription
            config: Configuration dictionary
        """
        self.audio_service = audio_service
        self.text_inserter = text_inserter
        self.audio_feedback = audio_feedback
        self.transcriber = transcriber
        self.config = config

        # State tracking
        self.is_recording = False
        self.recording_start_time = None
        self.current_audio_file = None
        self.should_exit = False

        # Signal handling
        self.stop_signal_received = False

    @abstractmethod
    def run(self):
        """Run the mode's main logic."""
        pass

    @abstractmethod
    def start(self):
        """Start the mode."""
        pass

    @abstractmethod
    def stop(self):
        """Stop the mode."""
        pass

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle interrupt signals for graceful shutdown."""
        print("\n\n⏹️  Shutting down...")
        self.should_exit = True
        if self.is_recording:
            self.is_recording = False

    def _sigusr1_handler(self, signum, frame):
        """Handle SIGUSR1 signal to stop recording."""
        self.stop_signal_received = True

    def _start_recording(self):
        """Start audio recording."""
        if self.is_recording:
            return

        # Open output stream FIRST to keep PipeWire active (prevents noise)
        self.audio_feedback.open_output_stream()

        # Play start beep
        self.audio_feedback.play_start_beep()
        # Minimal delay - just let beep finish playing
        time.sleep(0.05)

        self.is_recording = True
        self.recording_start_time = time.time()

        # Start recording
        self.current_audio_file = self.audio_service.start_recording()

        print("\nRecording... ", end='', flush=True)

    def _stop_recording(self):
        """Stop audio recording and process."""
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
            self._cleanup_audio_file()
            return

        # Transcribe and insert
        self._transcribe_and_insert(audio_file)

    def _transcribe_and_insert(self, audio_file):
        """Transcribe the recorded audio and insert the text."""
        if not audio_file or not Path(audio_file).exists():
            print("  ✗ Error: Audio file not found")
            return

        print("🔄 Transcribing...")

        try:
            # Transcribe using pre-loaded model
            # Auto-detect language - Whisper will choose based on audio
            result = self.transcriber.model.transcribe(
                audio_file,
                verbose=False,
                language=None,  # Auto-detect language
                task='transcribe'  # Transcribe in original language(s)
            )
            text = result["text"].strip()

            if not text:
                print("  ⚠ No speech detected")
                self._cleanup_audio_file(audio_file)
                return

            # Show preview of transcription
            preview = text[:80] + "..." if len(text) > 80 else text
            print(f"📝 Transcribed: \"{preview}\"")

            # Insert text at cursor
            print("⌨️  Inserting text...")
            if self.text_inserter.insert_text(text):
                print("✓ Done!")
            else:
                print("  You can manually copy/paste this text:")
                print(f"  {text}")

        except Exception as e:
            print(f"  ✗ Transcription error: {e}")
        finally:
            self._cleanup_audio_file(audio_file)

    def _cleanup_audio_file(self, audio_file):
        """Clean up temporary audio file."""
        if audio_file and not self.config.get('keep_audio', False):
            try:
                Path(audio_file).unlink(missing_ok=True)
            except Exception:
                pass
        elif audio_file and self.config.get('keep_audio', False):
            print(f"  Audio saved: {audio_file}")

        self.current_audio_file = None

    def cleanup(self):
        """Clean up resources."""
        self.audio_feedback.cleanup()
        self.audio_service.cleanup()