#!/usr/bin/env bash
# Voice-to-Text Toggle Script
# Use this script with desktop shortcuts to avoid input group requirement
# 
# Usage:
#   - First press: Starts recording in background
#   - Second press: Stops recording and transcribes
#
# No keyboard monitoring needed - uses PID file + signals

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="/tmp/voice_to_text.pid"

# Check if recording is already running
if [ -f "$PIDFILE" ]; then
    # PID file exists - stop recording
    PID=$(cat "$PIDFILE")
    
    # Check if process is actually running
    if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping recording (PID: $PID)..."
        kill -SIGUSR1 "$PID"
    else
        # Stale PID file
        echo "Removing stale PID file..."
        rm -f "$PIDFILE"
    fi
else
    # No PID file - start recording
    echo "Starting recording..."
    cd "$SCRIPT_DIR"
    
    # Start recording in background with PID file mode
    nohup uv run voice_to_text.py --record-once --use-pidfile > /tmp/voice_to_text.log 2>&1 &
    
    # Small delay to let it initialize
    sleep 0.5
    
    # Show notification if available
    if command -v notify-send &> /dev/null; then
        notify-send "Voice to Text" "Recording started - press Alt+R again to stop" -t 2000
    fi
fi
