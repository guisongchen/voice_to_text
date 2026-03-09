#!/usr/bin/env python3
"""
Voice-to-Text Input Tool - Single-file simplified version.
Records audio and inserts transcribed text at cursor position.
"""

import argparse
import socket
import subprocess
import sys
import tempfile
import threading
import time
import warnings
import wave
from pathlib import Path

import numpy as np
import pyaudio
import torch
import whisper

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
MODEL_SIZE_DEFAULT = 'small'
MODEL_CHOICES = ['tiny', 'base', 'small', 'medium', 'large']

warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")


class AudioTranscriber:
    """Whisper model wrapper with async loading."""

    def __init__(self, model_size='small'):
        self.model_size = model_size
        self._model = None
        self._ready = threading.Event()
        self._error = None

        # Start loading in background
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            self._model = whisper.load_model(self.model_size, device="cuda")
        except Exception as e:
            self._error = e
        finally:
            self._ready.set()

    def wait_for_ready(self):
        self._ready.wait()
        if self._error:
            raise self._error
        return self._model

    def transcribe(self, audio_path):
        """Transcribe audio file to text."""
        model = self.wait_for_ready()
        result = model.transcribe(
            str(audio_path),
            verbose=False,
            language=None,
            task='transcribe',
            fp16=True,
            best_of=1,
            beam_size=1
        )
        text = result["text"].strip()

        # Retranscribe as English if not English/Chinese
        detected = result.get("language", "unknown")
        if detected not in ['en', 'zh']:
            result = model.transcribe(
                str(audio_path),
                verbose=False,
                language='en',
                task='transcribe',
                fp16=True,
                best_of=1,
                beam_size=1
            )
            text = result["text"].strip()

        return text


class AudioRecorder:
    """Records audio from microphone to WAV file."""

    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.is_recording = False
        self._thread = None
        self._stream = None
        self._frames = []
        self._output_path = None

    def start(self):
        """Start recording in background thread."""
        if self.is_recording:
            return self._output_path

        fd, self._output_path = tempfile.mkstemp(suffix='.wav', prefix='vtt_')
        self.is_recording = True
        self._frames = []
        self._thread = threading.Thread(target=self._record, daemon=True)
        self._thread.start()
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

            while self.is_recording:
                try:
                    data = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
                    self._frames.append(data)
                except Exception as e:
                    print(f"  Recording error: {e}")
                    break

            self._stream.stop_stream()
            self._stream.close()

            if self._frames:
                self._save_wav()

        except Exception as e:
            print(f"  Recording failed: {e}")

    def _save_wav(self):
        """Save frames to WAV file."""
        with wave.open(self._output_path, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b''.join(self._frames))

    def stop(self):
        """Stop recording and return path to audio file."""
        if not self.is_recording:
            return None

        self.is_recording = False
        if self._thread:
            self._thread.join(timeout=3.0)

        return self._output_path if Path(self._output_path).exists() else None

    def cleanup(self):
        """Clean up resources."""
        self.is_recording = False
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except:
                pass
        if self.audio:
            self.audio.terminate()


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
    def check_xdotool():
        """Check if xdotool is installed."""
        try:
            result = subprocess.run(['xdotool', 'version'],
                                    capture_output=True, timeout=2)
            return result.returncode == 0
        except:
            return False

    @staticmethod
    def insert(text):
        """Insert text at cursor position."""
        if not text or not text.strip():
            print("  (No text to insert)")
            return False

        try:
            subprocess.run(
                ['xdotool', 'type', '--clearmodifiers', '--', text],
                check=True,
                timeout=XDOTOOL_TIMEOUT
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
        self.should_exit = False
        self.stop_signal = False

        # Components
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
        print(f"\n[2/2] Loading Whisper model '{self.model_size}'...")
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
        signal.signal(signal.SIGINT, lambda s, f: setattr(self, 'should_exit', True))
        signal.signal(signal.SIGTERM, lambda s, f: setattr(self, 'should_exit', True))

        # Start socket listener
        listener_thread = threading.Thread(target=self._socket_listener, daemon=True)
        listener_thread.start()

        time.sleep(0.3)

        # Start recording
        self.beep.open_stream()
        self.beep.play_start()
        time.sleep(0.02)

        audio_file = self.recorder.start()
        start_time = time.time()
        print("\nRecording... ", end='', flush=True)

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
        """Transcribe audio and insert text."""
        if not audio_file or not Path(audio_file).exists():
            print("  ✗ Error: Audio file not found")
            return

        print("🔄 Transcribing...")

        try:
            text = self.transcriber.transcribe(audio_file)

            if not text:
                print("  ⚠ No speech detected")
                return

            preview = text[:80] + "..." if len(text) > 80 else text
            print(f"📝 Transcribed: \"{preview}\"")

            print("⌨️  Inserting text...")
            if TextInserter.insert(text):
                print("✓ Done!")
            else:
                print(f"  Text: {text}")

        except Exception as e:
            print(f"  ✗ Transcription error: {e}")
        finally:
            self._cleanup(audio_file)

    def _cleanup(self, audio_file):
        """Clean up audio file."""
        if audio_file and not self.keep_audio:
            try:
                Path(audio_file).unlink(missing_ok=True)
            except:
                pass
        elif audio_file:
            print(f"  Audio saved: {audio_file}")

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

Model sizes (speed vs accuracy):
  tiny, base, small (default), medium, large

Toggle Script:
  Run voice_to_text_toggle.py to start/stop recording via socket.
"""
    )

    parser.add_argument(
        '-m', '--model',
        type=str,
        default=MODEL_SIZE_DEFAULT,
        choices=MODEL_CHOICES,
        help=f'Whisper model size (default: {MODEL_SIZE_DEFAULT})'
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
