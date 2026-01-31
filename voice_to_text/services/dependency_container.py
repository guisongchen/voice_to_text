"""
Dependency injection container for voice-to-text service.
"""

from ..core.audio_service import AudioService
from ..core.audio_feedback import AudioFeedback
from ..core.text_inserter import TextInserter
from ..modes.pid_file_mode import PidFileMode
from ..modes.record_pid_file_mode import RecordPidFileMode

from ..transcribe import AudioTranscriber


class DependencyContainer:
    """Dependency injection container."""

    def __init__(self, config):
        """
        Initialize dependency container.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self._audio_service = None
        self._audio_feedback = None
        self._text_inserter = None
        self._transcriber = None

    @property
    def audio_service(self):
        """Get or create AudioService instance."""
        if self._audio_service is None:
            self._audio_service = AudioService()
        return self._audio_service

    @property
    def audio_feedback(self):
        """Get or create AudioFeedback instance."""
        if self._audio_feedback is None:
            self._audio_feedback = AudioFeedback()
        return self._audio_feedback


    @property
    def text_inserter(self):
        """Get or create TextInserter instance."""
        if self._text_inserter is None:
            self._text_inserter = TextInserter()
        return self._text_inserter

    @property
    def transcriber(self):
        """Get or create AudioTranscriber instance."""
        if self._transcriber is None:
            print(f"Loading Whisper model '{self.config.get('model_size', 'medium')}'...")
            print("(This may take 5-10 seconds on first run)")
            self._transcriber = AudioTranscriber(
                model_size=self.config.get('model_size', 'medium')
            )
            print("✓ Model loaded successfully!")
        return self._transcriber

    def create_mode(self):
        """
        Create the appropriate mode based on configuration.

        Returns:
            BaseMode instance (always PidFileMode)
        """
        # Always use PID file mode for voice-to-text
        return PidFileMode(
            self.audio_service,
            self.text_inserter,
            self.audio_feedback,
            self.transcriber,
            self.config
        )

    def create_record_mode(self):
        """
        Create record mode for saving transcription to file.

        Returns:
            BaseMode instance (RecordPidFileMode)
        """
        # Use RecordPidFileMode for record command
        return RecordPidFileMode(
            self.audio_service,
            self.text_inserter,
            self.audio_feedback,
            self.transcriber,
            self.config
        )

    def cleanup(self):
        """Clean up all resources."""
        if self._audio_service:
            self._audio_service.cleanup()
        if self._audio_feedback:
            self._audio_feedback.cleanup()
        if self._text_inserter:
            self._text_inserter.cleanup()