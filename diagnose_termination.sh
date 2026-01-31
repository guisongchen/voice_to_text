#!/bin/bash
# Diagnostic script to help identify why the process isn't terminating

echo "=== Voice-to-Text Termination Diagnostic ==="
echo ""

# Clean up any existing processes/files
echo "Step 1: Cleaning up old processes and files..."
rm -f /tmp/voice_to_text.pid /tmp/voice_to_text.log
pkill -f "voice_to_text.py --record-once --use-pidfile" 2>/dev/null || true
sleep 1

# Start the process
echo ""
echo "Step 2: Starting recording with toggle script..."
./voice_to_text_toggle.sh

# Wait for initialization
echo "Waiting 5 seconds for initialization..."
sleep 5

# Check if PID file was created
echo ""
echo "Step 3: Checking PID file..."
if [ -f /tmp/voice_to_text.pid ]; then
    PID=$(cat /tmp/voice_to_text.pid)
    echo "✓ PID file exists: $PID"
    
    # Check if process is running
    if ps -p $PID > /dev/null 2>&1; then
        echo "✓ Process is running"
        
        # Show process info
        echo ""
        echo "Process info:"
        ps aux | grep $PID | grep -v grep
    else
        echo "✗ Process not running (stale PID file)"
    fi
else
    echo "✗ PID file not found"
    echo ""
    echo "Checking for any running voice_to_text processes:"
    ps aux | grep "voice_to_text.py" | grep -v grep
fi

# Show log if it exists
echo ""
echo "Step 4: Checking log file..."
if [ -f /tmp/voice_to_text.log ]; then
    echo "Last 30 lines of log (filtered):"
    tail -30 /tmp/voice_to_text.log | grep -v "ALSA\|jack\|Jack\|Cannot connect"
else
    echo "✗ Log file not found"
fi

# Prompt to test stopping
echo ""
echo "=======================" 
echo "Now testing stop signal..."
echo "Press Enter to send stop signal (or Ctrl+C to abort)"
read

# Stop the recording
echo "Sending stop signal..."
./voice_to_text_toggle.sh

# Wait and monitor
echo "Waiting 15 seconds for transcription and cleanup..."
sleep 15

# Check if process terminated
echo ""
echo "Step 5: Checking if process terminated..."
if [ -f /tmp/voice_to_text.pid ]; then
    echo "✗ PID file still exists (process may be hung)"
    PID=$(cat /tmp/voice_to_text.pid)
    
    if ps -p $PID > /dev/null 2>&1; then
        echo "✗ Process still running: $PID"
        echo ""
        echo "Process status:"
        ps aux | grep $PID | grep -v grep
        echo ""
        echo "Thread info:"
        ps -T -p $PID 2>/dev/null || echo "  (thread info not available)"
    else
        echo "  Process exited but PID file not cleaned up"
        rm -f /tmp/voice_to_text.pid
    fi
else
    echo "✓ PID file removed (process should have exited)"
    
    # Double-check no processes running
    RUNNING=$(ps aux | grep "voice_to_text.py --record-once --use-pidfile" | grep -v grep | wc -l)
    if [ $RUNNING -eq 0 ]; then
        echo "✓ No voice_to_text processes running"
    else
        echo "✗ Found $RUNNING running processes:"
        ps aux | grep "voice_to_text.py" | grep -v grep
    fi
fi

# Show final log
echo ""
echo "Step 6: Final log output..."
if [ -f /tmp/voice_to_text.log ]; then
    echo "Last 50 lines (filtered):"
    tail -50 /tmp/voice_to_text.log | grep -v "ALSA\|jack\|Jack\|Cannot connect"
else
    echo "✗ Log file not found"
fi

echo ""
echo "=== Diagnostic Complete ==="
echo ""
echo "If the process is still running, you can kill it with:"
echo "  kill -9 <PID>"
echo ""
echo "Please share the output above to help debug the issue."
