#!/usr/bin/env python3
"""
Voice-to-Text Toggle Script
Toggle recording on/off using Unix domain socket.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

SOCKET_FILE = Path("/tmp/voice_to_text.sock")
SCRIPT_DIR = Path(__file__).parent.resolve()
MAIN_SCRIPT = SCRIPT_DIR / "voice_to_text.py"
VENV_PYTHON = SCRIPT_DIR / ".venv" / "bin" / "python3"
LOG_FILE = Path("/tmp/voice_to_text.log")
STOP_TIMEOUT = 30.0
STARTUP_TIMEOUT = 5.0


def find_processes():
    """Find running voice-to-text service processes."""
    pids = []
    try:
        # Match both "voice-to-text" and "voice_to_text" (hyphens or underscores)
        result = subprocess.run(
            ["pgrep", "-a", "-f", "voice.to.text"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                parts = line.split(None, 1)
                if len(parts) < 2:
                    continue
                pid, cmdline = parts
                skip = (
                    "toggle" in cmdline
                    or "listener" in cmdline
                    or "grep" in cmdline
                    or cmdline.startswith("/bin/bash")
                    or cmdline.startswith("bash ")
                )
                if not skip:
                    pids.append(pid)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return pids


def kill_processes():
    """Force-kill any running voice-to-text processes."""
    pids = find_processes()
    for pid in pids:
        try:
            os.kill(int(pid), 9)
        except (ProcessLookupError, PermissionError, ValueError):
            pass


def send_stop():
    """Send stop command to running instance. Returns True if ACK received."""
    if not SOCKET_FILE.exists():
        return False

    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(2.0)
        client.connect(str(SOCKET_FILE))
        client.sendall(b'STOP\n')
        response = client.recv(1024)
        client.close()

        if response == b'ACK\n':
            return True
    except (socket.timeout, ConnectionRefusedError, FileNotFoundError):
        pass
    except Exception as e:
        print(f"  Warning: send_stop error: {e}", file=sys.stderr)

    return False


def wait_for_exit():
    """Wait for daemon process to exit and socket to disappear."""
    deadline = time.time() + STOP_TIMEOUT
    while time.time() < deadline:
        if not SOCKET_FILE.exists() and not find_processes():
            return True
        time.sleep(0.3)
    return False


def cleanup_stale():
    """Remove stale socket and kill leftover processes."""
    had_work = SOCKET_FILE.exists() or find_processes()
    if SOCKET_FILE.exists():
        SOCKET_FILE.unlink(missing_ok=True)
    kill_processes()
    if had_work:
        time.sleep(0.2)


def start_recording():
    """Start recording in background. Returns True if daemon started."""
    print("Starting recording...")

    # Clean up any stale state first
    cleanup_stale()

    # Run the daemon using the venv Python
    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    cmd = [python, str(MAIN_SCRIPT)]

    # Pass environment with offline flags to prevent network hangs
    env = os.environ.copy()
    env['HF_HUB_OFFLINE'] = '1'
    env['TRANSFORMERS_OFFLINE'] = '1'
    env['HF_DATASETS_OFFLINE'] = '1'

    try:
        with open(LOG_FILE, 'w') as log:
            subprocess.Popen(
                cmd,
                cwd=SCRIPT_DIR,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True
            )
    except FileNotFoundError:
        print(f"  ✗ Error: {MAIN_SCRIPT} not found", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  ✗ Error starting daemon: {e}", file=sys.stderr)
        return False

    # Wait for daemon to start and create socket
    deadline = time.time() + STARTUP_TIMEOUT
    while time.time() < deadline:
        if SOCKET_FILE.exists() and find_processes():
            print("✓ Recording started")
            return True
        time.sleep(0.3)

    print("✗ Failed to start recording (check /tmp/voice_to_text.log)", file=sys.stderr)
    return False


def main():
    """Toggle recording on/off."""
    daemon_running = SOCKET_FILE.exists() or find_processes()

    if daemon_running:
        print("Recording detected, sending stop command...")

        if not send_stop():
            # STOP command failed — daemon may be in bad state
            pids = find_processes()
            if pids:
                print(f"  ⚠ Failed to send STOP (pids: {', '.join(pids)}), force stopping...", file=sys.stderr)
                cleanup_stale()
            else:
                # Stale socket with no process — just clean up
                print("  ⚠ Stale socket detected, cleaning up...", file=sys.stderr)
                if SOCKET_FILE.exists():
                    SOCKET_FILE.unlink(missing_ok=True)
            print("✓ Stopped")
            return 0

        if wait_for_exit():
            print("✓ Stopped")
            return 0

        # Process is stuck — force cleanup
        print("⚠ Process stuck, force stopping...", file=sys.stderr)
        cleanup_stale()
        print("✓ Stopped")
        return 0

    start_recording()
    return 0


if __name__ == "__main__":
    sys.exit(main())
