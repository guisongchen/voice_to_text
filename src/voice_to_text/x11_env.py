"""Shared X11 environment discovery for xdotool and related tools."""

import glob
import os


def get_x11_env():
    """Return an environment dict with DISPLAY and XAUTHORITY set.

    Used by both the TextInserter (package) and the LP998 listener (script)
    so the discovery logic lives in one place.

    XAUTHORITY is re-validated on every call: mutter runs Xwayland
    on-demand and regenerates the auth cookie file (new random suffix)
    every time Xwayland restarts. A long-running daemon therefore often
    holds a stale path inherited from systemd's environment snapshot —
    the variable exists but the file is gone, which makes xclip fail
    with "Authorization required". In that case re-glob for the current
    file (picking the newest match) instead of trusting the env var.
    """
    env = os.environ.copy()
    if "DISPLAY" not in env:
        env["DISPLAY"] = ":1"

    current = env.get("XAUTHORITY")
    if current and os.path.exists(current):
        return env

    uid = os.getuid()
    home = os.path.expanduser("~")
    candidates = [
        f"/run/user/{uid}/gdm/Xauthority",
        f"/run/user/{uid}/.mutter-Xwaylandauth.*",
        os.path.join(home, ".Xauthority"),
    ]
    for pattern in candidates:
        paths = glob.glob(pattern) if "*" in pattern else [pattern]
        paths = [p for p in paths if os.path.exists(p)]
        if paths:
            env["XAUTHORITY"] = max(paths, key=os.path.getmtime)
            return env

    # Nothing found: drop the stale pointer entirely so libX11 falls back
    # to its default lookup instead of a file that no longer exists.
    env.pop("XAUTHORITY", None)
    return env
