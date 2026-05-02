import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from .config import SOCKET_FILE, VENV_PYTHON, LOG_FILE, STOP_TIMEOUT, STARTUP_TIMEOUT

MAIN_SCRIPT = Path(__file__).parent.parent.parent / "src" / "voice_to_text" / "__main__.py"


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


def send_stop():
    if not SOCKET_FILE.exists():
        return False

    try:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(2.0)
        client.connect(str(SOCKET_FILE))
        client.sendall(b'STOP\n')
        response = client.recv(1024)
        client.close()
        return response == b'ACK\n'
    except (socket.timeout, ConnectionRefusedError, FileNotFoundError):
        pass
    except Exception as e:
        print(f"  Warning: send_stop error: {e}", file=sys.stderr)
    return False


def wait_for_exit():
    deadline = time.time() + STOP_TIMEOUT
    while time.time() < deadline:
        if not SOCKET_FILE.exists() and not find_processes():
            return True
        time.sleep(0.3)
    return False


def cleanup_stale():
    had_work = SOCKET_FILE.exists() or find_processes()
    if SOCKET_FILE.exists():
        SOCKET_FILE.unlink(missing_ok=True)
    kill_processes()
    if had_work:
        time.sleep(0.2)


def start_recording():
    print("Starting recording...")
    cleanup_stale()

    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    cmd = [python, "-m", "voice_to_text"]

    env = os.environ.copy()
    env['HF_HUB_OFFLINE'] = '1'
    env['TRANSFORMERS_OFFLINE'] = '1'
    env['HF_DATASETS_OFFLINE'] = '1'

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
        print(f"  ✗ Error starting daemon: {e}", file=sys.stderr)
        return False

    deadline = time.time() + STARTUP_TIMEOUT
    while time.time() < deadline:
        if SOCKET_FILE.exists() and find_processes():
            print("✓ Recording started")
            return True
        time.sleep(0.3)

    print("✗ Failed to start recording (check /tmp/voice_to_text.log)", file=sys.stderr)
    return False


def main():
    daemon_running = SOCKET_FILE.exists() or find_processes()

    if daemon_running:
        print("Recording detected, sending stop command...")

        if not send_stop():
            pids = find_processes()
            if pids:
                print(f"  ⚠ Failed to send STOP (pids: {', '.join(pids)}), force stopping...", file=sys.stderr)
                cleanup_stale()
            else:
                print("  ⚠ Stale socket detected, cleaning up...", file=sys.stderr)
                if SOCKET_FILE.exists():
                    SOCKET_FILE.unlink(missing_ok=True)
            print("✓ Stopped")
            return 0

        if wait_for_exit():
            print("✓ Stopped")
            return 0

        print("⚠ Process stuck, force stopping...", file=sys.stderr)
        cleanup_stale()
        print("✓ Stopped")
        return 0

    start_recording()
    return 0


if __name__ == "__main__":
    sys.exit(main())
