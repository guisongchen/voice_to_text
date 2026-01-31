#!/bin/bash
# Test signal-based stopping

cd /home/ccc/vibe_projects/audio_recorder

echo "Cleaning up old files..."
rm -f /tmp/voice_to_text.pid /tmp/voice_to_text.log

echo "Starting recording in background..."
nohup uv run voice_to_text.py --record-once --use-pidfile > /tmp/voice_to_text.log 2>&1 &

echo "Waiting 5 seconds for recording to start..."
sleep 5

if [ -f /tmp/voice_to_text.pid ]; then
    SAVED_PID=$(cat /tmp/voice_to_text.pid)
    echo "PID file contains: $SAVED_PID"
    
    # Send signal to stop
    echo "Sending SIGUSR1 signal..."
    /bin/kill -SIGUSR1 $SAVED_PID
    
    # Wait for process to finish
    echo "Waiting for transcription..."
    sleep 10
    
    echo ""
    echo "=== Log output (last 40 lines) ==="
    tail -40 /tmp/voice_to_text.log | grep -v "ALSA\|jack\|Jack\|Cannot connect"
else
    echo "ERROR: PID file not created"
    echo "Log output:"
    cat /tmp/voice_to_text.log 2>/dev/null || echo "No log file"
fi
