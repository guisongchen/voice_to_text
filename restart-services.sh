#!/bin/bash
set -euo pipefail

PROJECT_DIR="$HOME/projects/voice_to_text"
PYTHON="$PROJECT_DIR/.venv/bin/python3"
SOCKET="/tmp/voice_to_text.sock"
LOG_FILE="/tmp/voice_to_text.log"
STARTING_MARKER="/tmp/voice_to_text.starting"

# ── Helpers ───────────────────────────────────────────────────────────────────

cleanup_stale() {
    # Remove stale socket
    if [ -S "$SOCKET" ]; then
        echo "  Cleaning up stale socket: $SOCKET"
        rm -f "$SOCKET"
    fi
    rm -f "$STARTING_MARKER"

    # Kill any lingering voice_to_text daemon processes
    local pids
    pids=$(pgrep -af "voice.to.text" 2>/dev/null \
        | grep -v "voice-to-text-t\|toggle\|listener\|grep\|bash" \
        | awk '{print $1}' || true)
    if [ -n "$pids" ]; then
        echo "  Killing stale daemon process(es): $pids"
        echo "$pids" | xargs -r kill -9
        sleep 0.3
    fi
}

# ── 1. Core Daemon ────────────────────────────────────────────────────────────

echo "=== Restarting Core Voice-to-Text Daemon ==="

cleanup_stale

export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export HF_DATASETS_OFFLINE=1

nohup "$PYTHON" -m voice_to_text --start-recording \
    > "$LOG_FILE" 2>&1 &

DAEMON_PID=$!
echo "  Daemon started (PID: $DAEMON_PID)"

# Wait for socket to appear
for i in $(seq 1 20); do
    if [ -S "$SOCKET" ]; then
        echo "✓ Core daemon ready (socket: $SOCKET)"
        break
    fi
    sleep 0.5
done

if [ ! -S "$SOCKET" ]; then
    echo "✗ Core daemon failed to start within 10s"
fi

# ── 2. LP998 Listener ─────────────────────────────────────────────────────────

echo ""
echo "=== Restarting LP998 Listener ==="

systemctl --user restart lp998-listener

sleep 1

if systemctl --user is-active --quiet lp998-listener; then
    echo "✓ LP998 listener is active"
else
    echo "✗ LP998 listener failed to start"
    systemctl --user status lp998-listener --no-pager -l | tail -5
fi

echo ""
echo "=== Done ==="
echo "Daemon log: $LOG_FILE"
echo "Journal:    journalctl --user -fu lp998-listener"
