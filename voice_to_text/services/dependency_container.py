"""
Dependency injection container for voice-to-text service.
"""

import threading

from ..core.audio_service import AudioService
from ..core.audio_feedback import AudioFeedback
from ..core.text_inserter import TextInserter
from ..modes.socket_mode import SocketMode

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
        self._transcriber_loading = False

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
        """Get or create AudioTranscriber instance with async loading."""
        if self._transcriber is None and not self._transcriber_loading:
            self._transcriber_loading = True
            # Create transcriber with async loading enabled
            self._transcriber = AudioTranscriber(
                model_size=self.config.get('model_size', 'medium'),
                async_load=True
            )
        return self._transcriber

    def create_mode(self):
        """
        Create the appropriate mode based on configuration.

        Returns:
            BaseMode instance (uses SocketMode for safer IPC)
        """
        # Use SocketMode for safer IPC (Unix domain socket)
        return SocketMode(
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