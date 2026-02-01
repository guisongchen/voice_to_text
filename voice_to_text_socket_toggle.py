#!/usr/bin/env python3
"""
Voice-to-Text Socket Toggle Script
Pure Python implementation using Unix domain socket for IPC.

Usage:
  - First press: Starts recording in background
  - Second press: Stops recording via socket communication
"""

import socket
import subprocess
import sys
import time
from pathlib import Path

SOCKET_FILE = Path("/tmp/voice_to_text.sock")


def send_stop_command():
    """Send stop command to running instance via socket."""
    if not SOCKET_FILE.exists():
        print("No recording instance found (socket doesn't exist)")
        return False
    
    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(5.0)  # 5 second timeout
        client.connect(str(SOCKET_FILE))
        client.sendall(b'STOP\n')
        response = client.recv(1024)
        client.close()
        
        if response == b'ACK\n':
            print("✓ Stop command sent successfully")
            return True
        else:
            print(f"⚠ Unexpected response: {response}")
            return False
    except socket.timeout:
        print("✗ Timeout: No response from recording service")
        return False
    except ConnectionRefusedError:
        print("✗ Connection refused: Removing stale socket file")
        if SOCKET_FILE.exists():
            SOCKET_FILE.unlink()
        return False
    except Exception as e:
        print(f"✗ Failed to send stop command: {e}")
        return False


def start_recording():
    """Start recording in background."""
    print("Starting recording...")
    
    # Get script directory
    script_dir = Path(__file__).parent.resolve()
    
    # Start recording in background
    log_file = Path("/tmp/voice_to_text.log")
    with open(log_file, 'w') as log:
        subprocess.Popen(
            ["uv", "run", "voice-to-text"],
            cwd=script_dir,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
    
    # Wait for initialization
    time.sleep(0.5)
    
    # # Show notification if available
    # try:
    #     subprocess.run(
    #         ["notify-send", "Voice to Text", 
    #          "Recording started - press Alt+R again to stop", "-t", "2000"],
    #         check=False,
    #         capture_output=True
    #     )
    # except FileNotFoundError:
    #     pass  # notify-send not available
    
    print("✓ Recording started")


def main():
    """Main toggle function."""
    if SOCKET_FILE.exists():
        # Recording is running - send stop command
        print("Recording detected, sending stop command...")
        send_stop_command()
    else:
        # No recording - start new instance
        start_recording()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
