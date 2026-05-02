import glob
import os
import subprocess
import time

from .config import XDOTOOL_TIMEOUT


class TextInserter:
    """Insert text using xdotool."""

    @staticmethod
    def _get_x11_env():
        env = os.environ.copy()
        if "DISPLAY" not in env:
            env["DISPLAY"] = ":1"
        if "XAUTHORITY" not in env:
            uid = os.getuid()
            home = os.path.expanduser("~")
            candidates = [
                f"/run/user/{uid}/gdm/Xauthority",
                f"/run/user/{uid}/.mutter-Xwaylandauth.*",
                os.path.join(home, ".Xauthority"),
            ]
            for pattern in candidates:
                paths = glob.glob(pattern) if "*" in pattern else [pattern]
                for path in paths:
                    if os.path.exists(path):
                        env["XAUTHORITY"] = path
                        break
                if "XAUTHORITY" in env:
                    break
        return env

    @staticmethod
    def check_xdotool():
        try:
            result = subprocess.run(
                ['xdotool', 'version'],
                capture_output=True, timeout=2,
                env=TextInserter._get_x11_env()
            )
            return result.returncode == 0
        except:
            return False

    @staticmethod
    def get_active_window():
        try:
            result = subprocess.run(
                ['xdotool', 'getactivewindow'],
                capture_output=True, text=True, timeout=2,
                env=TextInserter._get_x11_env()
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    @staticmethod
    def insert(text, window_id=None):
        if not text or not text.strip():
            print("  (No text to insert)")
            return False

        env = TextInserter._get_x11_env()

        try:
            if window_id:
                subprocess.run(
                    ['xdotool', 'windowfocus', window_id],
                    env=env, timeout=2, check=False
                )
                time.sleep(0.05)

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
