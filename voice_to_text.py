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

import evdev
from evdev import InputDevice, categorize, ecodes

from audio_recorder import AudioRecorder
from transcribe import AudioTranscriber


class VoiceToTextService:
    """Main service for voice-to-text input with global hotkey support."""
    
    def __init__(self, model_size='medium', min_duration=0.5, keep_audio=False):
        self.model_size = model_size
        self.min_duration = min_duration
        self.keep_audio = keep_audio
        
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
        
        # Find keyboard device
        print("\n[1/3] Finding keyboard device...")
        self.keyboard_device = self._find_keyboard_device()
        if not self.keyboard_device:
            print("✗ Error: No keyboard device found!")
            print("  Make sure you're in the 'input' group:")
            print("    sudo usermod -aG input $USER")
            print("  Then log out and log back in.")
            return False
        print(f"✓ Using keyboard: {self.keyboard_device.name}")
        
        # Check ydotool
        print("\n[2/3] Checking ydotool...")
        if not self._check_ydotool():
            print("✗ Error: ydotool not found or not working!")
            print("  Install with: sudo apt install ydotool")
            print("  You may need to start ydotool daemon:")
            print("    systemctl --user start ydotoold")
            return False
        print("✓ ydotool is available")
        
        # Pre-load Whisper model
        print(f"\n[3/3] Loading Whisper model '{self.model_size}'...")
        print("  (This may take 5-10 seconds on first run)")
        try:
            self.transcriber = AudioTranscriber(model_size=self.model_size)
            print("✓ Model loaded successfully!")
        except Exception as e:
            print(f"✗ Error loading model: {e}")
            return False
        
        # Initialize audio recorder
        self.recorder = AudioRecorder()
        
        print("\n" + "=" * 60)
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
    
    def _check_ydotool(self):
        """Check if ydotool is installed and working."""
        try:
            result = subprocess.run(
                ['ydotool', '--help'],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _insert_text(self, text):
        """Insert text at cursor position using ydotool."""
        if not text or not text.strip():
            print("  (No text to insert)")
            return False
        
        try:
            # Use ydotool to type the text
            # Add small delay to ensure it works reliably
            subprocess.run(
                ['ydotool', 'type', text],
                check=True,
                timeout=5
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"  ✗ Error inserting text: {e}")
            return False
        except subprocess.TimeoutExpired:
            print("  ✗ Error: ydotool timed out")
            return False
    
    def _start_recording(self):
        """Start audio recording in a separate thread."""
        if self.is_recording:
            return
        
        self.is_recording = True
        self.recording_start_time = time.time()
        
        # Create temporary file for recording
        temp_fd, temp_path = tempfile.mkstemp(suffix='.wav', prefix='voice_to_text_')
        self.current_audio_file = temp_path
        
        print("\n🎤 Recording... (release Alt+R to stop)")
        
        # Start recording in background thread
        self.recording_thread = threading.Thread(
            target=self._record_audio_thread,
            daemon=True
        )
        self.recording_thread.start()
    
    def _record_audio_thread(self):
        """Background thread for audio recording."""
        try:
            # Record until stopped
            # We'll record in chunks and check if we should stop
            stream = self.recorder.audio.open(
                format=self.recorder.format,
                channels=self.recorder.channels,
                rate=self.recorder.sample_rate,
                input=True,
                frames_per_buffer=self.recorder.chunk_size
            )
            
            frames = []
            
            while self.is_recording:
                try:
                    data = stream.read(self.recorder.chunk_size, exception_on_overflow=False)
                    frames.append(data)
                except Exception as e:
                    print(f"  Recording error: {e}")
                    break
            
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
        
        # Wait for recording thread to finish
        if self.recording_thread:
            self.recording_thread.join(timeout=2.0)
        
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
                print("  You can manually paste this text:")
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
        """Main event loop - listen for Alt+R hotkey."""
        if not self.initialize():
            return 1
        
        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
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
System Requirements:
  1. User must be in 'input' group:
     sudo usermod -aG input $USER
     (then log out and back in)
  
  2. ydotool must be installed:
     sudo apt install ydotool
  
  3. NVIDIA GPU with CUDA for Whisper transcription

Usage:
  Press and hold Alt+R to start recording
  Release Alt+R to stop and transcribe
  Text will be inserted at cursor position

Examples:
  # Run with default settings (medium model)
  uv run voice_to_text.py
  
  # Use faster model
  uv run voice_to_text.py --model small
  
  # Keep audio files for debugging
  uv run voice_to_text.py --keep-audio
  
  # List available keyboard devices
  uv run voice_to_text.py --list-keyboards
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
        '--min-duration',
        type=float,
        default=0.5,
        help='Minimum recording duration in seconds (default: 0.5)'
    )
    parser.add_argument(
        '--keep-audio',
        action='store_true',
        help='Keep audio files instead of deleting them'
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
        keep_audio=args.keep_audio
    )
    
    return service.run()


if __name__ == "__main__":
    sys.exit(main())
