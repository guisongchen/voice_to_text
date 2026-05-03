import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from .config import SOCKET_FILE, VENV_PYTHON, LOG_FILE


def find_processes():
    pids = []
    try:
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
                    "voice-to-text-t" in cmdline
                    or "toggle" in cmdline
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
    for pid in find_processes():
        try:
            os.kill(int(pid), 9)
        except (ProcessLookupError, PermissionError, ValueError):
            pass


def send_toggle():
    """Send TOGGLE to the running daemon. Returns response string or None on connection failure."""
    if not SOCKET_FILE.exists():
        return None

    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(2.0)
        client.connect(str(SOCKET_FILE))
        client.sendall(b'TOGGLE\n')
        response = client.recv(1024).decode('utf-8').strip()
        client.close()
        return response
    except (socket.timeout, ConnectionRefusedError, FileNotFoundError):
        pass
    except Exception as e:
        print(f"  Warning: send_toggle error: {e}", file=sys.stderr)
    return None


def cleanup_stale():
    had_work = SOCKET_FILE.exists() or find_processes()
    if SOCKET_FILE.exists():
        SOCKET_FILE.unlink(missing_ok=True)
    kill_processes()
    if had_work:
        time.sleep(0.2)


def start_recording():
    print("Starting recording...")

    # Sentinel to prevent double-spawn on rapid double-press
    starting_marker = Path("/tmp/voice_to_text.starting")
    if starting_marker.exists():
        if time.time() - starting_marker.stat().st_mtime < 3.0:
            print("  (already starting, skipping)")
            return True

    cleanup_stale()

    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    cmd = [python, "-m", "voice_to_text", "--start-recording"]

    env = os.environ.copy()
    env['HF_HUB_OFFLINE'] = '1'
    env['TRANSFORMERS_OFFLINE'] = '1'
    env['HF_DATASETS_OFFLINE'] = '1'

    starting_marker.touch()

    try:
        with open(LOG_FILE, 'w') as log:
            subprocess.Popen(
                cmd,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True
            )
    except Exception as e:
        starting_marker.unlink(missing_ok=True)
        print(f"  ✗ Error starting daemon: {e}", file=sys.stderr)
        return False

    print("✓ Recording started")
    return True


def main():
    daemon_running = SOCKET_FILE.exists() or find_processes()

    if daemon_running:
        result = send_toggle()
        if result is None:
            print("  ⚠ Daemon unresponsive, cleaning up and cold-starting...", file=sys.stderr)
            cleanup_stale()
            return 0 if start_recording() else 1
        if result == 'STARTED':
            print("✓ Recording started")
            return 0
        if result == 'STOPPED':
            print("✓ Stopping (transcribing)")
            return 0
        if result == 'BUSY':
            print("⚠ Daemon busy (transcribing), ignoring press")
            return 0
        print(f"✗ Daemon error: {result}", file=sys.stderr)
        return 1

    return 0 if start_recording() else 1


if __name__ == "__main__":
    sys.exit(main())
