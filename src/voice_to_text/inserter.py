import shutil
import subprocess

from .config import XDOTOOL_TIMEOUT, CLIPBOARD_THRESHOLD
from .x11_env import get_x11_env


class TextInserter:
    """Insert text using xdotool.

    Short text is typed directly via ``xdotool type``.  Text longer than
    CLIPBOARD_THRESHOLD characters is inserted via the X11 clipboard
    (xclip / xsel + Ctrl+V) to avoid command-line length limits and
    xdotool's per-keystroke overhead.
    """

    @staticmethod
    def check_xdotool():
        try:
            result = subprocess.run(
                ['xdotool', 'version'],
                capture_output=True, timeout=2,
                env=get_x11_env()
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def insert(text):
        if not text or not text.strip():
            print("  (No text to insert)")
            return False

        env = get_x11_env()

        if len(text) > CLIPBOARD_THRESHOLD:
            return TextInserter._insert_via_clipboard(text, env)
        return TextInserter._insert_via_xdotool(text, env)

    @staticmethod
    def _insert_via_xdotool(text, env):
        try:
            subprocess.run(
                ['xdotool', 'type', '--clearmodifiers', '--', text],
                check=True,
                timeout=XDOTOOL_TIMEOUT,
                env=env
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"  ✗ Error inserting text: {e}")
            return False
        except subprocess.TimeoutExpired:
            print("  ✗ Error: xdotool timed out")
            return False

    @staticmethod
    def _insert_via_clipboard(text, env):
        """Insert long text via X11 clipboard (xclip or xsel + Ctrl+V)."""
        clip_tool = shutil.which("xclip") or shutil.which("xsel")
        if not clip_tool:
            # Fall back to xdotool type even for long text.
            print("  ⚠ No clipboard tool (xclip/xsel), using xdotool type")
            return TextInserter._insert_via_xdotool(text, env)

        try:
            if "xclip" in clip_tool:
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text.encode("utf-8"),
                    check=True, timeout=5, env=env,
                )
            else:
                subprocess.run(
                    ["xsel", "--clipboard", "--input"],
                    input=text.encode("utf-8"),
                    check=True, timeout=5, env=env,
                )
            subprocess.run(
                ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
                check=True, timeout=XDOTOOL_TIMEOUT, env=env,
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"  ✗ Clipboard insertion failed: {e}, falling back to xdotool type")
            return TextInserter._insert_via_xdotool(text, env)
