"""
Audio feedback for beep generation and playback.
Manages PyAudio output stream for PipeWire noise prevention.
"""

import numpy as np
import pyaudio
import time
import sys

from .config import *


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

    def _generate_beep_tone(self, frequency=880, duration=0.2):
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
        amplitude = BEEP_AMPLITUDE  # 30% volume to prevent clipping
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

    def _play_tone(self, audio_data):
        """
        Play audio tone using PyAudio.

        Args:
            audio_data: numpy array of int16 audio samples
        """
        try:
            if self.pyaudio_instance is None:
                self.pyaudio_instance = pyaudio.PyAudio()

            # Use persistent stream if available, otherwise create temporary one
            if self.output_stream and self.output_stream.is_active():
                stream = self.output_stream
                close_after = False
            else:
                stream = self.pyaudio_instance.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.sample_rate,
                    output=True
                )
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
            if self.pyaudio_instance is None:
                self.pyaudio_instance = pyaudio.PyAudio()

            if self.output_stream is None or not self.output_stream.is_active():
                self.output_stream = self.pyaudio_instance.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.sample_rate,
                    output=True
                )
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
            # Quick double beep for start
            beep = self._generate_beep_tone(frequency=START_BEEP_FREQ,
                                           duration=START_BEEP_DURATION)
            self._play_tone(beep)
            time.sleep(0.04)  # Short pause between beeps
            self._play_tone(beep)

        except Exception as e:
            print(f"\nWarning: Beep failed: {e}", file=sys.stderr)

    def play_finish_beep(self):
        """Play audio feedback beep for recording finish."""
        try:
            # Single quick beep for finish
            beep = self._generate_beep_tone(frequency=FINISH_BEEP_FREQ,
                                           duration=FINISH_BEEP_DURATION)
            self._play_tone(beep)

        except Exception as e:
            print(f"\nWarning: Beep failed: {e}", file=sys.stderr)

    def cleanup(self):
        """Clean up resources."""
        self.close_output_stream()
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()
            self.pyaudio_instance = None