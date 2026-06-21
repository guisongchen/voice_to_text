#!/bin/bash
set -euo pipefail

# ── Restart all voice-to-text related systemd user services ───────────────────

echo "=== Restarting ASRCore + Voice-to-Text Services ==="

systemctl --user restart asr-core
systemctl --user restart voice-to-text
systemctl --user restart lp998-listener

sleep 1

for svc in asr-core voice-to-text lp998-listener; do
    if systemctl --user is-active --quiet "$svc"; then
        echo "✓ $svc is active"
    else
        echo "✗ $svc failed to start"
        systemctl --user status "$svc" --no-pager -l | tail -5
    fi
done

echo ""
echo "=== Done ==="
echo "ASRCore socket: /tmp/asr_core.sock"
echo "Voice socket:   /tmp/voice_to_text.sock"
echo "Journal:        journalctl --user -fu asr-core -u voice-to-text -u lp998-listener"
