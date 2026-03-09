#!/usr/bin/env python3
"""
Voice-to-Text Toggle Script
Toggle recording on/off using Unix domain socket.
"""

import socket
import subprocess
import sys
import time
from pathlib import Path

SOCKET_FILE = Path("/tmp/voice_to_text.sock")
SCRIPT_DIR = Path(__file__).parent.resolve()


def send_stop():
    """Send stop command to running instance."""
    if not SOCKET_FILE.exists():
        return False

    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(5.0)
        client.connect(str(SOCKET_FILE))
        client.sendall(b'STOP\n')
        response = client.recv(1024)
        client.close()

        if response == b'ACK\n':
            print("✓ Stop command sent")
            return True
    except socket.timeout:
        print("✗ Timeout waiting for response")
    except ConnectionRefusedError:
        print("✗ Connection refused, removing stale socket")
        SOCKET_FILE.unlink(missing_ok=True)
    except Exception as e:
        print(f"✗ Error: {e}")

    return False


def start_recording():
    """Start recording in background."""
    print("Starting recording...")

    log_file = Path("/tmp/voice_to_text.log")
    with open(log_file, 'w') as log:
        subprocess.Popen(
            ["uv", "run", "voice-to-text"],
            cwd=SCRIPT_DIR,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True
        )

    time.sleep(0.5)
    print("✓ Recording started")


def main():
    """Toggle recording on/off."""
    if SOCKET_FILE.exists():
        print("Recording detected, sending stop command...")
        if send_stop():
            return 0
        # If stop failed, maybe stale socket - try starting
        print("Failed to stop, attempting to start new recording...")

    start_recording()
    return 0


if __name__ == "__main__":
    sys.exit(main())
