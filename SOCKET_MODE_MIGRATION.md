# Socket Mode Migration

## Summary
Migrated from PID file + SIGUSR1 signal IPC to Unix domain socket for safer inter-process communication.

## What Changed

### 1. New Socket Mode Implementation
- **File**: [voice_to_text/modes/socket_mode.py](voice_to_text/modes/socket_mode.py)
  - Uses Unix domain socket (`/tmp/voice_to_text.sock`) instead of PID file
  - Reliable ACK mechanism confirms stop command receipt
  - Automatic cleanup of stale socket files

### 2. Updated Toggle Scripts
- **Bash**: [voice_to_text_toggle.sh](voice_to_text_toggle.sh)
  - Now checks for socket file instead of PID file
  - Sends "STOP" command via socket instead of SIGUSR1 signal
  
- **Python**: [voice_to_text_socket_toggle.py](voice_to_text_socket_toggle.py) (NEW)
  - Pure Python implementation for better reliability
  - Proper timeout handling and error messages
  - Recommended for desktop shortcuts

### 3. Updated Dependencies
- [voice_to_text/modes/__init__.py](voice_to_text/modes/__init__.py): Export SocketMode
- [voice_to_text/services/dependency_container.py](voice_to_text/services/dependency_container.py): Use SocketMode by default

## Benefits Over PID File + SIGUSR1

### Security & Reliability
✅ **No PID reuse vulnerability** - Socket files don't suffer from PID reuse issues  
✅ **Stale file detection** - Connection attempts fail cleanly on stale sockets  
✅ **ACK mechanism** - Confirms stop command was received  
✅ **Better error handling** - Clear error messages instead of silent failures  

### Robustness
✅ **No signal loss** - Socket messages are queued, signals can be lost  
✅ **Atomic operations** - Socket bind is atomic, prevents race conditions  
✅ **Clean shutdown** - Reliable two-way communication ensures proper cleanup  

## Usage

### Desktop Shortcut (GNOME)
Use the Python toggle script for better reliability:

```bash
/home/ccc/vibe_projects/voice_to_text/voice_to_text_socket_toggle.py
```

### Command Line
```bash
# Start recording (both methods work)
./voice_to_text_toggle.sh
# OR
./voice_to_text_socket_toggle.py

# Stop recording (run same command again)
./voice_to_text_toggle.sh
# OR
./voice_to_text_socket_toggle.py
```

## Technical Details

### Socket Protocol
- **Socket path**: `/tmp/voice_to_text.sock`
- **Type**: Unix domain socket (SOCK_STREAM)
- **Command**: Client sends `STOP\n`
- **Response**: Server responds with `ACK\n`

### Thread Safety
- Socket listener runs in daemon thread
- Non-blocking with 1-second timeout
- Proper synchronization with main recording loop

### Cleanup
- Socket file removed on normal exit
- Stale sockets cleaned up on next start
- Works correctly with Ctrl+C interruption

## Migration Notes

The old PID file mode ([pid_file_mode.py](voice_to_text/modes/pid_file_mode.py)) is still available but no longer used by default. All new instances use socket mode automatically.

### If You Need the Old Behavior
Modify [dependency_container.py](voice_to_text/services/dependency_container.py) to return `PidFileMode` instead of `SocketMode`.

## Testing

Test the implementation:

```bash
# Terminal 1: Start recording
./voice_to_text_socket_toggle.py

# Terminal 2: Check socket exists
ls -la /tmp/voice_to_text.sock

# Terminal 2: Stop recording
./voice_to_text_socket_toggle.py

# Verify cleanup
ls -la /tmp/voice_to_text.sock  # Should not exist
```
