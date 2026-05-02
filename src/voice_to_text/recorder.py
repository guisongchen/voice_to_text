"""Audio recorder — zero ML imports, starts in ~50ms."""
import os
import tempfile
import threading
import wave
from pathlib import Path

import pyaudio

from .config import SAMPLE_RATE, CHANNELS, CHUNK_SIZE


class AudioRecorder:
    """Records audio from microphone to WAV file."""

    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self._lock = threading.Lock()
        self._is_recording = False
        self._thread = None
        self._stream = None
        self._frames = []
        self._output_path = None
        self._cleaned_up = False
        self._ready = threading.Event()
        self._start_error = None

    @property
    def is_recording(self):
        with self._lock:
            return self._is_recording

    def start(self):
        if self.is_recording:
            return self._output_path

        fd, self._output_path = tempfile.mkstemp(suffix='.wav', prefix='vtt_')
        os.close(fd)
        Path(self._output_path).unlink(missing_ok=True)
        with self._lock:
            self._is_recording = True
            self._frames = []
        self._ready.clear()
        self._start_error = None
        self._thread = threading.Thread(target=self._record, daemon=True)
        self._thread.start()

        if not self._ready.wait(timeout=2.0):
            with self._lock:
                self._is_recording = False
            raise RuntimeError("Timed out waiting for audio recorder to start")

        if self._start_error:
            with self._lock:
                self._is_recording = False
            if self._thread:
                self._thread.join(timeout=1.0)
            raise RuntimeError(f"Failed to start audio recorder: {self._start_error}")

        return self._output_path

    def _record(self):
        try:
            self._stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=CHANNELS,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE
            )
            first_chunk = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
            with self._lock:
                if self._is_recording:
                    self._frames.append(first_chunk)
            self._ready.set()

            while True:
                with self._lock:
                    if not self._is_recording:
                        break
                try:
                    data = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
                    with self._lock:
                        self._frames.append(data)
                except Exception as e:
                    print(f"  Recording error: {e}")
                    break

            self._stream.stop_stream()
            self._stream.close()

            if self._frames:
                self._save_wav()

        except Exception as e:
            self._start_error = e
            self._ready.set()
            print(f"  Recording failed: {e}")

    def _save_wav(self):
        with self._lock:
            frames_copy = b''.join(self._frames)
        with wave.open(self._output_path, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(frames_copy)

    def stop(self):
        if not self.is_recording:
            return None

        with self._lock:
            self._is_recording = False
        if self._thread:
            self._thread.join(timeout=3.0)

        return self._output_path if Path(self._output_path).exists() else None

    def cleanup(self):
        with self._lock:
            if self._cleaned_up:
                return
            self._cleaned_up = True
            self._is_recording = False

        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except:
                pass
        if self.audio:
            self.audio.terminate()
            self.audio = None
