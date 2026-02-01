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
SOCKET_FILE="/tmp/voice_to_text.sock"

# Check if recording is already running
if [ -S "$SOCKET_FILE" ]; then
    # Socket exists - send stop command via socket
    echo "Stopping recording..."
    echo "STOP" | nc -U "$SOCKET_FILE" 2>/dev/null || {
        # If nc fails, try Python method
        python3 -c "import socket; s=socket.socket(socket.AF_UNIX); s.connect('$SOCKET_FILE'); s.sendall(b'STOP\n'); print(s.recv(1024)); s.close()"
    }
else
    # No socket - start recording
    echo "Starting recording..."
    cd "$SCRIPT_DIR"
    
    # Start recording in background (uses socket mode for safer IPC)
    nohup uv run voice-to-text > /tmp/voice_to_text.log 2>&1 &
    
    # Small delay to let it initialize
    sleep 0.5
    
    # Show notification if available
    if command -v notify-send &> /dev/null; then
        notify-send "Voice to Text" "Recording started - press Alt+R again to stop" -t 2000
    fi
fi
