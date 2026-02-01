"""
Audio feedback for beep generation and playback.
Manages PyAudio output stream for PipeWire noise prevention.
"""

import numpy as np
import pyaudio
import time
import sys

from ..config import *


class AudioFeedback:
    """Audio feedback for beep generation and playback."""

    def __init__(self, sample_rate=SAMPLE_RATE):
        """
        Initialize audio feedback.

        Args:
            sample_rate: Audio sample rate in Hz
        """
        self.sample_rate = sample_rate
        self.pyaudio_instance = None
        self.output_stream = None  # Keep stream alive to prevent PipeWire noise
        
        # Cache stream format parameters for efficiency
        self._stream_params = {
            'format': pyaudio.paInt16,
            'channels': 1,
            'rate': self.sample_rate,
            'output': True
        }
        
        # Pre-generate beep tones to avoid runtime overhead
        self._start_beep = self._generate_beep_tone(
            frequency=START_BEEP_FREQ,
            duration=START_BEEP_DURATION,
            amplitude=START_BEEP_AMPLITUDE
        )
        self._finish_beep = self._generate_beep_tone(
            frequency=FINISH_BEEP_FREQ,
            duration=FINISH_BEEP_DURATION,
            amplitude=FINISH_BEEP_AMPLITUDE
        )
        
        # Pre-generate silence gap for double beep
        # Use active noise (dither) instead of pure zeros to prevent buffering/merging issues
        gap_duration = 0.08  # 80ms - balance between speed and clarity
        gap_samples = int(self.sample_rate * gap_duration)
        self._silence_gap = np.random.randint(-1, 2, gap_samples, dtype=np.int16)

    def _generate_beep_tone(self, frequency=880, duration=0.2, amplitude=0.5):
        """
        Generate a beep tone as numpy array.

        Args:
            frequency: Frequency in Hz (default 880 Hz = A5 note)
            duration: Duration in seconds (default 0.2s)

        Returns:
            numpy array of int16 audio samples
        """
        # Generate time array
        num_samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, num_samples, False)

        # Generate sine wave
        # Generate sine wave
        sine_wave = amplitude * np.sin(2 * np.pi * frequency * t)

        # Apply fade in/out to avoid clicks
        fade_samples = FADE_SAMPLES  # 10ms fade
        fade_in = np.linspace(0, 1, fade_samples)
        fade_out = np.linspace(1, 0, fade_samples)
        sine_wave[:fade_samples] *= fade_in
        sine_wave[-fade_samples:] *= fade_out

        # Convert to 16-bit PCM
        audio_data = (sine_wave * 32767).astype(np.int16)
        return audio_data

    def _ensure_pyaudio(self):
        """Ensure PyAudio instance is initialized."""
        if self.pyaudio_instance is None:
            try:
                self.pyaudio_instance = pyaudio.PyAudio()
            except Exception as e:
                print(f"\nError: Failed to initialize PyAudio: {e}", file=sys.stderr)
                raise
        return self.pyaudio_instance

    def _play_tone(self, audio_data):
        """
        Play audio tone using PyAudio.

        Args:
            audio_data: numpy array of int16 audio samples
        """
        try:
            self._ensure_pyaudio()

            # Use persistent stream if available, otherwise create temporary one
            if self.output_stream and self.output_stream.is_active():
                stream = self.output_stream
                close_after = False
            else:
                stream = self.pyaudio_instance.open(**self._stream_params)
                close_after = True

            # Play audio
            stream.write(audio_data.tobytes())

            # Only close if we created a temporary stream
            if close_after:
                stream.stop_stream()
                stream.close()

        except Exception as e:
            print(f"\nWarning: Could not play beep: {e}", file=sys.stderr)

    def open_output_stream(self):
        """
        Open and keep output stream active to prevent PipeWire noise.

        This keeps the audio output active during the recording session,
        preventing PipeWire from suspending/resuming the output stream
        which causes buzz/noise artifacts.
        """
        try:
            self._ensure_pyaudio()

            if self.output_stream is None or not self.output_stream.is_active():
                self.output_stream = self.pyaudio_instance.open(**self._stream_params)
                
                # Write "active silence" (low level noise) to force wake-up
                # Pure zeros can sometimes be ignored by aggressive power saving
                warmup_duration = 0.1  # 100ms - balance between speed and device wake-up
                num_samples = int(self.sample_rate * warmup_duration)
                # Random noise at lowest bit level (1/32767)
                warmup_signal = np.random.randint(-1, 2, num_samples, dtype=np.int16)
                self.output_stream.write(warmup_signal.tobytes())

        except Exception as e:
            print(f"\nWarning: Could not open output stream: {e}", file=sys.stderr)

    def close_output_stream(self):
        """Close the persistent output stream."""
        try:
            if self.output_stream:
                self.output_stream.stop_stream()
                self.output_stream.close()
                self.output_stream = None
        except Exception as e:
            print(f"\nWarning: Could not close output stream: {e}", file=sys.stderr)

    def play_start_beep(self):
        """Play audio feedback beep for recording start."""
        try:
            # Quick double beep for start using pre-generated tone
            # Use explicit silence buffer instead of sleep to ensure clean gap in stream
            
            # Pre-roll with active silence to ensure audio device is at full volume
            # This fixes the issue where the first beep is weaker than the second due to ramp-up
            self._play_tone(self._silence_gap)
            
            self._play_tone(self._start_beep)
            self._play_tone(self._silence_gap)
            self._play_tone(self._start_beep)
        except Exception as e:
            print(f"\nWarning: Beep failed: {e}", file=sys.stderr)

    def play_finish_beep(self):
        """Play audio feedback beep for recording finish."""
        try:
            # Single quick beep using pre-generated tone
            self._play_tone(self._finish_beep)
        except Exception as e:
            print(f"\nWarning: Beep failed: {e}", file=sys.stderr)

    def __enter__(self):
        """Context manager entry."""
        self.open_output_stream()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
        return False

    def cleanup(self):
        """Clean up resources."""
        self.close_output_stream()
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()
            self.pyaudio_instance = None