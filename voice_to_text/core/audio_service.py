"""
Unified audio recording service with PipeWire noise prevention.
Combines AudioRecorder functionality with warm-up/cool-down chunks.
"""

import pyaudio
import wave
import tempfile
import threading
import queue
import time
from pathlib import Path

from .config import *


class AudioService:
    """Unified audio recording service with PipeWire noise prevention."""

    def __init__(self, sample_rate=SAMPLE_RATE, channels=CHANNELS,
                 chunk_size=CHUNK_SIZE):
        """
        Initialize audio service.

        Args:
            sample_rate: Audio sample rate in Hz
            channels: Number of audio channels (1=mono, 2=stereo)
            chunk_size: Size of audio chunks to read
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.format = pyaudio.paInt16

        # PyAudio instance
        self.audio = pyaudio.PyAudio()

        # Threading for non-blocking recording
        self.recording_thread = None
        self.audio_queue = queue.Queue()

        # State tracking
        self.is_recording = False
        self.current_audio_file = None
        self.stream = None

    def start_recording(self):
        """
        Start audio recording in a separate thread.

        Returns:
            Path to the temporary audio file that will be recorded to
        """
        if self.is_recording:
            return self.current_audio_file

        self.is_recording = True

        # Create temporary file for recording
        temp_fd, temp_path = tempfile.mkstemp(suffix='.wav', prefix='voice_to_text_')
        self.current_audio_file = temp_path

        # Start recording in background thread
        self.recording_thread = threading.Thread(
            target=self._record_audio_thread,
            args=(temp_path,),
            daemon=True
        )
        self.recording_thread.start()

        return temp_path

    def _record_audio_thread(self, output_path):
        """Background thread for audio recording with PipeWire noise prevention."""
        try:
            # Open audio INPUT stream (microphone)
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                stream_callback=None
            )

            # INPUT WARM-UP: Discard initial chunks to avoid mic activation noise
            # Minimal warm-up since output stream keep-alive prevents most issues
            for i in range(WARMUP_CHUNKS):
                if not self.is_recording:
                    break
                try:
                    self.stream.read(self.chunk_size, exception_on_overflow=False)
                except Exception:
                    pass

            frames = []

            # Now record the actual audio (system should be stable)
            while self.is_recording:
                try:
                    data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                    frames.append(data)
                except Exception as e:
                    print(f"  Recording error: {e}")
                    break

            # COOL-DOWN: Minimal cool-down since output stream stays active
            for _ in range(COOLDOWN_CHUNKS):
                try:
                    self.stream.read(self.chunk_size, exception_on_overflow=False)
                except Exception:
                    pass

            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

            # Save the recording
            if frames:
                self._save_wav(frames, output_path)
                self.audio_queue.put(('success', output_path))
            else:
                self.audio_queue.put(('error', 'No audio data recorded'))

        except Exception as e:
            self.audio_queue.put(('error', str(e)))

    def stop_recording(self):
        """
        Stop audio recording and wait for thread to finish.

        Returns:
            Path to the recorded audio file, or None if recording failed
        """
        if not self.is_recording:
            return None

        self.is_recording = False

        # Wait for recording thread to finish (includes cool-down)
        if self.recording_thread:
            self.recording_thread.join(timeout=RECORDING_THREAD_TIMEOUT)

        # Check if recording was successful
        try:
            status, data = self.audio_queue.get(timeout=QUEUE_TIMEOUT)
            if status == 'error':
                print(f"  ✗ Recording error: {data}")
                return None
            return data
        except queue.Empty:
            print("  ✗ Recording thread timed out")
            return None

    def _save_wav(self, frames, filename):
        """Save recorded frames to WAV file."""
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.audio.get_sample_size(self.format))
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(frames))

    def record(self, duration, output_file=None):
        """
        Record audio for specified duration (synchronous).

        Args:
            duration: Recording duration in seconds
            output_file: Output filename (optional)

        Returns:
            Path to the recorded audio file
        """
        if output_file is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"recording_{timestamp}.wav"

        print(f"Recording for {duration} seconds...")
        print(f"Output file: {output_file}")

        stream = self.audio.open(
            format=self.format,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )

        frames = []
        total_chunks = int(self.sample_rate / self.chunk_size * duration)

        try:
            for i in range(total_chunks):
                data = stream.read(self.chunk_size)
                frames.append(data)

                progress = (i + 1) / total_chunks * 100
                print(f"\rProgress: {progress:.1f}%", end='', flush=True)
        except KeyboardInterrupt:
            print("\n\nRecording stopped by user")
        finally:
            print("\n")
            stream.stop_stream()
            stream.close()

        self._save_wav(frames, output_file)
        print(f"Recording saved to: {output_file}")
        return output_file

    def list_devices(self):
        """List available audio input devices."""
        print("\nAvailable audio input devices:")
        print("-" * 60)
        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                print(f"Device {i}: {device_info['name']}")
                print(f"  Channels: {device_info['maxInputChannels']}")
                print(f"  Sample Rate: {int(device_info['defaultSampleRate'])} Hz")
                print()

    def cleanup(self):
        """Clean up resources."""
        self.is_recording = False

        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        if self.recording_thread:
            self.recording_thread.join(timeout=1.0)

        if self.audio:
            self.audio.terminate()
            self.audio = None