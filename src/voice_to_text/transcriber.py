import os
import threading
from pathlib import Path

import torch
from qwen_asr import Qwen3ASRModel

from .config import MODEL_LOCAL_PATH


class AudioTranscriber:
    """Qwen3-ASR model wrapper with async loading."""

    def __init__(self, model_name='qwen3-asr-0.6b'):
        self.model_name = model_name
        self._model = None
        self._ready = threading.Event()
        self._error = None

        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            if Path(MODEL_LOCAL_PATH).is_dir():
                model_id = MODEL_LOCAL_PATH
            else:
                model_id = "Qwen/Qwen3-ASR-0.6B"

            self._model = Qwen3ASRModel.from_pretrained(
                model_id,
                dtype=torch.bfloat16,
                device_map="cuda",
                max_inference_batch_size=1,
                max_new_tokens=256,
                local_files_only=True,
            )
        except Exception as e:
            self._error = e
        finally:
            self._ready.set()

    def wait_for_ready(self, timeout=120):
        if not self._ready.wait(timeout=timeout):
            raise RuntimeError(f"Model loading timed out after {timeout}s")
        if self._error:
            raise self._error
        return self._model

    ALLOWED_LANGUAGES = {"english", "chinese"}

    def transcribe(self, audio_path):
        model = self.wait_for_ready()

        results = model.transcribe(
            audio=str(audio_path),
            language=None,
        )

        detected = results[0].language.lower() if results[0].language else ""
        text = results[0].text.strip()

        # If model hallucinated a wrong language, force English as fallback
        if text and detected and detected not in self.ALLOWED_LANGUAGES:
            print(f"  ⚠ Unexpected language '{detected}', re-transcribing as English")
            results = model.transcribe(
                audio=str(audio_path),
                language="English",
            )
            text = results[0].text.strip()

        return text
