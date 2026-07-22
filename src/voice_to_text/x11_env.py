"""Shared X11 environment discovery for xdotool and related tools."""

import glob
import os


def get_x11_env():
    """Return an environment dict with DISPLAY and XAUTHORITY set.

    Used by both the TextInserter (package) and the LP998 listener (script)
    so the discovery logic lives in one place.
    """
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
