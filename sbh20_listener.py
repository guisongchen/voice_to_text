#!/usr/bin/env python3
"""SBH20 button listener daemon.

Maps SBH20 Bluetooth headset buttons to keyboard shortcuts via xdotool:
  - Play/Pause  -> Alt+R
  - Volume Up   -> Shift
  - Volume Down -> Return (Enter)

Run with --debug to discover the exact keycodes your SBH20 sends.
"""

import argparse
import os
import subprocess
import sys
import time

from evdev import InputDevice, ecodes, list_devices

SBH20_MAC = "4C:21:D0:9D:E8:10"
DEVICE_NAME_PATTERN = "SBH20"
DEBOUNCE_MS = 0.3  # seconds — SBH20 sends PLAYCD+PAUSECD on one press

# Default mapping based on SBH20 AVRCP capabilities.
# Run --debug to verify actual codes, then override with --map if needed.
DEFAULT_KEY_MAP = {
    # Play/Pause (center button)
    200: (["xdotool", "key", "alt+r"], "PlayCD -> Alt+R"),
    201: (["xdotool", "key", "alt+r"], "PauseCD -> Alt+R"),
    164: (["xdotool", "key", "alt+r"], "PlayPause -> Alt+R"),
    # Volume (SBH20 sends NEXT/PREV instead of VOL_UP/DOWN)
    163: (["xdotool", "key", "Return"], "NextSong -> Enter"),
    165: (["xdotool", "key", "shift"], "PreviousSong -> Shift"),
    # Fallback for devices that send standard volume codes
    115: (["xdotool", "key", "shift"], "VolumeUp -> Shift"),
    114: (["xdotool", "key", "Return"], "VolumeDown -> Enter"),
}


def find_sbh20_device():
    """Find the SBH20 AVRCP input device path by name."""
    for path in list_devices():
        try:
            dev = InputDevice(path)
            if DEVICE_NAME_PATTERN in dev.name and "AVRCP" in dev.name:
                return dev
        except Exception:
            continue
    return None


def is_sbh20_connected():
    """Check if SBH20 is connected as a Bluetooth device via BlueZ D-Bus."""
    result = subprocess.run(
        [
            "dbus-send", "--system", "--dest=org.bluez", "--type=method_call",
            "--print-reply", f"/org/bluez/hci0/dev_{SBH20_MAC.replace(':', '_')}",
            "org.freedesktop.DBus.Properties.Get",
            "string:org.bluez.Device1", "string:Connected",
        ],
        capture_output=True,
        text=True,
    )
    return "boolean true" in result.stdout


def inject_key(cmd, description):
    """Run xdotool to inject a key sequence (non-blocking)."""
    env = os.environ.copy()
    # Preserve X11 context so xdotool can talk to the display server
    for key in ("DISPLAY", "XAUTHORITY"):
        if key in os.environ:
            env[key] = os.environ[key]
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    print(f"Injected: {description}")


def listen_once(device, key_map, debug=False):
    """Read events from a grabbed device until it disconnects."""
    supported = device.capabilities().get(ecodes.EV_KEY, [])
    last_debounce_time = 0.0
    debounce_codes = {200, 201, 164}  # PLAYCD, PAUSECD, PLAYPAUSE

    for event in device.read_loop():
        if event.type != ecodes.EV_KEY:
            continue
        # Only act on key-down events (value=1), not repeat (2) or release (0)
        if event.value != 1:
            continue
        if event.code not in supported:
            continue

        key_name = ecodes.KEY.get(event.code, f"KEY_{event.code}")
        if debug or event.code not in key_map:
            print(f"[debug] Button: {key_name} (code={event.code})")

        if event.code in key_map:
            now = time.monotonic()
            if event.code in debounce_codes and (now - last_debounce_time) < DEBOUNCE_MS:
                if debug:
                    print(f"[debug] Debounced: {key_name} (code={event.code})")
                continue
            if event.code in debounce_codes:
                last_debounce_time = now
            cmd, desc = key_map[event.code]
            inject_key(cmd, desc)


def main():
    parser = argparse.ArgumentParser(
        description="Map SBH20 Bluetooth buttons to keyboard shortcuts"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Print every button event received (use this to discover keycodes)"
    )
    parser.add_argument(
        "--map", metavar="CODE:KEYS", action="append",
        help="Override a mapping, e.g. --map 200:alt+r (can be used multiple times)"
    )
    args = parser.parse_args()

    if not is_sbh20_connected():
        print("ERROR: SBH20 is not connected via Bluetooth.", file=sys.stderr)
        return 1

    key_map = dict(DEFAULT_KEY_MAP)
    if args.map:
        for m in args.map:
            if ":" not in m:
                print(f"ERROR: Invalid --map format: {m}", file=sys.stderr)
                return 1
            code_str, keys = m.split(":", 1)
            try:
                code = int(code_str)
            except ValueError:
                print(f"ERROR: Invalid keycode: {code_str}", file=sys.stderr)
                return 1
            key_map[code] = (["xdotool", "key", keys], f"custom -> {keys}")

    reconnects = 0
    MAX_RECONNECTS = 5

    while True:
        print("Looking for SBH20 AVRCP input device...")
        device = None
        for attempt in range(10):
            device = find_sbh20_device()
            if device:
                break
            print(f"  Not found, retrying ({attempt + 1}/10)...")
            time.sleep(2)

        if not device:
            print("ERROR: SBH20 AVRCP device not found. Is it connected?", file=sys.stderr)
            return 1

        print(f"Found: {device.name} at {device.path}")

        try:
            device.grab()
            print("Exclusive evdev grab acquired.")
        except PermissionError:
            print(
                "ERROR: Permission denied accessing the input device.\n"
                "  Fix: sudo usermod -aG input $USER  (then log out and back in)\n"
                "  Or run this script with sudo.",
                file=sys.stderr,
            )
            return 1

        print("Listening for button presses...")
        if args.debug:
            print("Debug mode: all button events will be printed.")
        for code, (_, desc) in key_map.items():
            print(f"  {desc}")

        try:
            listen_once(device, key_map, debug=args.debug)
        except OSError as e:
            reconnects += 1
            if reconnects > MAX_RECONNECTS:
                print(
                    f"Device disconnected {MAX_RECONNECTS} times, giving up.",
                    file=sys.stderr,
                )
                try:
                    device.ungrab()
                except Exception:
                    pass
                device.close()
                return 1
            print(
                f"Device disconnected ({e}), releasing grab and retrying "
                f"({reconnects}/{MAX_RECONNECTS})..."
            )
            try:
                device.ungrab()
            except Exception:
                pass
            device.close()
            time.sleep(5)
            continue
        except KeyboardInterrupt:
            print("\nExiting.")
            try:
                device.ungrab()
            except Exception:
                pass
            device.close()
            return 0


if __name__ == "__main__":
    sys.exit(main())
