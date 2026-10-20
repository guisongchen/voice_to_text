"""Tests for AudioOutputController sink parsing and mute/restore logic."""
from unittest.mock import patch, MagicMock

import pytest

from voice_to_text.audio_control import AudioOutputController, _SinkState


# ---------------------------------------------------------------------------
# Sample command outputs
# ---------------------------------------------------------------------------

PACTL_OUTPUT = """\
Sink #69
\tState: RUNNING
\tName: alsa_output.usb-Device-00.analog-stereo
\tDescription: USB Audio Analog Stereo
\tMute: no
\tVolume: front-left: 65536 / 100%
Sink #72
\tState: SUSPENDED
\tName: bluez_sink.5C_08_19_C2_4D_AF.a2dp_sink
\tDescription: LP998
\tMute: yes
\tVolume: front-left: 32768 /  50%
"""

# wpctl status output — the parser looks for a line that strips to "Sinks:"
# and then reads lines starting with " │" or "*" until another section.
WPCTL_OUTPUT = """\
PipeWire 'pipewire-0' [1.2.0, ccc@host, cookie:123]
 └─ Clients:
        33. xdg-desktop-portal

Audio
 Sinks:
 │      52. HDA NVidia Digital Stereo (HDMI)    [vol: 0.00 MUTED]
 │  *   85. HUAWEI FreeGO                       [vol: 0.33]
 │
 Sources:
 │  *   60. Built-in Audio Analog Stereo        [vol: 0.67]
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPactlParsing:
    def test_parse_sinks(self):
        ctrl = AudioOutputController(preferred_tool="pactl")
        with patch.object(ctrl, "_run", return_value=PACTL_OUTPUT):
            sinks = ctrl._list_sinks_pactl()

        assert len(sinks) == 2
        assert sinks[0] == _SinkState("alsa_output.usb-Device-00.analog-stereo", False)
        assert sinks[1] == _SinkState("bluez_sink.5C_08_19_C2_4D_AF.a2dp_sink", True)

    def test_empty_output(self):
        ctrl = AudioOutputController(preferred_tool="pactl")
        with patch.object(ctrl, "_run", return_value=""):
            sinks = ctrl._list_sinks_pactl()
        assert sinks == []


class TestWpctlParsing:
    def test_parse_sinks(self):
        ctrl = AudioOutputController(preferred_tool="wpctl")
        with patch.object(ctrl, "_run", return_value=WPCTL_OUTPUT):
            sinks = ctrl._list_sinks_wpctl()

        assert len(sinks) == 2
        assert sinks[0].identifier == "52"
        assert sinks[0].muted is True
        assert sinks[1].identifier == "85"
        assert sinks[1].muted is False

    def test_empty_output(self):
        ctrl = AudioOutputController(preferred_tool="wpctl")
        with patch.object(ctrl, "_run", return_value=""):
            sinks = ctrl._list_sinks_wpctl()
        assert sinks == []


class TestSaveMuteRestore:
    def test_save_and_mute_then_restore(self):
        ctrl = AudioOutputController(preferred_tool="pactl")
        calls = []

        def fake_run(cmd):
            calls.append(cmd)
            if cmd == ["pactl", "list", "sinks"]:
                return PACTL_OUTPUT
            return ""

        with patch.object(ctrl, "_run", side_effect=fake_run):
            assert ctrl.save_and_mute() is True
            assert ctrl.is_active() is True

            # Should have muted both sinks.
            mute_calls = [c for c in calls if "set-sink-mute" in c]
            assert len(mute_calls) == 2
            assert mute_calls[0][-1] == "1"  # muted
            assert mute_calls[1][-1] == "1"

            # Restore should set original states.
            calls.clear()
            assert ctrl.restore() is True
            restore_calls = [c for c in calls if "set-sink-mute" in c]
            assert len(restore_calls) == 2
            assert restore_calls[0][-1] == "0"  # was not muted
            assert restore_calls[1][-1] == "1"  # was muted

            assert ctrl.is_active() is False

    def test_restore_idempotent(self):
        ctrl = AudioOutputController(preferred_tool="pactl")
        # Not active — restore should return False.
        assert ctrl.restore() is False

    def test_double_mute_is_noop(self):
        ctrl = AudioOutputController(preferred_tool="pactl")
        with patch.object(ctrl, "_run", return_value=PACTL_OUTPUT):
            assert ctrl.save_and_mute() is True
            # Second call should be a no-op (already active).
            assert ctrl.save_and_mute() is True

    def test_no_tool_returns_false(self):
        ctrl = AudioOutputController(preferred_tool=None)
        ctrl._tool = None
        assert ctrl.save_and_mute() is False


class TestAmixerParsing:
    def test_finds_master(self):
        ctrl = AudioOutputController(preferred_tool="amixer")
        output = "Simple mixer control 'Master',0\nSimple mixer control 'Capture',0\n"
        with patch.object(ctrl, "_run", return_value=output):
            sinks = ctrl._list_sinks_amixer()
        assert len(sinks) == 1
        assert sinks[0].identifier == "Master"

    def test_no_master(self):
        ctrl = AudioOutputController(preferred_tool="amixer")
        output = "Simple mixer control 'Capture',0\n"
        with patch.object(ctrl, "_run", return_value=output):
            sinks = ctrl._list_sinks_amixer()
        assert sinks == []
