#!/usr/bin/env python3
"""
FiiO μBTR button listener daemon.
Monitors the AVRCP input device at the kernel evdev level (bypasses X11/HFP),
and triggers voice_to_text_toggle.py on button press.
"""

import glob
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
TOGGLE_SCRIPT = SCRIPT_DIR / "scripts" / "voice-to-text-t"
DEVICE_NAME_PATTERN = "FiiO"

# X11 keycode - 8 = evdev code. FiiO sends X11 208/209, so evdev 200/201.
# But evdev codes depend on the kernel driver; discover them at runtime.
TRIGGER_KEYCODES = None  # discovered on first event


def get_x11_env():
    """Discover X11 environment (DISPLAY, XAUTHORITY) for xdotool."""
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


def find_fiio_device():
    """Find the FiiO AVRCP input device path by name."""
    try:
        from evdev import InputDevice, list_devices
        for path in list_devices():
            try:
                dev = InputDevice(path)
                if DEVICE_NAME_PATTERN in dev.name and "AVRCP" in dev.name:
                    return dev
            except Exception:
                continue
    except ImportError:
        pass
    return None


def run_toggle():
    """Run the toggle script in a subprocess (non-blocking)."""
    env = get_x11_env()
    subprocess.Popen(
        [sys.executable, str(TOGGLE_SCRIPT)],
        start_new_session=True,
        env=env,
    )


FIIO_MAC = "40:ED:98:19:0D:57"
FIIO_CARD = "bluez_card.40_ED_98_19_0D_57"
FIIO_A2DP_PROFILE = "a2dp-sink-sbc"
UGREEN_SOURCE = "alsa_input.usb-JinAudio_UGREEN_USB_MIC-CM769_202408060037-00.iec958-stereo"


def is_fiio_bluetooth_connected():
    """Check if FiiO is connected as a Bluetooth device via BlueZ D-Bus."""
    result = subprocess.run(
        [
            "dbus-send", "--system", "--dest=org.bluez", "--type=method_call",
            "--print-reply", f"/org/bluez/hci0/dev_{FIIO_MAC.replace(':', '_')}",
            "org.freedesktop.DBus.Properties.Get",
            "string:org.bluez.Device1", "string:Connected",
        ],
        capture_output=True,
        text=True,
    )
    return "boolean true" in result.stdout


def ensure_audio_setup():
    """Force FiiO to A2DP profile and set UGREEN as default mic."""
    try:
        subprocess.run(
            ["pactl", "set-card-profile", FIIO_CARD, FIIO_A2DP_PROFILE],
            check=True, capture_output=True
        )
        print(f"FiiO set to A2DP profile ({FIIO_A2DP_PROFILE})")
    except subprocess.CalledProcessError as e:
        print(f"Warning: could not set FiiO profile: {e.stderr.decode().strip()}")

    try:
        subprocess.run(
            ["pactl", "set-default-source", UGREEN_SOURCE],
            check=True, capture_output=True
        )
        print(f"Default mic set to UGREEN USB")
    except subprocess.CalledProcessError as e:
        print(f"Warning: could not set default source: {e.stderr.decode().strip()}")


def listen_once(device, supported, ecodes):
    """Read events from a grabbed device until it disconnects."""
    for event in device.read_loop():
        if event.type != ecodes.EV_KEY:
            continue
        # Only act on key-down events (value=1), not repeat (2) or release (0)
        if event.value != 1:
            continue
        # Only act if it's a key this device actually has (media buttons)
        if event.code not in supported:
            continue

        key_name = ecodes.KEY.get(event.code, f"KEY_{event.code}")
        print(f"Button pressed: {key_name} (code={event.code}) → toggling")
        run_toggle()


def main():
    from evdev import InputDevice, categorize, ecodes, list_devices

    if not is_fiio_bluetooth_connected():
        print("ERROR: FiiO is not connected via Bluetooth.", file=sys.stderr)
        return 1

    reconnects = 0
    MAX_RECONNECTS = 5

    while True:
        print(f"Looking for FiiO AVRCP input device...")
        device = None
        for attempt in range(10):
            device = find_fiio_device()
            if device:
                break
            print(f"  Not found, retrying ({attempt + 1}/10)...")
            time.sleep(2)

        if not device:
            print("ERROR: FiiO AVRCP device not found. Is it connected?", file=sys.stderr)
            return 1

        print(f"Found: {device.name} at {device.path}")
        ensure_audio_setup()

        # Grab the device exclusively so BlueZ HFP cannot intercept button events
        # during audio recording (which activates the HFP call-control profile).
        device.grab()
        print(f"Exclusive evdev grab acquired — button events bypass HFP.")
        print(f"Listening for button presses...")

        # Collect the key codes this device supports (for filtering)
        supported = device.capabilities().get(ecodes.EV_KEY, [])

        try:
            listen_once(device, supported, ecodes)
        except OSError as e:
            reconnects += 1
            if reconnects > MAX_RECONNECTS:
                print(f"Device disconnected {MAX_RECONNECTS} times, giving up.", file=sys.stderr)
                try:
                    device.ungrab()
                except Exception:
                    pass
                device.close()
                return 1
            print(f"Device disconnected ({e}), releasing grab and retrying ({reconnects}/{MAX_RECONNECTS})...")
            try:
                device.ungrab()
            except Exception:
                pass
            device.close()
            time.sleep(5)
            continue


if __name__ == "__main__":
    sys.exit(main())
