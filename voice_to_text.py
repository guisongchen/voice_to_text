#!/usr/bin/env python3
"""
Voice-to-Text Input Tool
System-wide voice input triggered by Alt+R hotkey with automatic text insertion.
"""
import argparse
import sys
import subprocess
import signal
import tempfile
import time
from pathlib import Path
from datetime import datetime
import threading
import queue
import os

import evdev
from evdev import InputDevice, categorize, ecodes

from audio_recorder import AudioRecorder
from transcribe import AudioTranscriber


class VoiceToTextService:
    """Main service for voice-to-text input with global hotkey support."""
    
    def __init__(self, model_size='medium', min_duration=0.5, keep_audio=False, 
                 duration=None, no_hotkey=False, no_beeps=False):
        self.model_size = model_size
        self.min_duration = min_duration
        self.keep_audio = keep_audio
        self.fixed_duration = duration
        self.no_hotkey = no_hotkey
        self.no_beeps = no_beeps
        
        # State tracking
        self.is_recording = False
        self.recording_start_time = None
        self.current_audio_file = None
        self.should_exit = False
        
        # Components
        self.recorder = None
        self.transcriber = None
        self.keyboard_device = None
        
        # Threading for non-blocking recording
        self.recording_thread = None
        self.audio_queue = queue.Queue()
        
    def initialize(self):
        """Initialize all components."""
        print("=" * 60)
        print("Voice-to-Text Input Tool")
        print("=" * 60)
        
        # Skip keyboard device if in no-hotkey mode
        if not self.no_hotkey:
            # Find keyboard device
            print("\n[1/3] Finding keyboard device...")
            self.keyboard_device = self._find_keyboard_device()
            if not self.keyboard_device:
                print("✗ Error: No keyboard device found!")
                print("  Make sure you're in the 'input' group:")
                print("    sudo usermod -aG input $USER")
                print("  Then log out and log back in.")
                print("\n  Alternative: Use --record-once mode (no keyboard access needed):")
                print("    uv run voice_to_text.py --record-once")
                return False
            print(f"✓ Using keyboard: {self.keyboard_device.name}")
            
            step = 2
        else:
            step = 1
        
        # Check xdotool
        print(f"\n[{step}/{2 if self.no_hotkey else 3}] Checking xdotool...")
        if not self._check_xdotool():
            print("✗ Error: xdotool not found!")
            print("  Install with: sudo apt install xdotool")
            return False
        print("✓ xdotool is available")
        
        step += 1
        
        # Pre-load Whisper model
        print(f"\n[{step}/{2 if self.no_hotkey else 3}] Loading Whisper model '{self.model_size}'...")
        print("  (This may take 5-10 seconds on first run)")
        try:
            self.transcriber = AudioTranscriber(model_size=self.model_size)
            print("✓ Model loaded successfully!")
        except Exception as e:
            print(f"✗ Error loading model: {e}")
            return False
        
        # Initialize audio recorder
        self.recorder = AudioRecorder()
        
        # Show diagnostic mode info
        if self.no_beeps or self.keep_audio:
            print("\n" + "=" * 60)
            print("DIAGNOSTIC MODE:")
            if self.no_beeps:
                print("  • Audio feedback beeps DISABLED")
            if self.keep_audio:
                print("  • Recording files will be PRESERVED")
            print("=" * 60)
        
        print("\n" + "=" * 60)
        if self.no_hotkey:
            if self.fixed_duration:
                print(f"✓ Ready! Recording will start in 2 seconds ({self.fixed_duration}s duration)")
            else:
                print("✓ Ready! Press Ctrl+C when done recording")
        else:
            print("✓ Ready! Press and hold Alt+R to record speech")
            print("  Release Alt+R to transcribe and insert text")
            print("  Press Ctrl+C to exit")
        print("=" * 60)
        
        return True
    
    def _find_keyboard_device(self):
        """Find a suitable keyboard input device."""
        try:
            devices = [InputDevice(path) for path in evdev.list_devices()]
        except PermissionError:
            return None
        
        # Look for devices that have key capabilities
        for device in devices:
            capabilities = device.capabilities()
            if ecodes.EV_KEY in capabilities:
                # Check if it has keyboard keys (not just power button, etc.)
                keys = capabilities[ecodes.EV_KEY]
                if ecodes.KEY_A in keys or ecodes.KEY_LEFTALT in keys:
                    return device
        
        return None
    
    def _check_xdotool(self):
        """Check if xdotool is installed."""
        try:
            result = subprocess.run(
                ['xdotool', 'version'],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _play_beep(self, beep_type='start'):
        """Play a beep sound for feedback.
        
        Uses terminal bell (system beep) which bypasses audio system.
        Falls back to audio files if terminal bell doesn't work.
        
        Args:
            beep_type: 'start' for recording start, 'finish' for recording finish
        """
        try:
            # PRIMARY: Use terminal bell (bypasses PipeWire entirely)
            # Double beep for start, single for finish (to distinguish)
            if beep_type == 'start':
                print('\a\a', end='', flush=True)  # Two beeps
            else:  # finish
                print('\a', end='', flush=True)  # One beep
            
            # Note: Terminal bell behavior depends on terminal settings
            # GNOME Terminal, Konsole, etc. handle this differently
            # Some play sound, some flash screen, some do nothing
            
        except Exception:
            # Silent failure - beep is nice-to-have, not critical
            pass
    
    def _insert_text(self, text):
        """Insert text at cursor position using xdotool."""
        if not text or not text.strip():
            print("  (No text to insert)")
            return False
        
        try:
            # Use xdotool to type the text directly at cursor
            subprocess.run(
                ['xdotool', 'type', '--clearmodifiers', '--', text],
                check=True,
                timeout=10
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"  ✗ Error inserting text: {e}")
            return False
        except subprocess.TimeoutExpired:
            print("  ✗ Error: xdotool timed out")
            return False
    
    def _start_recording(self):
        """Start audio recording in a separate thread."""
        if self.is_recording:
            return
        
        # Play start beep BEFORE starting recording (if enabled)
        if not self.no_beeps:
            self._play_beep('start')
            # Short delay for beep to finish (warm-up happens in thread)
            time.sleep(0.3)
        
        self.is_recording = True
        self.recording_start_time = time.time()
        
        # Create temporary file for recording
        temp_fd, temp_path = tempfile.mkstemp(suffix='.wav', prefix='voice_to_text_')
        self.current_audio_file = temp_path
        
        print("\n🎤 Recording... (release Alt+R to stop)")
        
        # Start recording in background thread
        # Thread will do extended warm-up for PipeWire/PulseAudio
        self.recording_thread = threading.Thread(
            target=self._record_audio_thread,
            daemon=True
        )
        self.recording_thread.start()
    
    def _record_audio_thread(self):
        """Background thread for audio recording."""
        try:
            # Open audio stream
            stream = self.recorder.audio.open(
                format=self.recorder.format,
                channels=self.recorder.channels,
                rate=self.recorder.sample_rate,
                input=True,
                frames_per_buffer=self.recorder.chunk_size,
                # These may help with PipeWire/PulseAudio stability
                stream_callback=None
            )
            
            # EXTENDED WARM-UP for PipeWire/PulseAudio
            # PipeWire needs ~1 second to fully activate the stream
            # Discard audio during activation to avoid buzz/noise
            warmup_chunks = 50  # ~1.2 seconds at default chunk size
            for i in range(warmup_chunks):
                if not self.is_recording:
                    break
                try:
                    stream.read(self.recorder.chunk_size, exception_on_overflow=False)
                except Exception:
                    pass
            
            frames = []
            
            # Now record the actual audio (system should be stable)
            while self.is_recording:
                try:
                    data = stream.read(self.recorder.chunk_size, exception_on_overflow=False)
                    frames.append(data)
                except Exception as e:
                    print(f"  Recording error: {e}")
                    break
            
            # COOL-DOWN: Keep reading for a bit to avoid end noise
            # This helps PipeWire cleanly close the stream
            cooldown_chunks = 10  # ~230ms
            for _ in range(cooldown_chunks):
                try:
                    stream.read(self.recorder.chunk_size, exception_on_overflow=False)
                except Exception:
                    pass
            
            stream.stop_stream()
            stream.close()
            
            # Save the recording
            if frames:
                self.recorder._save_wav(frames, self.current_audio_file)
                self.audio_queue.put(('success', self.current_audio_file))
            else:
                self.audio_queue.put(('error', 'No audio data recorded'))
                
        except Exception as e:
            self.audio_queue.put(('error', str(e)))
    
    def _stop_recording(self):
        """Stop audio recording and process."""
        if not self.is_recording:
            return
        
        self.is_recording = False
        duration = time.time() - self.recording_start_time
        
        print(f"⏹️  Stopped (duration: {duration:.1f}s)")
        
        # Wait for recording thread to finish (includes cool-down)
        if self.recording_thread:
            self.recording_thread.join(timeout=3.0)
        
        # Play finish beep AFTER recording has stopped (if enabled)
        if not self.no_beeps:
            # Short delay before beep (stream is already closed cleanly)
            time.sleep(0.2)
            self._play_beep('finish')
        
        # Check if recording was successful
        try:
            status, data = self.audio_queue.get(timeout=1.0)
            if status == 'error':
                print(f"  ✗ Recording error: {data}")
                return
        except queue.Empty:
            print("  ✗ Recording thread timed out")
            return
        
        # Check minimum duration
        if duration < self.min_duration:
            print(f"  ⚠ Recording too short (< {self.min_duration}s), ignoring")
            self._cleanup_audio_file()
            return
        
        # Transcribe and insert
        self._transcribe_and_insert()
    
    def _transcribe_and_insert(self):
        """Transcribe the recorded audio and insert the text."""
        if not self.current_audio_file or not Path(self.current_audio_file).exists():
            print("  ✗ Error: Audio file not found")
            return
        
        print("🔄 Transcribing...")
        
        try:
            # Transcribe using pre-loaded model
            result = self.transcriber.model.transcribe(
                self.current_audio_file,
                verbose=False
            )
            text = result["text"].strip()
            
            if not text:
                print("  ⚠ No speech detected")
                self._cleanup_audio_file()
                return
            
            # Show preview of transcription
            preview = text[:80] + "..." if len(text) > 80 else text
            print(f"📝 Transcribed: \"{preview}\"")
            
            # Insert text at cursor
            print("⌨️  Inserting text...")
            if self._insert_text(text):
                print("✓ Done!")
            else:
                print("  You can manually copy/paste this text:")
                print(f"  {text}")
            
        except Exception as e:
            print(f"  ✗ Transcription error: {e}")
        finally:
            self._cleanup_audio_file()
    
    def _cleanup_audio_file(self):
        """Clean up temporary audio file."""
        if self.current_audio_file and not self.keep_audio:
            try:
                Path(self.current_audio_file).unlink(missing_ok=True)
            except Exception:
                pass
        elif self.current_audio_file and self.keep_audio:
            print(f"  Audio saved: {self.current_audio_file}")
        
        self.current_audio_file = None
    
    def run(self):
        """Main event loop - listen for Alt+R hotkey or do single recording."""
        if not self.initialize():
            return 1
        
        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Single recording mode (no hotkey monitoring)
        if self.no_hotkey:
            return self._run_single_recording()
        
        # Continuous hotkey monitoring mode
        return self._run_hotkey_mode()
    
    def _run_single_recording(self):
        """Run a single recording session without hotkey monitoring."""
        try:
            if self.fixed_duration:
                # Fixed duration recording
                time.sleep(2)  # Give user time to focus the target window
                self._start_recording()
                time.sleep(self.fixed_duration)
                self._stop_recording()
            else:
                # Manual stop with Ctrl+C
                print("\nStarting recording in 2 seconds...")
                print("Press Ctrl+C when done recording")
                time.sleep(2)
                self._start_recording()
                
                # Wait for Ctrl+C
                while self.is_recording and not self.should_exit:
                    time.sleep(0.1)
                
                if self.is_recording:
                    self._stop_recording()
        except KeyboardInterrupt:
            print("\n\n⏹️  Stopping recording...")
            if self.is_recording:
                self.is_recording = False
                time.sleep(0.5)  # Give recording thread time to finish
                self._stop_recording()
        except Exception as e:
            print(f"\n✗ Error: {e}")
            return 1
        finally:
            self.cleanup()
        
        print("\n👋 Done!")
        return 0
    
    def _run_hotkey_mode(self):
        """Run continuous hotkey monitoring mode."""
        # Track Alt key state
        alt_pressed = False
        r_pressed = False
        
        try:
            for event in self.keyboard_device.read_loop():
                if self.should_exit:
                    break
                
                if event.type == ecodes.EV_KEY:
                    key_event = categorize(event)
                    
                    # Track Alt key (left or right)
                    if event.code in [ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT]:
                        if event.value == 1:  # Key down
                            alt_pressed = True
                        elif event.value == 0:  # Key up
                            alt_pressed = False
                            # If we were recording, stop
                            if self.is_recording:
                                self._stop_recording()
                    
                    # Track R key
                    elif event.code == ecodes.KEY_R:
                        if event.value == 1:  # Key down
                            r_pressed = True
                            # Start recording if Alt is held
                            if alt_pressed and not self.is_recording:
                                self._start_recording()
                        elif event.value == 0:  # Key up
                            r_pressed = False
                            
        except Exception as e:
            print(f"\n✗ Error: {e}")
            return 1
        finally:
            self.cleanup()
        
        print("\n👋 Goodbye!")
        return 0
    
    def _signal_handler(self, signum, frame):
        """Handle interrupt signals for graceful shutdown."""
        print("\n\n⏹️  Shutting down...")
        self.should_exit = True
        if self.is_recording:
            self.is_recording = False
    
    def cleanup(self):
        """Clean up resources."""
        if self.recorder:
            self.recorder.close()
        if self.current_audio_file:
            self._cleanup_audio_file()


def list_keyboard_devices():
    """List all available keyboard input devices."""
    print("\nAvailable keyboard input devices:")
    print("=" * 60)
    
    try:
        devices = [InputDevice(path) for path in evdev.list_devices()]
    except PermissionError:
        print("✗ Permission denied!")
        print("  You need to be in the 'input' group:")
        print("    sudo usermod -aG input $USER")
        print("  Then log out and log back in.")
        return
    
    found_keyboards = False
    for device in devices:
        capabilities = device.capabilities()
        if ecodes.EV_KEY in capabilities:
            keys = capabilities[ecodes.EV_KEY]
            if ecodes.KEY_A in keys or ecodes.KEY_LEFTALT in keys:
                found_keyboards = True
                print(f"\n📋 {device.path}")
                print(f"   Name: {device.name}")
                print(f"   Physical: {device.phys}")
    
    if not found_keyboards:
        print("\n⚠ No keyboard devices found")


def main():
    parser = argparse.ArgumentParser(
        description="Voice-to-Text Input Tool - Press Alt+R to record and insert text",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
System Requirements (Hotkey Mode):
  1. User must be in 'input' group:
     sudo usermod -aG input $USER
     (then log out and back in)
  
  2. xdotool must be installed:
     sudo apt install xdotool
  
  3. NVIDIA GPU with CUDA for Whisper transcription

SECURITY NOTE: 
  Hotkey mode requires input group access. For a more secure approach,
  use --record-once mode with desktop environment shortcuts.

Usage Modes:

  HOTKEY MODE (requires input group):
    Press and hold Alt+R to start recording
    Release Alt+R to stop and transcribe
    Text will be inserted at cursor position

  SINGLE RECORDING MODE (secure, no input group needed):
    Use --record-once to record once and exit
    Bind this command to Alt+R in GNOME Keyboard Settings
    or run manually for voice input

Examples:
  # Hotkey mode (requires input group)
  uv run voice_to_text.py
  
  # Single recording with fixed 5 second duration (RECOMMENDED)
  uv run voice_to_text.py --record-once -d 5
  
  # Single recording with manual stop (press Ctrl+C)
  uv run voice_to_text.py --record-once
  
  # Use faster model
  uv run voice_to_text.py --record-once --model small -d 3
  
  # Keep audio files for debugging
  uv run voice_to_text.py --record-once --keep-audio -d 5
  
  # Disable beeps for diagnostics (test if beeps cause issues)
  uv run voice_to_text.py --record-once --no-beeps -d 5
  
  # Full diagnostic mode (no beeps, keep audio file)
  uv run voice_to_text.py --record-once --no-beeps --keep-audio -d 5
  
  # List available keyboard devices (for hotkey mode)
  uv run voice_to_text.py --list-keyboards

Diagnostic Workflow:
  If you hear noise/buzz in recordings:
  1. Test without beeps: --no-beeps --keep-audio -d 5
  2. Check saved WAV file with audio player
  3. If noise is in WAV file: recording issue
  4. If noise only during playback: beep/output issue

Desktop Shortcut Setup (GNOME):
  1. Open Settings → Keyboard → Keyboard Shortcuts
  2. Click "+" to add custom shortcut
  3. Name: "Voice to Text"
  4. Command: /full/path/to/uv run /full/path/to/voice_to_text.py --record-once -d 5
  5. Set shortcut: Alt+R
  6. Now Alt+R records for 5 seconds and inserts text at cursor!
        """
    )
    
    parser.add_argument(
        '-m', '--model',
        type=str,
        default='medium',
        choices=['tiny', 'base', 'small', 'medium', 'large'],
        help='Whisper model size (default: medium per spec)'
    )
    parser.add_argument(
        '-d', '--duration',
        type=float,
        help='Fixed recording duration in seconds (for --record-once mode)'
    )
    parser.add_argument(
        '--min-duration',
        type=float,
        default=0.5,
        help='Minimum recording duration in seconds (default: 0.5)'
    )
    parser.add_argument(
        '--keep-audio',
        action='store_true',
        help='Keep audio files instead of deleting them (for debugging)'
    )
    parser.add_argument(
        '--no-beeps',
        action='store_true',
        help='Disable audio feedback beeps (for diagnostic purposes)'
    )
    parser.add_argument(
        '--record-once',
        action='store_true',
        help='Record once and exit (no keyboard monitoring, no input group needed)'
    )
    parser.add_argument(
        '--list-keyboards',
        action='store_true',
        help='List available keyboard input devices and exit'
    )
    
    args = parser.parse_args()
    
    # List keyboards mode
    if args.list_keyboards:
        list_keyboard_devices()
        return 0
    
    # Run the service
    service = VoiceToTextService(
        model_size=args.model,
        min_duration=args.min_duration,
        keep_audio=args.keep_audio,
        duration=args.duration,
        no_hotkey=args.record_once,
        no_beeps=args.no_beeps
    )
    
    return service.run()


if __name__ == "__main__":
    sys.exit(main())
