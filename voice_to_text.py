#!/usr/bin/env python3
"""
Voice-to-Text Input Tool - Single-file simplified version.
Records audio and inserts transcribed text at cursor position.
"""

import argparse
import glob
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import warnings
import wave
from pathlib import Path

# Force offline mode for all HuggingFace libraries — must be set
# BEFORE any HF-related imports to prevent network hang on unreachable hosts.
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_DATASETS_OFFLINE'] = '1'

import numpy as np
import pyaudio
import soundfile as sf
import torch
import torchaudio
from qwen_asr import Qwen3ASRModel

# Configuration
SAMPLE_RATE = 44100
CHANNELS = 2
CHUNK_SIZE = 1024
SOCKET_PATH = '/tmp/voice_to_text.sock'
START_BEEP_FREQ = 784
FINISH_BEEP_FREQ = 523
START_BEEP_DURATION = 0.24
FINISH_BEEP_DURATION = 0.12
XDOTOOL_TIMEOUT = 10
MODEL_SIZE_DEFAULT = 'qwen3-asr-0.6b'
MODEL_CHOICES = ['qwen3-asr-0.6b']

warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")


class AudioPreprocessor:
    """Audio preprocessing for better transcription accuracy."""

    @staticmethod
    def preprocess(audio_path):
        """
        Preprocess audio: convert to mono, resample to 16kHz, normalize volume.
        Returns path to processed audio file.
        """
        try:
            # Load audio using soundfile (more robust than torchaudio)
            data, sample_rate = sf.read(audio_path, dtype='float32')
            if data.ndim == 1:
                waveform = torch.from_numpy(data).unsqueeze(0)
            else:
                waveform = torch.from_numpy(data).t().contiguous()

            # Convert to mono if stereo
            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)

            # Resample to 16kHz (Qwen3-ASR's expected sample rate)
            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(
                    orig_freq=sample_rate, new_freq=16000
                )
                waveform = resampler(waveform)

            # Normalize volume (peak normalization to -1dB)
            peak = torch.max(torch.abs(waveform))
            if peak > 0:
                waveform = waveform / peak * 0.891  # -1dB = 10^(-1/20)

            # Apply mild noise reduction using spectral gating
            waveform = AudioPreprocessor._reduce_noise(waveform)

            # Save processed audio
            processed_path = audio_path.replace('.wav', '_processed.wav')
            sf.write(processed_path, waveform.squeeze().numpy(), 16000)

            return processed_path

        except Exception as e:
            print(f"  Warning: Audio preprocessing failed ({e}), using original")
            return audio_path

    @staticmethod
    def _reduce_noise(waveform, n_fft=2048, hop_length=512, noise_reduction=0.7):
        """Simple spectral gating noise reduction."""
        try:
            # Convert to numpy for processing
            audio_np = waveform.squeeze().numpy()

            # Compute STFT
            stft = torch.stft(
                waveform.squeeze(),
                n_fft=n_fft,
                hop_length=hop_length,
                return_complex=True
            )

            # Estimate noise floor from quietest segments
            # Don't assume leading silence — user may start speaking immediately
            window_size = int(0.05 * 16000)  # 50ms windows
            hop_size = window_size // 2
            num_windows = max(1, (len(audio_np) - window_size) // hop_size + 1)

            energies = np.array([
                np.sum(audio_np[i * hop_size:i * hop_size + window_size] ** 2)
                for i in range(num_windows)
            ])

            # Use quietest 10% of windows for noise estimation
            quietest_count = max(1, num_windows // 10)
            quietest_indices = np.argsort(energies)[:quietest_count]

            cols_per_window = window_size // hop_length
            hop_cols = hop_size // hop_length
            noise_cols = []
            for idx in quietest_indices:
                start = idx * hop_cols
                end = start + cols_per_window
                noise_cols.extend(range(start, min(end, stft.shape[1])))

            if noise_cols:
                noise_floor = torch.mean(torch.abs(stft[:, noise_cols]), dim=1, keepdim=True)
            else:
                # Fallback: median across all time frames
                noise_floor = torch.median(torch.abs(stft), dim=1, keepdim=True)[0]

            # Spectral gating: attenuate frequencies below noise floor
            magnitude = torch.abs(stft)
            phase = torch.angle(stft)

            # Soft mask based on signal-to-noise ratio
            mask = torch.clamp((magnitude - noise_reduction * noise_floor) / (magnitude + 1e-10), 0, 1)
            mask = mask ** 0.5  # Soften the mask

            # Apply mask and reconstruct
            cleaned_magnitude = magnitude * mask
            cleaned_stft = cleaned_magnitude * torch.exp(1j * phase)

            # Inverse STFT
            cleaned = torch.istft(
                cleaned_stft,
                n_fft=n_fft,
                hop_length=hop_length,
                length=len(audio_np)
            )

            return cleaned.unsqueeze(0)

        except Exception:
            # If noise reduction fails, return original
            return waveform


class AudioTranscriber:
    """Qwen3-ASR model wrapper with async loading."""

    # Local model directory — copy from HF cache with:
    #   cp -rL ~/.cache/huggingface/hub/models--Qwen--Qwen3-ASR-0.6B/snapshots/<hash>/* models/qwen3-asr-0.6b/
    MODEL_PATH = str(Path(__file__).parent / "models" / "qwen3-asr-0.6b")

    def __init__(self, model_name='qwen3-asr-0.6b'):
        self.model_name = model_name
        self._model = None
        self._ready = threading.Event()
        self._error = None

        # Start loading in background
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            if Path(self.MODEL_PATH).is_dir():
                model_id = self.MODEL_PATH
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
            raise RuntimeError(
                f"Model loading timed out after {timeout}s"
            )
        if self._error:
            raise self._error
        return self._model

    def transcribe(self, audio_path):
        """Transcribe audio file to text."""
        model = self.wait_for_ready()

        results = model.transcribe(
            audio=str(audio_path),
            language=None,  # Auto-detect
        )

        return results[0].text.strip()


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
        """Thread-safe access to recording state."""
        with self._lock:
            return self._is_recording

    def _set_recording(self, value):
        """Thread-safe modification of recording state."""
        with self._lock:
            self._is_recording = value

    def start(self):
        """Start recording in background thread."""
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
        """Recording thread."""
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
        """Save frames to WAV file."""
        with self._lock:
            frames_copy = b''.join(self._frames)
        with wave.open(self._output_path, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(frames_copy)

    def stop(self):
        """Stop recording and return path to audio file."""
        if not self.is_recording:
            return None

        with self._lock:
            self._is_recording = False
        if self._thread:
            self._thread.join(timeout=3.0)

        return self._output_path if Path(self._output_path).exists() else None

    def cleanup(self):
        """Clean up resources."""
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


class BeepPlayer:
    """Plays start/finish beep sounds."""

    def __init__(self):
        self.sample_rate = SAMPLE_RATE
        self.audio = None
        self.output_stream = None
        self._start_beep = self._generate(START_BEEP_FREQ, START_BEEP_DURATION)
        self._finish_beep = self._generate(FINISH_BEEP_FREQ, FINISH_BEEP_DURATION)
        gap_samples = int(SAMPLE_RATE * 0.08)
        self._gap = np.random.randint(-1, 2, gap_samples, dtype=np.int16)

    def _generate(self, freq, duration):
        """Generate a beep tone."""
        samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, samples, False)
        wave = np.sin(2 * np.pi * freq * t)

        # Fade in/out
        fade = int(SAMPLE_RATE * 0.01)
        wave[:fade] *= np.linspace(0, 1, fade)
        wave[-fade:] *= np.linspace(1, 0, fade)

        return (wave * 32767).astype(np.int16)

    def _ensure_audio(self):
        if self.audio is None:
            self.audio = pyaudio.PyAudio()
        return self.audio

    def open_stream(self):
        """Open output stream to prevent PipeWire noise."""
        try:
            self._ensure_audio()
            self.output_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                output=True
            )
            # Wake-up signal
            warmup = np.random.randint(-1, 2, int(self.sample_rate * 0.1), dtype=np.int16)
            self.output_stream.write(warmup.tobytes())
        except Exception as e:
            print(f"Warning: Could not open audio output: {e}")

    def close_stream(self):
        """Close output stream."""
        if self.output_stream:
            try:
                self.output_stream.stop_stream()
                self.output_stream.close()
            except:
                pass
            self.output_stream = None

    def play_start(self):
        """Play start beep (double beep)."""
        try:
            self._play(self._gap)
            self._play(self._start_beep)
            self._play(self._gap)
            self._play(self._start_beep)
        except:
            pass

    def play_finish(self):
        """Play finish beep (single beep)."""
        try:
            self._play(self._finish_beep)
        except:
            pass

    def _play(self, data):
        """Play audio data."""
        self._ensure_audio()
        if self.output_stream and self.output_stream.is_active():
            stream = self.output_stream
            close_after = False
        else:
            stream = self.audio.open(format=pyaudio.paInt16, channels=1,
                                     rate=self.sample_rate, output=True)
            close_after = True

        stream.write(data.tobytes())

        if close_after:
            stream.stop_stream()
            stream.close()

    def cleanup(self):
        """Clean up resources."""
        self.close_stream()
        if self.audio:
            self.audio.terminate()
            self.audio = None


class TextInserter:
    """Insert text using xdotool."""

    @staticmethod
    def _get_x11_env():
        """Discover X11 environment (DISPLAY, XAUTHORITY) for xdotool."""
        env = os.environ.copy()

        if "DISPLAY" not in env:
            env["DISPLAY"] = ":1"

        if "XAUTHORITY" not in env:
            uid = os.getuid()
            home = os.path.expanduser("~")
            candidates = [
                f"/run/user/{uid}/gdm/Xauthority",
                f"/run/user/{uid}/.mutter-Xwaylandauth.*",
                os.path.join(home, ".Xauthority"),
            ]
            for pattern in candidates:
                paths = glob.glob(pattern) if "*" in pattern else [pattern]
                for path in paths:
                    if os.path.exists(path):
                        env["XAUTHORITY"] = path
                        break
                if "XAUTHORITY" in env:
                    break

        return env

    @staticmethod
    def check_xdotool():
        """Check if xdotool is installed."""
        try:
            result = subprocess.run(
                ['xdotool', 'version'],
                capture_output=True, timeout=2,
                env=TextInserter._get_x11_env()
            )
            return result.returncode == 0
        except:
            return False

    @staticmethod
    def get_active_window():
        """Get the ID of the currently focused window."""
        try:
            result = subprocess.run(
                ['xdotool', 'getactivewindow'],
                capture_output=True, text=True, timeout=2,
                env=TextInserter._get_x11_env()
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    @staticmethod
    def insert(text, window_id=None):
        """Insert text at cursor position, optionally restoring window focus."""
        if not text or not text.strip():
            print("  (No text to insert)")
            return False

        env = TextInserter._get_x11_env()

        try:
            if window_id:
                subprocess.run(
                    ['xdotool', 'windowfocus', window_id],
                    env=env, timeout=2, check=False
                )
                time.sleep(0.05)

            subprocess.run(
                ['xdotool', 'type', '--clearmodifiers', '--', text],
                check=True,
                timeout=XDOTOOL_TIMEOUT,
                env=env
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"  ✗ Error inserting text: {e}")
            return False
        except subprocess.TimeoutExpired:
            print("  ✗ Error: xdotool timed out")
            return False


class VoiceToTextService:
    """Main voice-to-text service using socket-based IPC."""

    def __init__(self, model_size='small', keep_audio=False):
        self.model_size = model_size
        self.keep_audio = keep_audio
        self.socket_path = Path(SOCKET_PATH)
        self.server_socket = None
        self._lock = threading.Lock()
        self._should_exit = False
        self._stop_signal = False
        self._active_window = None
        self._init_components(model_size)

    @property
    def should_exit(self):
        """Thread-safe access to should_exit flag."""
        with self._lock:
            return self._should_exit

    @should_exit.setter
    def should_exit(self, value):
        """Thread-safe modification of should_exit flag."""
        with self._lock:
            self._should_exit = value

    @property
    def stop_signal(self):
        """Thread-safe access to stop_signal flag."""
        with self._lock:
            return self._stop_signal

    @stop_signal.setter
    def stop_signal(self, value):
        """Thread-safe modification of stop_signal flag."""
        with self._lock:
            self._stop_signal = value

    def _init_components(self, model_size):
        """Initialize components - called from __init__."""
        self.recorder = AudioRecorder()
        self.beep = BeepPlayer()
        self.transcriber = AudioTranscriber(model_size)

    def initialize(self):
        """Initialize and check dependencies."""
        print("=" * 50)
        print("Voice-to-Text Input Tool")
        print("=" * 50)

        # Check xdotool
        print("\n[1/2] Checking xdotool...")
        if not TextInserter.check_xdotool():
            print("✗ Error: xdotool not found!")
            print("  Install with: sudo apt install xdotool")
            return False
        print("✓ xdotool is available")

        # Start model loading
        print(f"\n[2/2] Loading Qwen3-ASR model '{self.model_size}'...")
        print("✓ Model loading in background")

        if self.keep_audio:
            print("\n" + "=" * 50)
            print("DIAGNOSTIC MODE: Audio files will be preserved")
            print("=" * 50)

        return True

    def _socket_listener(self):
        """Listen for stop commands on Unix socket."""
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        if self.socket_path.exists():
            self.socket_path.unlink()

        self.server_socket.bind(str(self.socket_path))
        self.server_socket.listen(1)
        self.server_socket.settimeout(1.0)

        while not self.should_exit:
            try:
                conn, _ = self.server_socket.accept()
                command = conn.recv(1024).decode('utf-8').strip()
                if command == 'STOP':
                    print("\n⏹️  Stop command received")
                    self.stop_signal = True
                conn.sendall(b'ACK\n')
                conn.close()
            except socket.timeout:
                continue
            except:
                break

    def run(self):
        """Main entry point."""
        if not self.initialize():
            return 1

        print("\n" + "=" * 50)
        print("✓ Ready! Recording starts in 0.3 seconds")
        print("  Run toggle script again to stop")
        print("=" * 50)

        # Setup signal handlers
        import signal
        def _signal_handler(signum, frame):
            self._should_exit = True
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        # Start socket listener
        listener_thread = threading.Thread(target=self._socket_listener, daemon=True)
        listener_thread.start()

        time.sleep(0.3)

        # Start recording BEFORE playing beep, so speech during/after beep is captured
        audio_file = self.recorder.start()
        self._active_window = TextInserter.get_active_window()
        start_time = time.time()
        print("\nRecording... ", end='', flush=True)

        time.sleep(0.02)
        self.beep.open_stream()
        self.beep.play_start()

        # Wait for stop signal
        try:
            while not self.stop_signal and not self.should_exit:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopping...")

        # Stop recording
        self.recorder.stop()
        duration = time.time() - start_time
        print(f"\nStopped (duration: {duration:.1f}s)")

        self.beep.play_finish()
        self.beep.close_stream()

        # Process if long enough
        if duration < 0.5:
            print("  ⚠ Recording too short, ignoring")
            self._cleanup(audio_file)
            return 0

        self._transcribe_and_insert(audio_file)
        return 0

    def _transcribe_and_insert(self, audio_file):
        """Transcribe audio and insert text with preprocessing."""
        if not audio_file or not Path(audio_file).exists():
            print("  ✗ Error: Audio file not found")
            return

        processed_file = None
        try:
            # Preprocess audio for better accuracy
            print("🔄 Preprocessing audio...")
            processed_file = AudioPreprocessor.preprocess(audio_file)

            print("🔄 Transcribing...")
            text = self.transcriber.transcribe(processed_file)

            if not text:
                print("  ⚠ No speech detected")
                self._cleanup(audio_file, processed_file)
                return

            preview = text[:80] + "..." if len(text) > 80 else text
            print(f"📝 Transcribed: \"{preview}\"")

            print("⌨️  Inserting text...")
            if TextInserter.insert(text, window_id=self._active_window):
                print("✓ Done!")
            else:
                print(f"  Text: {text}")

        except Exception as e:
            print(f"  ✗ Transcription error: {e}")
        finally:
            self._cleanup(audio_file, processed_file)

    def _cleanup(self, audio_file, processed_file=None):
        """Clean up audio files."""
        if audio_file and not self.keep_audio:
            try:
                Path(audio_file).unlink(missing_ok=True)
            except:
                pass
        elif audio_file:
            print(f"  Audio saved: {audio_file}")

        if processed_file and not self.keep_audio:
            try:
                Path(processed_file).unlink(missing_ok=True)
            except:
                pass

    def cleanup(self):
        """Clean up all resources."""
        self.should_exit = True
        self.recorder.cleanup()
        self.beep.cleanup()
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except:
                pass


def main():
    parser = argparse.ArgumentParser(
        description="Voice-to-Text Input Tool - Record and transcribe speech",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Usage:
  voice-to-text                    # Start recording
  voice-to-text --model small      # Use faster model
  voice-to-text --keep-audio       # Keep audio files

Available model:
  qwen3-asr-0.6b (default)

Toggle Script:
  Run voice_to_text_toggle.py to start/stop recording via socket.
"""
    )

    parser.add_argument(
        '-m', '--model',
        type=str,
        default=MODEL_SIZE_DEFAULT,
        choices=MODEL_CHOICES,
        help=f'ASR model to use (default: {MODEL_SIZE_DEFAULT})'
    )
    parser.add_argument(
        '--keep-audio',
        action='store_true',
        help='Keep audio files for debugging'
    )

    args = parser.parse_args()

    service = VoiceToTextService(
        model_size=args.model,
        keep_audio=args.keep_audio
    )

    try:
        return service.run()
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        return 1
    finally:
        service.cleanup()


if __name__ == "__main__":
    sys.exit(main())
