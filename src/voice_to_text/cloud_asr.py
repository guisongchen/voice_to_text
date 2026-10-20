"""Cloud ASR client for voice_to_text: direct DashScope transcription.

Thin adapter over asr_core.cloud_transcriber.CloudTranscriber (the single
implementation of the DashScope call lives in asr_core) exposing the same
transcribe()/close() surface that VoiceToTextService uses from
ASRCoreClient. Selected when config.ASR_MODE == "cloud".
"""

import logging

from asr_core.cloud_transcriber import CloudTranscriber

logger = logging.getLogger(__name__)


class CloudASRClient:
    """Drop-in replacement for ASRCoreClient backed by DashScope cloud ASR."""

    def __init__(self, model_name: str = None):
        # model_name from voice_to_text refers to local Qwen3-ASR models;
        # the cloud model is configured in asr_core (CLOUD_MODEL_DEFAULT).
        self._transcriber = CloudTranscriber()
        self._transcriber.load()  # validates DASHSCOPE_API_KEY, no network
        logger.info("Using cloud ASR backend (model=%s)", self._transcriber.model_name)

    def transcribe(self, audio_path: str, model_name: str = None, language: str = None) -> dict:
        return self._transcriber.transcribe(audio_path, language=language)

    def close(self):
        self._transcriber.unload()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
