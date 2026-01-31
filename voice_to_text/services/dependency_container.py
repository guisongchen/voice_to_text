"""
Dependency injection container for voice-to-text service.
"""

from ..core.audio_service import AudioService
from ..core.audio_feedback import AudioFeedback
from ..core.text_inserter import TextInserter
from ..modes.fixed_duration_mode import FixedDurationMode
from ..modes.pid_file_mode import PidFileMode

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
            BaseMode instance
        """
        use_pidfile = self.config.get('use_pidfile', False)
        duration = self.config.get('duration', None)

        if duration is not None:
            # Fixed duration mode
            return FixedDurationMode(
                self.audio_service,
                self.text_inserter,
                self.audio_feedback,
                self.transcriber,
                self.config
            )
        elif use_pidfile:
            # PID file mode
            return PidFileMode(
                self.audio_service,
                self.text_inserter,
                self.audio_feedback,
                self.transcriber,
                self.config
            )
        else:
            # Default: Fixed duration mode with default duration
            # Ensure duration is set in config
            config = self.config.copy()
            from ..core.config import DEFAULT_RECORDING_DURATION
            config['duration'] = DEFAULT_RECORDING_DURATION
            return FixedDurationMode(
                self.audio_service,
                self.text_inserter,
                self.audio_feedback,
                self.transcriber,
                config
            )

    def cleanup(self):
        """Clean up all resources."""
        if self._audio_service:
            self._audio_service.cleanup()
        if self._audio_feedback:
            self._audio_feedback.cleanup()
        if self._text_inserter:
            self._text_inserter.cleanup()