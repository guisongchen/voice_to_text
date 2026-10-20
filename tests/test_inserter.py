"""Tests for session-aware text insertion dispatch."""
from unittest.mock import patch, MagicMock

from voice_to_text.inserter import TextInserter


def _ok_run(*args, **kwargs):
    result = MagicMock()
    result.returncode = 0
    result.stdout = b""
    return result


WAYLAND_TOOLS = {"/usr/bin/xclip", "/usr/bin/ydotool"}


def _which(toolset):
    return lambda t: f"/usr/bin/{t}" if f"/usr/bin/{t}" in toolset else None


class TestInsertDispatch:
    def test_wayland_uses_xclip_bridge_plus_shift_insert(self):
        calls = []

        def spy_run(cmd, **kwargs):
            calls.append(cmd)
            return _ok_run()

        with patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"}), \
             patch("voice_to_text.inserter.shutil.which",
                   side_effect=_which(WAYLAND_TOOLS)), \
             patch("voice_to_text.inserter.subprocess.run", side_effect=spy_run), \
             patch("voice_to_text.inserter.time.sleep"):
            assert TextInserter.insert("你好世界") is True
        commands = [c[0].split("/")[-1] for c in calls]
        # xclip writes the text (clipboard + primary), then ydotool sends
        # Shift+Insert (raw keycodes 42/110)
        copy_idx = commands.index("xclip")
        key_calls = [i for i, c in enumerate(calls)
                     if "ydotool" in c[0] and c[1] == "key"]
        assert key_calls and "110:1" in calls[key_calls[0]]
        assert copy_idx < key_calls[0]
        writes = [c for c in calls
                  if "xclip" in c[0] and "-in" in c]
        selections = {c[c.index("-selection") + 1] for c in writes}
        assert selections == {"clipboard", "primary"}

    def test_wayland_clipboard_without_ydotool_falls_back_to_x11(self):
        # The Wayland bridge needs ydotool to send Shift+Insert, so
        # xclip alone is not enough.
        calls = []

        def spy_run(cmd, **kwargs):
            calls.append(cmd)
            return _ok_run()

        with patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"}), \
             patch("voice_to_text.inserter.shutil.which",
                   side_effect=_which({"/usr/bin/xclip"})), \
             patch("voice_to_text.inserter.subprocess.run", side_effect=spy_run), \
             patch("voice_to_text.inserter.time.sleep"):
            assert TextInserter.insert("hello") is True
        assert calls and "xclip" in calls[0][0]

    def test_x11_uses_clipboard_path(self):
        calls = []

        def spy_run(cmd, **kwargs):
            calls.append(cmd)
            return _ok_run()

        with patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"}), \
             patch("voice_to_text.inserter.shutil.which",
                   side_effect=_which({"/usr/bin/xclip"})), \
             patch("voice_to_text.inserter.subprocess.run", side_effect=spy_run), \
             patch("voice_to_text.inserter.time.sleep"):
            assert TextInserter.insert("hello") is True
        assert calls and "xclip" in calls[0][0]

    def test_wayland_without_any_tool_uses_xdotool_type(self):
        calls = []

        def spy_run(cmd, **kwargs):
            calls.append(cmd)
            return _ok_run()

        with patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"}), \
             patch("voice_to_text.inserter.shutil.which",
                   side_effect=_which(set())), \
             patch("voice_to_text.inserter.subprocess.run", side_effect=spy_run):
            assert TextInserter.insert("hello") is True
        assert calls and "xdotool" in calls[0][0]

    def test_empty_text_inserts_nothing(self):
        with patch("voice_to_text.inserter.subprocess.run") as mock_run:
            assert TextInserter.insert("   ") is False
        mock_run.assert_not_called()

    def test_ydotool_timeout_scales_with_text_length(self):
        seen_timeouts = []

        def spy_run(cmd, **kwargs):
            seen_timeouts.append(kwargs.get("timeout"))
            return _ok_run()

        with patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"}), \
             patch("voice_to_text.inserter.shutil.which",
                   side_effect=_which({"/usr/bin/ydotool"})), \
             patch("voice_to_text.inserter.subprocess.run", side_effect=spy_run):
            TextInserter.insert("短")
            TextInserter.insert("字" * 1000)
        assert seen_timeouts[1] > seen_timeouts[0]
