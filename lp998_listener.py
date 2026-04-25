#!/usr/bin/env python3
"""LP998 touch zone listener daemon.

Maps UGREEN-LP998 touch zones to keyboard shortcuts via xdotool.
The LP998 is a Bluetooth presenter remote with a touchpad-based ring
(5 touch zones) plus 2 physical buttons at the bottom.

Both the touchpad and Consumer Control evdev devices are grabbed so
the system (desktop environment) cannot intercept button events.
"""

import argparse
import glob
import math
import os
import subprocess
import sys
import threading
import time

from evdev import InputDevice, ecodes, list_devices

MAC = "5C:08:19:C2:4D:AF"
DEVICE_NAME_PATTERN = "LP998"

ZONE_THRESHOLD = 75
TOUCH_DEBOUNCE_SECONDS = 0.12
CC_DEBOUNCE_SECONDS = 0.2

ZONES = [
    {"name": "ring_top",    "center": (500, 350), "cmd": ["xdotool", "key", "Up"],             "desc": "Ring Top -> Up"},
    {"name": "ring_bottom", "center": (500, 620), "cmd": ["xdotool", "key", "Down"],           "desc": "Ring Bottom -> Down"},
    {"name": "ring_left",   "center": (300, 292), "cmd": ["xdotool", "key", "Left"],           "desc": "Ring Left -> Left"},
    {"name": "ring_right",  "center": (700, 297), "cmd": ["xdotool", "key", "Right"],          "desc": "Ring Right -> Right"},
    {"name": "ring_center", "center": (500, 400), "cmd": ["xdotool", "key", "alt+shift+r"],    "desc": "Ring Center -> Alt+Shift+R"},
    {"name": "left_button", "center": (512, 833), "cmd": ["xdotool", "key", "BackSpace"],      "desc": "Left Button -> Backspace"},
]

CC_KEY_MAP = {
    114: (["xdotool", "key", "Return"], "Right Button -> Enter", "right_button"),
    115: (["xdotool", "key", "Return"], "Right Button -> Enter", "right_button"),
}

ACTION_LAST_INJECTED_AT = {}
ACTION_DEBOUNCE_LOCK = threading.Lock()


def find_lp998_devices():
    """Find LP998 input devices by name pattern.

    Returns: (touch_device, cc_devices) where cc_devices is a list (may be empty).
    """
    touch_dev = None
    cc_devices = []
    for path in list_devices():
        try:
            dev = InputDevice(path)
            if DEVICE_NAME_PATTERN not in dev.name:
                continue
            if "Consumer Control" in dev.name:
                cc_devices.append(dev)
            elif "Consumer" not in dev.name:
                touch_dev = dev
        except Exception:
            continue
    return touch_dev, cc_devices


def is_connected():
    """Check if LP998 is connected via BlueZ D-Bus."""
    result = subprocess.run(
        [
            "dbus-send", "--system", "--dest=org.bluez", "--type=method_call",
            "--print-reply", f"/org/bluez/hci0/dev_{MAC.replace(':', '_')}",
            "org.freedesktop.DBus.Properties.Get",
            "string:org.bluez.Device1", "string:Connected",
        ],
        capture_output=True,
        text=True,
    )
    return "boolean true" in result.stdout


def get_x11_env():
    """Discover X11 environment for xdotool."""
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


def inject_keys(cmd, description):
    """Run xdotool to inject a key sequence (non-blocking)."""
    env = get_x11_env()
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    print(f"Injected: {description}")


def debounce_action(debounce_key, debounce_seconds):
    """Return elapsed time if action should be suppressed, else None."""
    now = time.monotonic()
    with ACTION_DEBOUNCE_LOCK:
        previous = ACTION_LAST_INJECTED_AT.get(debounce_key)
        if previous is not None and now - previous < debounce_seconds:
            return now - previous
        ACTION_LAST_INJECTED_AT[debounce_key] = now
    return None


def match_zone(x, y):
    """Find closest matching zone by Euclidean distance."""
    best = None
    best_dist = ZONE_THRESHOLD
    for z in ZONES:
        cx, cy = z["center"]
        d = math.hypot(x - cx, y - cy)
        if d < best_dist:
            best_dist = d
            best = z
    return best, best_dist


def consume_cc_events(device, debug=False):
    """Handle mapped Consumer Control events and discard the rest."""
    try:
        for event in device.read_loop():
            if event.type != ecodes.EV_KEY:
                continue

            key_name = ecodes.KEY.get(event.code, f"KEY_{event.code}")
            if debug:
                print(f"[debug] CC consumed: {key_name} (code={event.code}, val={event.value})")

            if event.value != 1:
                continue

            mapping = CC_KEY_MAP.get(event.code)
            if mapping:
                cmd, description, debounce_key = mapping
                elapsed = debounce_action(debounce_key, CC_DEBOUNCE_SECONDS)
                if elapsed is not None:
                    if debug:
                        print(
                            f"[debug] CC suppressed: {description} "
                            f"(code={event.code}, dt={elapsed:.3f}s)"
                        )
                    continue
                inject_keys(cmd, description)
    except OSError:
        pass


def listen_touch_events(device, debug=False):
    """Process touch events, tracking multi-touch sessions."""
    def empty_touch():
        return {
            "x_sum": 0,
            "y_sum": 0,
            "xc": 0,
            "yc": 0,
            "first_x": None,
            "first_y": None,
            "last_x": None,
            "last_y": None,
            "min_x": None,
            "max_x": None,
            "min_y": None,
            "max_y": None,
        }

    last_touch_x = None
    last_touch_y = None
    tracking_active = False
    cur = empty_touch()

    for event in device.read_loop():
        if event.type != ecodes.EV_ABS:
            continue

        if event.code == ecodes.ABS_MT_TRACKING_ID:
            if event.value == -1:
                if tracking_active:
                    avg_x = cur["x_sum"] / cur["xc"] if cur["xc"] > 0 else last_touch_x
                    avg_y = cur["y_sum"] / cur["yc"] if cur["yc"] > 0 else last_touch_y
                    touch_x = cur["first_x"] if cur["first_x"] is not None else avg_x
                    touch_y = cur["first_y"] if cur["first_y"] is not None else avg_y

                    if touch_x is not None and touch_y is not None:
                        zone, dist = match_zone(touch_x, touch_y)
                        if zone:
                            elapsed = debounce_action(zone["name"], TOUCH_DEBOUNCE_SECONDS)
                            if elapsed is not None:
                                if debug:
                                    print(
                                        f"[debug] Touch suppressed: {zone['name']} "
                                        f"(dt={elapsed:.3f}s)"
                                    )
                                tracking_active = False
                                cur = empty_touch()
                                continue
                            if debug:
                                print(
                                    "[debug] Matched touch: "
                                    f"X={touch_x:.0f}, Y={touch_y:.0f} -> {zone['name']} "
                                    f"(center={zone['center']}, dist={dist:.1f}, "
                                    f"avg=({avg_x:.0f},{avg_y:.0f}), "
                                    f"first=({cur['first_x']},{cur['first_y']}), "
                                    f"last=({cur['last_x']},{cur['last_y']}), "
                                    f"x_seen={cur['xc']}, y_seen={cur['yc']}, "
                                    f"x_range=({cur['min_x']},{cur['max_x']}), "
                                    f"y_range=({cur['min_y']},{cur['max_y']}))"
                                )
                            inject_keys(zone["cmd"], zone["desc"])
                        elif debug:
                            print(
                                "[debug] Unknown touch: "
                                f"X={touch_x:.0f}, Y={touch_y:.0f}, "
                                f"avg=({avg_x:.0f},{avg_y:.0f}), "
                                f"first=({cur['first_x']},{cur['first_y']}), "
                                f"last=({cur['last_x']},{cur['last_y']}), "
                                f"x_seen={cur['xc']}, y_seen={cur['yc']}, "
                                f"x_range=({cur['min_x']},{cur['max_x']}), "
                                f"y_range=({cur['min_y']},{cur['max_y']})"
                            )

                tracking_active = False
                cur = empty_touch()
            else:
                tracking_active = True
                cur = empty_touch()

        elif event.code == ecodes.ABS_MT_POSITION_X:
            cur["x_sum"] += event.value
            cur["xc"] += 1
            last_touch_x = event.value
            if cur["first_x"] is None:
                cur["first_x"] = event.value
            cur["last_x"] = event.value
            cur["min_x"] = event.value if cur["min_x"] is None else min(cur["min_x"], event.value)
            cur["max_x"] = event.value if cur["max_x"] is None else max(cur["max_x"], event.value)
        elif event.code == ecodes.ABS_MT_POSITION_Y:
            cur["y_sum"] += event.value
            cur["yc"] += 1
            last_touch_y = event.value
            if cur["first_y"] is None:
                cur["first_y"] = event.value
            cur["last_y"] = event.value
            cur["min_y"] = event.value if cur["min_y"] is None else min(cur["min_y"], event.value)
            cur["max_y"] = event.value if cur["max_y"] is None else max(cur["max_y"], event.value)


def grab_device(dev, name):
    """Try to grab an evdev device, return True on success."""
    try:
        dev.grab()
        print(f"Grabbed {name} ({dev.path})")
        return True
    except PermissionError:
        print(
            f"ERROR: Permission denied for {name}. Fix: sudo usermod -aG input $USER",
            file=sys.stderr,
        )
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Map LP998 touch zones to keyboard shortcuts"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Print every touch event received"
    )
    args = parser.parse_args()

    if not is_connected():
        print("ERROR: LP998 is not connected via Bluetooth.", file=sys.stderr)
        return 1

    reconnects = 0
    MAX_RECONNECTS = 5

    while True:
        print("Looking for LP998 input devices...")
        touch_dev = None
        cc_devices = []
        for attempt in range(10):
            touch_dev, cc_devices = find_lp998_devices()
            if touch_dev:
                break
            print(f"  Not found, retrying ({attempt + 1}/10)...")
            time.sleep(2)

        if not touch_dev:
            print("ERROR: LP998 touch device not found.", file=sys.stderr)
            return 1

        print(f"Found touch: {touch_dev.name} at {touch_dev.path}")
        for cc_dev in cc_devices:
            print(f"Found CC:    {cc_dev.name} at {cc_dev.path}")

        if not grab_device(touch_dev, "touch device"):
            return 1

        # Grab and consume Consumer Control events so the system ignores them
        cc_threads = []
        for cc_dev in cc_devices:
            if grab_device(cc_dev, "Consumer Control device"):
                t = threading.Thread(
                    target=consume_cc_events, args=(cc_dev, args.debug), daemon=True
                )
                t.start()
                cc_threads.append(t)

        print("Listening for touch events...")
        for z in ZONES:
            print(f"  {z['desc']}")

        try:
            listen_touch_events(touch_dev, debug=args.debug)
        except OSError as e:
            reconnects += 1
            if reconnects > MAX_RECONNECTS:
                print(f"Device disconnected {MAX_RECONNECTS} times, giving up.", file=sys.stderr)
                try:
                    touch_dev.ungrab()
                except Exception:
                    pass
                for cc_dev in cc_devices:
                    try:
                        cc_dev.ungrab()
                    except Exception:
                        pass
                touch_dev.close()
                for cc_dev in cc_devices:
                    cc_dev.close()
                return 1
            print(f"Device disconnected ({e}), retrying ({reconnects}/{MAX_RECONNECTS})...")
            try:
                touch_dev.ungrab()
            except Exception:
                pass
            for cc_dev in cc_devices:
                try:
                    cc_dev.ungrab()
                except Exception:
                    pass
            touch_dev.close()
            for cc_dev in cc_devices:
                cc_dev.close()
            time.sleep(5)
            continue
        except KeyboardInterrupt:
            print("\nExiting.")
            try:
                touch_dev.ungrab()
            except Exception:
                pass
            for cc_dev in cc_devices:
                try:
                    cc_dev.ungrab()
                except Exception:
                    pass
            touch_dev.close()
            for cc_dev in cc_devices:
                cc_dev.close()
            return 0


if __name__ == "__main__":
    sys.exit(main())
