"""Tests for the VoiceToTextService state machine logic.

We test the state machine in isolation by constructing a service object
with mocked-out I/O dependencies (recorder, ASR client, audio controller).
"""
import time
import threading
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers to build a service with all heavy dependencies mocked out.
# ---------------------------------------------------------------------------

def _make_service():
    """Create a VoiceToTextService with mocked I/O dependencies."""
    with patch("voice_to_text.service.ASRCoreClient") as mock_asr, \
         patch("voice_to_text.service.AudioRecorder") as mock_rec, \
         patch("voice_to_text.service.AudioOutputController") as mock_audio:
        mock_asr.return_value = MagicMock()
        mock_rec.return_value = MagicMock()
        mock_audio.return_value = MagicMock()

        from voice_to_text.service import VoiceToTextService
        svc = VoiceToTextService()
    return svc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStateTransitions:
    def test_initial_state_is_idle(self):
        svc = _make_service()
        assert svc._state == "idle"

    def test_try_transition_success(self):
        svc = _make_service()
        assert svc._try_transition("idle", "recording") is True
        assert svc._state == "recording"

    def test_try_transition_wrong_source(self):
        svc = _make_service()
        # State is idle, not recording — should fail.
        assert svc._try_transition("recording", "transcribing") is False
        assert svc._state == "idle"

    def test_try_transition_bounce_guard(self):
        svc = _make_service()
        assert svc._try_transition("idle", "recording") is True
        # Immediate second transition should be rejected (bounce guard).
        assert svc._try_transition("recording", "transcribing") is False
        assert svc._state == "recording"

    def test_try_transition_after_bounce_interval(self):
        svc = _make_service()
        assert svc._try_transition("idle", "recording") is True
        # Simulate passage of time beyond MIN_TRANSITION_INTERVAL.
        with svc._lock:
            svc._last_transition = time.monotonic() - 1.0
        assert svc._try_transition("recording", "transcribing") is True
        assert svc._state == "transcribing"

    def test_force_transition_overrides(self):
        svc = _make_service()
        svc._force_transition("transcribing")
        assert svc._state == "transcribing"
        svc._force_transition("idle")
        assert svc._state == "idle"

    def test_handle_toggle_from_idle(self):
        svc = _make_service()
        result = svc._handle_toggle()
        assert result == "STARTED"
        # State should be recording (set by _try_transition before thread starts).
        assert svc._state == "recording"

    def test_handle_toggle_busy_during_transcribing(self):
        svc = _make_service()
        svc._force_transition("transcribing")
        # Allow bounce interval to pass.
        with svc._lock:
            svc._last_transition = time.monotonic() - 1.0
        result = svc._handle_toggle()
        assert result == "BUSY"


class TestShouldExit:
    def test_property_thread_safe(self):
        svc = _make_service()
        assert svc.should_exit is False
        svc.should_exit = True
        assert svc.should_exit is True

    def test_request_shutdown_sets_flag(self):
        svc = _make_service()
        svc._request_shutdown()
        assert svc.should_exit is True
