import shutil
import signal
import socket
import threading
import time
from pathlib import Path

from .config import SOCKET_PATH
from .inserter import TextInserter
from .recorder import AudioRecorder  # lightweight — no torch/numpy imports


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
        self.recorder = AudioRecorder()
        self._transcriber = None
        self._preprocessor = None
        self._model_error = None

        # Start model loading in background AFTER recorder is ready
        threading.Thread(target=self._load_model, daemon=True).start()

    @property
    def should_exit(self):
        with self._lock:
            return self._should_exit

    @should_exit.setter
    def should_exit(self, value):
        with self._lock:
            self._should_exit = value

    @property
    def stop_signal(self):
        with self._lock:
            return self._stop_signal

    @stop_signal.setter
    def stop_signal(self, value):
        with self._lock:
            self._stop_signal = value

    def _load_model(self):
        """Load heavy ML modules in background thread."""
        try:
            from .transcriber import AudioTranscriber
            self._transcriber = AudioTranscriber(self.model_size)
        except Exception as e:
            self._model_error = e

    def initialize(self):
        print("=" * 50)
        print("Voice-to-Text Input Tool")
        print("=" * 50)

        print("\n[1/2] Checking xdotool...")
        if not TextInserter.check_xdotool():
            print("✗ Error: xdotool not found!")
            print("  Install with: sudo apt install xdotool")
            return False
        print("✓ xdotool is available")

        print(f"\n[2/2] Loading Qwen3-ASR model '{self.model_size}'...")
        print("✓ Model loading in background")

        return True

    def _socket_listener(self):
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        if self.socket_path.exists():
            self.socket_path.unlink()

        self.server_socket.bind(str(self.socket_path))
        self.server_socket.listen(1)
        self.server_socket.settimeout(1.0)

        # Clear the starting sentinel — daemon is now listening
        Path("/tmp/voice_to_text.starting").unlink(missing_ok=True)

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
        if not self.initialize():
            return 1

        print("\n" + "=" * 50)
        print("✓ Ready — recording")
        print("  Run toggle script again to stop")
        print("=" * 50)

        signal.signal(signal.SIGINT, lambda s, f: setattr(self, '_should_exit', True))
        signal.signal(signal.SIGTERM, lambda s, f: setattr(self, '_should_exit', True))

        listener_thread = threading.Thread(target=self._socket_listener, daemon=True)
        listener_thread.start()

        audio_file = self.recorder.start()
        self._active_window = TextInserter.get_active_window()
        start_time = time.time()
        print("\nRecording... ", end='', flush=True)

        try:
            while not self.stop_signal and not self.should_exit:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopping...")

        self.recorder.stop()
        duration = time.time() - start_time
        print(f"\nStopped (duration: {duration:.1f}s)")

        if duration < 0.5:
            print("  ⚠ Recording too short, ignoring")
            self._cleanup(audio_file)
            return 0

        self._transcribe_and_insert(audio_file)
        return 0

    def _wait_for_model(self, timeout=120):
        """Wait for model loading to complete. Returns AudioTranscriber wrapper."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._transcriber is not None:
                self._transcriber.wait_for_ready(timeout=timeout)
                return self._transcriber
            if self._model_error:
                raise self._model_error
            time.sleep(0.5)
        raise RuntimeError(f"Model loading timed out after {timeout}s")

    def _transcribe_and_insert(self, audio_file):
        if not audio_file or not Path(audio_file).exists():
            print("  ✗ Error: Audio file not found")
            return

        processed_file = None
        text = None
        try:
            from .audio import AudioPreprocessor  # lazy heavy import

            print("🔄 Preprocessing audio...")
            processed_file = AudioPreprocessor.preprocess(audio_file)

            print("🔄 Transcribing...")
            model = self._wait_for_model()
            text = model.transcribe(processed_file)

            if not text:
                print("  ⚠ No speech detected")

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
            self._save_recording(audio_file, processed_file, text)
            self._cleanup(audio_file, processed_file)

    def _save_recording(self, audio_file, processed_file, text):
        """Save recording to ~/voice_recordings/ for future model training."""
        try:
            archive_dir = Path.home() / "voice_recordings"
            archive_dir.mkdir(exist_ok=True)

            ts = time.strftime("%Y%m%d_%H%M%S")
            raw_dest = archive_dir / f"vtt_{ts}_raw.wav"
            shutil.copy2(audio_file, raw_dest)

            if processed_file and Path(processed_file).exists():
                proc_dest = archive_dir / f"vtt_{ts}_processed.wav"
                shutil.copy2(processed_file, proc_dest)

            if text:
                txt_dest = archive_dir / f"vtt_{ts}.txt"
                txt_dest.write_text(text)

            print(f"  💾 Saved: {raw_dest.name}")
        except Exception as e:
            print(f"  Warning: Could not save recording: {e}")

    def _cleanup(self, audio_file, processed_file=None):
        if audio_file:
            try:
                Path(audio_file).unlink(missing_ok=True)
            except:
                pass
        if processed_file:
            try:
                Path(processed_file).unlink(missing_ok=True)
            except:
                pass

    def cleanup(self):
        self.should_exit = True
        self.recorder.cleanup()
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
        Path("/tmp/voice_to_text.starting").unlink(missing_ok=True)
