import shutil
import subprocess
import time

from .config import XDOTOOL_TIMEOUT, XDOTOOL_TYPE_DELAY_MS
from .x11_env import get_x11_env


class TextInserter:
    """Insert text at the cursor.

    Primary path: X11 clipboard (xclip/xsel) + Ctrl+V.  Pasting is atomic,
    so no characters are lost.  ``xdotool type`` is kept only as a fallback
    when no clipboard tool is installed — it is known to drop CJK
    characters because it synthesises them by remapping spare keycodes and
    reusing them for subsequent characters, racing with the receiving
    application.
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

        clip_tool = shutil.which("xclip") or shutil.which("xsel")
        if clip_tool:
            return TextInserter._insert_via_clipboard(text, env, clip_tool)

        print("  ⚠ No clipboard tool (xclip/xsel), falling back to xdotool type")
        return TextInserter._insert_via_xdotool(text, env)

    @staticmethod
    def _insert_via_xdotool(text, env):
        """Type text keystroke-by-keystroke (fallback; may drop CJK chars)."""
        try:
            subprocess.run(
                ['xdotool', 'type', '--clearmodifiers',
                 '--delay', str(XDOTOOL_TYPE_DELAY_MS), '--', text],
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
    def _clipboard_read(clip_tool, env):
        """Best-effort read of the current clipboard contents."""
        try:
            if "xclip" in clip_tool:
                cmd = [clip_tool, "-selection", "clipboard", "-out"]
            else:
                cmd = [clip_tool, "--clipboard", "--output"]
            result = subprocess.run(
                cmd, capture_output=True, timeout=2, env=env
            )
            return result.stdout if result.returncode == 0 else None
        except Exception:
            return None

    @staticmethod
    def _clipboard_write(clip_tool, data, env):
        if "xclip" in clip_tool:
            cmd = [clip_tool, "-selection", "clipboard", "-in"]
        else:
            cmd = [clip_tool, "--clipboard", "--input"]
        subprocess.run(cmd, input=data, check=True, timeout=5, env=env)

    @staticmethod
    def _insert_via_clipboard(text, env, clip_tool):
        """Paste text via the X11 clipboard, preserving its previous contents."""
        previous = TextInserter._clipboard_read(clip_tool, env)
        try:
            TextInserter._clipboard_write(clip_tool, text.encode("utf-8"), env)
            subprocess.run(
                ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
                check=True, timeout=XDOTOOL_TIMEOUT, env=env,
            )
            # Give the target application a moment to finish reading the
            # selection from the clipboard owner before restoring it.
            time.sleep(0.5)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"  ✗ Clipboard insertion failed: {e}, falling back to xdotool type")
            return TextInserter._insert_via_xdotool(text, env)
        finally:
            if previous is not None:
                try:
                    TextInserter._clipboard_write(clip_tool, previous, env)
                except Exception:
                    pass
