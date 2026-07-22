import os
import shutil
import signal
import socket
import subprocess
import threading
import time
import traceback
from pathlib import Path

from asr_core.client import ASRCoreClient

from .audio_control import AudioOutputController
from .config import (
    IDLE_CHECK_INTERVAL,
    IDLE_TIMEOUT_SECONDS,
    MIN_RECORDING_DURATION,
    MIN_TRANSITION_INTERVAL,
    SAVE_RECORDINGS,
    SHUTDOWN_TRANSCRIBE_GRACE,
    SOCKET_PATH,
    MUTE_SPEAKERS_DURING_RECORDING,
)
from .inserter import TextInserter
from .recorder import AudioRecorder  # lightweight — no torch/numpy imports

BEEP_START = Path(__file__).parent.parent.parent / "scripts" / "beep_start.wav"
BEEP_FINISH = Path(__file__).parent.parent.parent / "scripts" / "beep_finish.wav"

STATE_IDLE = 'idle'
STATE_RECORDING = 'recording'
STATE_TRANSCRIBING = 'transcribing'


def _play_beep(wav_path):
    """Play a WAV file through aplay and wait for it to finish."""
    try:
        subprocess.run(
            ["aplay", "-q", str(wav_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        pass


class VoiceToTextService:
    """Persistent voice-to-text daemon with idle timeout."""

    def __init__(self, model_size=None, keep_audio=False):
        self.model_size = model_size
        self.keep_audio = keep_audio
        self.socket_path = Path(SOCKET_PATH)
        self.server_socket = None
        self._lock = threading.Lock()
        self._should_exit = False

        # State machine
        self._state = STATE_IDLE
        self._last_activity = time.monotonic()
        self._last_transition = 0.0  # 0 so first transition isn't blocked
        self._current_audio_file = None
        self._recording_start_time = None
        self._transcribe_thread = None

        self.recorder = AudioRecorder()
        self._asr_client = ASRCoreClient(auto_start=True)
        self._audio_controller = AudioOutputController()
        self._mute_speakers = MUTE_SPEAKERS_DURING_RECORDING

    @property
    def should_exit(self):
        with self._lock:
            return self._should_exit

    @should_exit.setter
    def should_exit(self, value):
        with self._lock:
            self._should_exit = value

    def _request_shutdown(self, signum=None, frame=None):
        """Signal-safe shutdown request (used as signal handler)."""
        self.should_exit = True

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

        print("\n[2/2] ASRCore client ready (model loaded on first use)")

        return True

    # ---------- State machine ----------

    def _try_transition(self, from_state, to_state):
        """Atomic CAS state transition. Returns True if transitioned.

        Rejects if (a) state doesn't match from_state, or (b) less than
        MIN_TRANSITION_INTERVAL has passed since the previous transition
        (hardware-bounce guard).
        """
        with self._lock:
            if self._state != from_state:
                return False
            now = time.monotonic()
            if now - self._last_transition < MIN_TRANSITION_INTERVAL:
                return False
            self._state = to_state
            self._last_activity = now
            self._last_transition = now
            return True

    def _force_transition(self, to_state):
        """Unconditional transition (transcribe completion or error rollback)."""
        with self._lock:
            self._state = to_state
            self._last_activity = time.monotonic()

    def _handle_toggle(self):
        """Returns 'STARTED' / 'STOPPED' / 'BUSY' and dispatches I/O work."""
        if self._try_transition(STATE_IDLE, STATE_RECORDING):
            threading.Thread(target=self._begin_recording, daemon=True).start()
            return 'STARTED'
        if self._try_transition(STATE_RECORDING, STATE_TRANSCRIBING):
            threading.Thread(target=self._begin_stop_action, daemon=True).start()
            return 'STOPPED'
        return 'BUSY'

    def _begin_recording(self):
        """Worker thread: open mic, play start beep, then mute speakers. Roll back to IDLE on failure.

        Note: if the user presses toggle again during the beep (~240ms), the
        state transitions to TRANSCRIBING and _begin_stop_action runs
        concurrently.  The recorder's internal lock serialises start/stop,
        and the still_recording check below prevents speaker muting after
        the state has already moved on.
        """
        try:
            audio_file = self.recorder.start()
            with self._lock:
                self._current_audio_file = audio_file
                self._recording_start_time = time.time()
            _play_beep(BEEP_START)
            with self._lock:
                still_recording = self._state == STATE_RECORDING
            if still_recording:
                if self._mute_speakers:
                    if self._audio_controller.save_and_mute():
                        print("  🔇 Speakers muted")
                print(f"\n🎤 Recording... (file: {audio_file})")
        except Exception as e:
            print(f"  ✗ Failed to start audio recorder: {e}")
            self._force_transition(STATE_IDLE)

    def _begin_stop_action(self):
        """Worker thread: close mic, restore speakers, play beep, dispatch transcription."""
        with self._lock:
            audio_file = self._current_audio_file
            start_time = self._recording_start_time
        try:
            self.recorder.stop()
        except Exception as e:
            print(f"  ✗ Error stopping recorder: {e}")

        if self._mute_speakers:
            if self._audio_controller.restore():
                print("  🔊 Speakers restored")

        duration = time.time() - start_time if start_time else 0
        _play_beep(BEEP_FINISH)
        print(f"\n⏹  Stopped (duration: {duration:.1f}s)")

        if duration < MIN_RECORDING_DURATION:
            print("  ⚠ Recording too short, ignoring")
            self._cleanup(audio_file)
            with self._lock:
                self._current_audio_file = None
                self._recording_start_time = None
            self._force_transition(STATE_IDLE)
            return

        t = threading.Thread(
            target=self._run_transcription, args=(audio_file,), daemon=True
        )
        with self._lock:
            self._transcribe_thread = t
        t.start()

    def _run_transcription(self, audio_file):
        try:
            self._transcribe_and_insert(audio_file)
        except Exception as e:
            print(f"  ✗ Transcription thread error: {e}")
        finally:
            with self._lock:
                self._current_audio_file = None
                self._recording_start_time = None
                self._transcribe_thread = None
            self._force_transition(STATE_IDLE)

    def _idle_timer_loop(self):
        """Daemon thread: exit the daemon after IDLE_TIMEOUT_SECONDS in IDLE."""
        while not self.should_exit:
            time.sleep(IDLE_CHECK_INTERVAL)
            if self.should_exit:
                return
            with self._lock:
                if self._state != STATE_IDLE:
                    continue
                idle_for = time.monotonic() - self._last_activity
            if idle_for > IDLE_TIMEOUT_SECONDS:
                print(f"\n💤 Idle for {idle_for:.0f}s, exiting daemon")
                self.should_exit = True
                return

    def _graceful_shutdown(self):
        """Salvage in-flight transcription; drop in-flight recording; restore speakers."""
        with self._lock:
            state = self._state
            transcribe_thread = self._transcribe_thread
        if state == STATE_RECORDING:
            print("Daemon exiting mid-recording, dropping audio")
            try:
                self.recorder.stop()
            except Exception:
                pass
        elif state == STATE_TRANSCRIBING and transcribe_thread is not None:
            print(f"Daemon exiting, waiting up to {SHUTDOWN_TRANSCRIBE_GRACE}s for transcription")
            transcribe_thread.join(timeout=SHUTDOWN_TRANSCRIBE_GRACE)

        # Always attempt to restore speakers on shutdown.
        try:
            self._audio_controller.restore()
        except Exception:
            pass

    # ---------- Socket listener ----------

    def _socket_listener(self):
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        if self.socket_path.exists():
            self.socket_path.unlink()

        self.server_socket.bind(str(self.socket_path))
        # Restrict socket to owner only (single-user desktop tool).
        os.chmod(str(self.socket_path), 0o600)
        self.server_socket.listen(1)
        self.server_socket.settimeout(1.0)

        while not self.should_exit:
            try:
                conn, _ = self.server_socket.accept()
            except socket.timeout:
                continue
            except OSError as e:
                if self.should_exit:
                    break
                print(f"  ✗ Socket listener error: {e}")
                traceback.print_exc()
                break

            try:
                command = conn.recv(1024).decode('utf-8').strip()
                if command == 'TOGGLE':
                    response = self._handle_toggle()
                else:
                    response = f'ERROR unknown command: {command}'
                conn.sendall((response + '\n').encode('utf-8'))
            except Exception as e:
                print(f"  ✗ Error handling socket command: {e}")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

    # ---------- run / lifecycle ----------

    def run(self, start_recording=False):
        if not self.initialize():
            return 1

        signal.signal(signal.SIGINT, self._request_shutdown)
        signal.signal(signal.SIGTERM, self._request_shutdown)

        threading.Thread(target=self._socket_listener, daemon=True).start()

        # Wait for the listener to bind the socket before clearing the spawn sentinel
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if self.socket_path.exists():
                break
            time.sleep(0.05)

        Path("/tmp/voice_to_text.starting").unlink(missing_ok=True)

        threading.Thread(target=self._idle_timer_loop, daemon=True).start()

        if start_recording:
            result = self._handle_toggle()
            if result != 'STARTED':
                print(f"  ⚠ Cold-start recording skipped: {result}")

        print("\n" + "=" * 50)
        print("✓ Daemon ready")
        print(f"  Idle timeout: {IDLE_TIMEOUT_SECONDS}s")
        print("=" * 50)

        try:
            while not self.should_exit:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n\n⏹  Stopping...")

        self._graceful_shutdown()
        return 0

    # ---------- Transcription / cleanup ----------

    def _transcribe_and_insert(self, audio_file):
        if not audio_file or not Path(audio_file).exists():
            print("  ✗ Error: Audio file not found")
            return

        text = None
        try:
            print("🔄 Transcribing via ASRCore...")
            result = self._asr_client.transcribe(audio_file, model_name=self.model_size)
            text = result.get("text", "").strip()

            if not text:
                print("  ⚠ No speech detected")

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
            self._save_recording(audio_file, text)
            self._cleanup(audio_file)

    def _save_recording(self, audio_file, text):
        """Save recording to ~/voice_recordings/ for future model training."""
        if not SAVE_RECORDINGS:
            return
        try:
            archive_dir = Path.home() / "voice_recordings"
            archive_dir.mkdir(exist_ok=True)

            ts = time.strftime("%Y%m%d_%H%M%S")
            raw_dest = archive_dir / f"vtt_{ts}_raw.wav"
            shutil.copy2(audio_file, raw_dest)

            if text:
                txt_dest = archive_dir / f"vtt_{ts}.txt"
                txt_dest.write_text(text)

            print(f"  💾 Saved: {raw_dest.name}")
        except Exception as e:
            print(f"  Warning: Could not save recording: {e}")

    def _cleanup(self, audio_file):
        if audio_file:
            try:
                Path(audio_file).unlink(missing_ok=True)
            except Exception:
                pass

    def cleanup(self):
        self.should_exit = True
        try:
            self._audio_controller.restore()
        except Exception:
            pass
        self.recorder.cleanup()
        if self._asr_client:
            try:
                self._asr_client.close()
            except Exception:
                pass
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except Exception:
                pass
        Path("/tmp/voice_to_text.starting").unlink(missing_ok=True)
