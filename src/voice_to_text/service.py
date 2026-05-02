import signal
import socket
import threading
import time
from pathlib import Path

from .audio import AudioRecorder, AudioPreprocessor, BeepPlayer
from .config import SOCKET_PATH
from .inserter import TextInserter
from .transcriber import AudioTranscriber


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

    def _init_components(self, model_size):
        self.recorder = AudioRecorder()
        self.beep = BeepPlayer()
        self.transcriber = AudioTranscriber(model_size)

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

        if self.keep_audio:
            print("\n" + "=" * 50)
            print("DIAGNOSTIC MODE: Audio files will be preserved")
            print("=" * 50)

        return True

    def _socket_listener(self):
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
        if not self.initialize():
            return 1

        print("\n" + "=" * 50)
        print("✓ Ready! Recording starts in 0.3 seconds")
        print("  Run toggle script again to stop")
        print("=" * 50)

        signal.signal(signal.SIGINT, lambda s, f: setattr(self, '_should_exit', True))
        signal.signal(signal.SIGTERM, lambda s, f: setattr(self, '_should_exit', True))

        listener_thread = threading.Thread(target=self._socket_listener, daemon=True)
        listener_thread.start()

        time.sleep(0.3)

        audio_file = self.recorder.start()
        self._active_window = TextInserter.get_active_window()
        start_time = time.time()
        print("\nRecording... ", end='', flush=True)

        time.sleep(0.02)
        self.beep.open_stream()
        self.beep.play_start()

        try:
            while not self.stop_signal and not self.should_exit:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopping...")

        self.recorder.stop()
        duration = time.time() - start_time
        print(f"\nStopped (duration: {duration:.1f}s)")

        self.beep.play_finish()
        self.beep.close_stream()

        if duration < 0.5:
            print("  ⚠ Recording too short, ignoring")
            self._cleanup(audio_file)
            return 0

        self._transcribe_and_insert(audio_file)
        return 0

    def _transcribe_and_insert(self, audio_file):
        if not audio_file or not Path(audio_file).exists():
            print("  ✗ Error: Audio file not found")
            return

        processed_file = None
        try:
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
