#!/usr/bin/env python3
"""
Voice-to-Text Input Tool
System-wide voice input triggered by Alt+R hotkey with automatic text insertion.

PipeWire Noise Prevention:
- OUTPUT stream kept alive during recording to prevent suspension noise
- INPUT stream warm-up (50 chunks ~1.2s) discards mic activation artifacts
- Programmatic beep tones (no file I/O) for clean audio feedback
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
import numpy as np
import pyaudio

import evdev
from evdev import InputDevice, categorize, ecodes

from audio_recorder import AudioRecorder
from transcribe import AudioTranscriber


class VoiceToTextService:
    """Main service for voice-to-text input with global hotkey support."""
    
    def __init__(self, model_size='medium', min_duration=0.5, keep_audio=False, 
                 duration=None, no_hotkey=False, wait_for_key=False, use_pidfile=False):
        self.model_size = model_size
        self.min_duration = min_duration
        self.keep_audio = keep_audio
        self.fixed_duration = duration
        self.no_hotkey = no_hotkey
        self.wait_for_key = wait_for_key  # Wait for Alt+R to stop
        self.use_pidfile = use_pidfile  # Use PID file + SIGUSR1 for stopping
        self.pidfile = Path('/tmp/voice_to_text.pid')
        
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
        
        # PyAudio for beep generation
        self.pyaudio_instance = None
        self.output_stream = None  # Keep stream alive to prevent PipeWire noise
        
    def initialize(self):
        """Initialize all components."""
        print("=" * 60)
        print("Voice-to-Text Input Tool")
        print("=" * 60)
        
        # Skip keyboard device if not needed
        # Only needed for: hotkey mode OR wait_for_key mode
        # NOT needed for: fixed duration OR PID file mode
        if not self.no_hotkey or (self.wait_for_key and not self.use_pidfile):
            # Find keyboard device
            print("\n[1/3] Finding keyboard device...")
            self.keyboard_device = self._find_keyboard_device()
            if not self.keyboard_device:
                print("✗ Error: No keyboard device found!")
                print("  Make sure you're in the 'input' group:")
                print("    sudo usermod -aG input $USER")
                print("  Then log out and log back in.")
                print("\n  Alternatives:")
                print("    • Fixed duration: uv run voice_to_text.py --record-once -d 5")
                print("    • Toggle script: ./voice_to_text_toggle.sh (no input group needed)")
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
        if self.keep_audio:
            print("\n" + "=" * 60)
            print("DIAGNOSTIC MODE:")
            print("  • Recording files will be PRESERVED")
            print("=" * 60)
        
        print("\n" + "=" * 60)
        if self.no_hotkey:
            if self.fixed_duration:
                print(f"✓ Ready! Recording will start in 2 seconds ({self.fixed_duration}s duration)")
            elif self.wait_for_key:
                print("✓ Ready! Recording will start in 2 seconds")
                print("  Press Alt+R again to stop recording")
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
    
    def _generate_beep_tone(self, frequency=880, duration=0.2, sample_rate=44100):
        """Generate a beep tone as numpy array.
        
        Args:
            frequency: Frequency in Hz (default 880 Hz = A5 note)
            duration: Duration in seconds (default 0.2s)
            sample_rate: Sample rate in Hz (default 44100)
            
        Returns:
            numpy array of int16 audio samples
        """
        # Generate time array
        num_samples = int(sample_rate * duration)
        t = np.linspace(0, duration, num_samples, False)
        
        # Generate sine wave
        amplitude = 0.3  # 30% volume to prevent clipping
        sine_wave = amplitude * np.sin(2 * np.pi * frequency * t)
        
        # Apply fade in/out to avoid clicks
        fade_samples = int(sample_rate * 0.01)  # 10ms fade
        fade_in = np.linspace(0, 1, fade_samples)
        fade_out = np.linspace(1, 0, fade_samples)
        sine_wave[:fade_samples] *= fade_in
        sine_wave[-fade_samples:] *= fade_out
        
        # Convert to 16-bit PCM
        audio_data = (sine_wave * 32767).astype(np.int16)
        return audio_data
    
    def _play_tone(self, audio_data, sample_rate=44100):
        """Play audio tone using PyAudio.
        
        Args:
            audio_data: numpy array of int16 audio samples
            sample_rate: Sample rate in Hz
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
                    rate=sample_rate,
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
    
    def _open_output_stream(self, sample_rate=44100):
        """Open and keep output stream active to prevent PipeWire noise.
        
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
                    rate=sample_rate,
                    output=True
                )
        except Exception as e:
            print(f"\nWarning: Could not open output stream: {e}", file=sys.stderr)
    
    def _close_output_stream(self):
        """Close the persistent output stream."""
        try:
            if self.output_stream:
                self.output_stream.stop_stream()
                self.output_stream.close()
                self.output_stream = None
        except Exception as e:
            print(f"\nWarning: Could not close output stream: {e}", file=sys.stderr)
    
    def _play_beep(self, beep_type='start'):
        """Play audio feedback beep.
        
        Args:
            beep_type: 'start' for recording start, 'finish' for recording finish
        """
        try:
            if beep_type == 'start':
                # Quick double beep for start
                beep = self._generate_beep_tone(frequency=880, duration=0.08)
                self._play_tone(beep)
                time.sleep(0.04)  # Short pause between beeps
                self._play_tone(beep)
            else:  # finish
                # Single quick beep for finish
                beep = self._generate_beep_tone(frequency=660, duration=0.1)
                self._play_tone(beep)
                
        except Exception as e:
            print(f"\nWarning: Beep failed: {e}", file=sys.stderr)
    
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
        
        # Open output stream FIRST to keep PipeWire active (prevents noise)
        self._open_output_stream()
        
        # Play start beep
        self._play_beep('start')
        # Minimal delay - just let beep finish playing
        time.sleep(0.05)
        
        self.is_recording = True
        self.recording_start_time = time.time()
        
        # Create temporary file for recording
        temp_fd, temp_path = tempfile.mkstemp(suffix='.wav', prefix='voice_to_text_')
        self.current_audio_file = temp_path
        
        print("\nRecording... ", end='', flush=True)
        if not self.no_hotkey and not self.fixed_duration:
            print("(release Alt+R to stop)", flush=True)
        else:
            print("", flush=True)
        
        # Start recording in background thread
        # Thread handles INPUT stream warm-up (discard initial mic noise)
        self.recording_thread = threading.Thread(
            target=self._record_audio_thread,
            daemon=True
        )
        self.recording_thread.start()
    
    def _record_audio_thread(self):
        """Background thread for audio recording."""
        try:
            # Open audio INPUT stream (microphone)
            stream = self.recorder.audio.open(
                format=self.recorder.format,
                channels=self.recorder.channels,
                rate=self.recorder.sample_rate,
                input=True,
                frames_per_buffer=self.recorder.chunk_size,
                stream_callback=None
            )
            
            # INPUT WARM-UP: Discard initial chunks to avoid mic activation noise
            # Minimal warm-up since output stream keep-alive prevents most issues
            warmup_chunks = 3  # ~70ms - just enough to stabilize
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
            
            # COOL-DOWN: Minimal cool-down since output stream stays active
            cooldown_chunks = 2  # ~50ms - just for clean closure
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
        
        print(f"\nStopped (duration: {duration:.1f}s)")
        
        # Wait for recording thread to finish (includes cool-down)
        if self.recording_thread:
            self.recording_thread.join(timeout=3.0)
        
        # Play finish beep immediately
        self._play_beep('finish')
        
        # Close output stream now that we're done with audio
        self._close_output_stream()
        
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
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Setup SIGUSR1 handler for stop signal (PID file mode)
        if self.use_pidfile:
            signal.signal(signal.SIGUSR1, self._sigusr1_handler)
        
        # Single recording mode (no hotkey monitoring)
        if self.no_hotkey:
            return self._run_single_recording()
        
        # Continuous hotkey monitoring mode
        return self._run_hotkey_mode()
    
    def _sigusr1_handler(self, signum, frame):
        """Handle SIGUSR1 signal to stop recording."""
        if self.is_recording:
            print("\n[Received stop signal]")
            self.is_recording = False
    
    def _run_single_recording(self):
        """Run a single recording session without hotkey monitoring."""
        try:
            if self.use_pidfile:
                # PID file mode - wait for SIGUSR1 signal to stop
                print("\nStarting recording in 2 seconds...")
                print("Run the same command again (or send SIGUSR1) to stop recording")
                time.sleep(2)
                
                # Write PID file
                self.pidfile.write_text(str(os.getpid()))
                
                self._start_recording()
                
                # Wait for signal to stop
                while self.is_recording and not self.should_exit:
                    time.sleep(0.1)
                
                # Clean up PID file
                if self.pidfile.exists():
                    self.pidfile.unlink()
                
                if self.is_recording:
                    self._stop_recording()
                    
            elif self.wait_for_key:
                # Wait for Alt+R to stop recording
                print("\nStarting recording in 2 seconds...")
                print("Press Alt+R again to stop recording")
                time.sleep(2)
                self._start_recording()
                
                # Monitor for Alt+R press
                self._wait_for_stop_key()
                
                if self.is_recording:
                    self._stop_recording()
            elif self.fixed_duration:
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
    
    def _wait_for_stop_key(self):
        """Wait for Alt+R press to stop recording."""
        alt_pressed = False
        
        try:
            for event in self.keyboard_device.read_loop():
                if not self.is_recording or self.should_exit:
                    break
                
                if event.type == ecodes.EV_KEY:
                    # Track Alt key
                    if event.code in [ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT]:
                        if event.value == 1:  # Key down
                            alt_pressed = True
                        elif event.value == 0:  # Key up
                            alt_pressed = False
                    
                    # Check for R key press
                    elif event.code == ecodes.KEY_R:
                        if event.value == 1 and alt_pressed:  # Alt+R pressed
                            # Stop recording
                            break
                            
        except Exception as e:
            print(f"\n✗ Keyboard monitoring error: {e}")
    
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
        # Clean up PID file if it exists
        if self.use_pidfile and self.pidfile.exists():
            try:
                self.pidfile.unlink()
            except Exception:
                pass
        
        self._close_output_stream()
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()
            self.pyaudio_instance = None
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
  
  # Single recording - press Alt+R again to stop (RECOMMENDED)
  uv run voice_to_text.py --record-once
  
  # Single recording with fixed 5 second duration
  uv run voice_to_text.py --record-once -d 5
  
  # Use with toggle script (NO INPUT GROUP NEEDED)
  ./voice_to_text_toggle.sh
  
  # Use faster model
  uv run voice_to_text.py --record-once --model small
  
  # Keep audio files for debugging
  uv run voice_to_text.py --record-once --keep-audio
  
  # List available keyboard devices (for hotkey mode)
  uv run voice_to_text.py --list-keyboards

Desktop Shortcut Setup (GNOME):
  
  SECURE METHOD (no input group needed):
  1. Open Settings > Keyboard > Keyboard Shortcuts
  2. Click "+" to add custom shortcut
  3. Name: "Voice to Text"
  4. Command: /full/path/to/voice_to_text_toggle.sh
  5. Set shortcut: Alt+R
  6. Press Alt+R to start, Alt+R again to stop!
  
  ALTERNATIVE (requires input group):
  Command: /full/path/to/uv run /full/path/to/voice_to_text.py --record-once
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
        help='Fixed recording duration in seconds (optional, otherwise press Alt+R to stop)'
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
        '--record-once',
        action='store_true',
        help='Record once and exit (use with --use-pidfile or -d for duration)'
    )
    parser.add_argument(
        '--use-pidfile',
        action='store_true',
        help='Use PID file + SIGUSR1 for stopping (no keyboard monitoring)'
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
        wait_for_key=(args.record_once and not args.duration and not args.use_pidfile),
        use_pidfile=args.use_pidfile
    )
    
    return service.run()


if __name__ == "__main__":
    sys.exit(main())
