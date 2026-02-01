"""
Socket mode: Use Unix domain socket for IPC (safer than PID file).
"""

import socket
import threading
import time
import os
from pathlib import Path
from .base_mode import BaseMode

from ..config import SOCKET_PATH


class SocketMode(BaseMode):
    """Socket mode: Use Unix domain socket for reliable IPC."""

    def __init__(self, audio_service, text_inserter,
                 audio_feedback, transcriber, config):
        """Initialize socket mode."""
        super().__init__(audio_service, text_inserter,
                        audio_feedback, transcriber, config)
        self.socket_path = Path(SOCKET_PATH)
        self.server_socket = None
        self.socket_thread = None

    def _socket_listener(self):
        """Listen for stop commands on socket."""
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        
        # Remove stale socket file if exists
        if self.socket_path.exists():
            self.socket_path.unlink()
        
        self.server_socket.bind(str(self.socket_path))
        self.server_socket.listen(1)
        self.server_socket.settimeout(1.0)  # Non-blocking with timeout
        
        while not self.should_exit:
            try:
                conn, _ = self.server_socket.accept()
                command = conn.recv(1024).decode('utf-8').strip()
                if command == 'STOP':
                    print("\n⏹️  Stop command received via socket")
                    self.stop_signal_received = True
                conn.sendall(b'ACK\n')  # Acknowledge receipt
                conn.close()
            except socket.timeout:
                continue
            except Exception as e:
                if not self.should_exit:
                    print(f"Socket error: {e}")
                break

    def run(self):
        """Run socket mode recording."""
        print("\n" + "=" * 60)
        print("✓ Ready! Recording will start in 2 seconds")
        print("  Run toggle script again to stop")
        print("=" * 60)

        self._setup_signal_handlers()

        try:
            # Start socket listener in background
            self.socket_thread = threading.Thread(target=self._socket_listener, daemon=True)
            self.socket_thread.start()

            print("\nStarting recording in 2 seconds...")
            print("Run the same command again to stop recording")
            time.sleep(2)

            self._start_recording()

            # Wait for stop signal
            while not self.stop_signal_received and not self.should_exit:
                time.sleep(0.1)

            if self.is_recording:
                self._stop_recording()

        except KeyboardInterrupt:
            print("\n\n⏹️  Stopping recording...")
            if self.is_recording:
                self.is_recording = False
                time.sleep(0.5)
                self._stop_recording()
        except Exception as e:
            print(f"\n✗ Error: {e}", flush=True)
            return 1
        finally:
            self.cleanup()

        return 0

    def start(self):
        """Start socket mode recording."""
        # Already handled in run()
        pass

    def stop(self):
        """Stop socket mode recording."""
        self.should_exit = True
        if self.is_recording:
            self._stop_recording()

    def cleanup(self):
        """Clean up resources including socket."""
        super().cleanup()
        
        # Close socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
        
        # Remove socket file
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except Exception:
                pass

    @staticmethod
    def send_stop_command():
        """Send stop command to running instance."""
        socket_path = Path(SOCKET_PATH)
        
        if not socket_path.exists():
            print("No recording instance found")
            return False
        
        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(str(socket_path))
            client.sendall(b'STOP\n')
            response = client.recv(1024)
            client.close()
            return response == b'ACK\n'
        except Exception as e:
            print(f"Failed to send stop command: {e}")
            return False
