"""Audio output control — mute speakers while recording and restore afterwards.

This module intentionally has no Python package dependencies beyond the
standard library.  It shells out to the same system audio utilities that are
already used elsewhere in the project (`aplay`, `xdotool`, etc.).

Supported backends (tried in order):
  1. `pactl` — PulseAudio and PipeWire's PulseAudio compatibility layer.
  2. `wpctl` — native PipeWire / WirePlumber control.
  3. `amixer` — bare ALSA fallback (controls the "Master" simple control).
"""

from __future__ import annotations

import atexit
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass
from typing import Optional


@dataclass
class _SinkState:
    """Saved mute state for a single audio output sink/control."""

    identifier: str
    muted: bool


class AudioOutputController:
    """Save, mute, and restore system audio outputs.

    The controller is thread-safe and keeps saved state only in memory.  When
    the process exits cleanly (including via `SIGTERM`) the `atexit` hook will
    attempt to restore audio if it was left muted.
    """

    def __init__(self, preferred_tool: Optional[str] = None):
        self._tool = preferred_tool or self._detect_tool()
        self._lock = threading.Lock()
        self._saved: list[_SinkState] = []
        self._active = False
        # Last-ditch safety net for clean exits.
        atexit.register(self.restore)

    @staticmethod
    def available() -> bool:
        """Return True if any supported audio control tool is present."""
        return AudioOutputController._detect_tool() is not None

    @staticmethod
    def _detect_tool() -> Optional[str]:
        for tool in ("pactl", "wpctl", "amixer"):
            if shutil.which(tool):
                return tool
        return None

    def save_and_mute(self) -> bool:
        """Save current mute state for all outputs and mute them.

        Returns True if at least one sink was successfully muted.  Returns
        False when no supported tool is available or when the operation fails;
        in that case audio is left untouched.
        """
        if not self._tool:
            return False

        with self._lock:
            if self._active:
                return True  # Already muted by us.
            try:
                sinks = self._list_sinks()
                if not sinks:
                    return False
                self._saved = sinks
                for sink in sinks:
                    self._set_mute(sink.identifier, True)
                self._active = True
                return True
            except Exception:
                self._saved = []
                self._active = False
                return False

    def restore(self) -> bool:
        """Restore the previously saved mute state.

        Safe to call repeatedly.  Returns True if a restoration was performed.
        """
        with self._lock:
            if not self._active:
                return False
            try:
                for sink in self._saved:
                    self._set_mute(sink.identifier, sink.muted)
                return True
            except Exception:
                return False
            finally:
                self._saved = []
                self._active = False

    def is_active(self) -> bool:
        """Return True if this controller currently has outputs muted."""
        with self._lock:
            return self._active

    def _run(self, cmd: list[str]) -> str:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return result.stdout

    def _list_sinks(self) -> list[_SinkState]:
        if self._tool == "pactl":
            return self._list_sinks_pactl()
        if self._tool == "wpctl":
            return self._list_sinks_wpctl()
        if self._tool == "amixer":
            return self._list_sinks_amixer()
        return []

    def _set_mute(self, identifier: str, mute: bool) -> None:
        if self._tool == "pactl":
            self._run(["pactl", "set-sink-mute", identifier, "1" if mute else "0"])
        elif self._tool == "wpctl":
            self._run(["wpctl", "set-mute", identifier, "1" if mute else "0"])
        elif self._tool == "amixer":
            self._run(["amixer", "set", identifier, "mute" if mute else "unmute"])

    def _list_sinks_pactl(self) -> list[_SinkState]:
        """Parse `pactl list sinks` output.

        Each sink block contains lines like:
            Sink #69
            	Name: alsa_output.usb-...
            	Mute: no
        """
        output = self._run(["pactl", "list", "sinks"])
        sinks: list[_SinkState] = []
        current_name: Optional[str] = None
        current_mute = False

        for raw_line in output.splitlines():
            line = raw_line.strip()
            if line.startswith("Sink #"):
                if current_name is not None:
                    sinks.append(_SinkState(current_name, current_mute))
                current_name = None
                current_mute = False
            elif line.startswith("Name:"):
                current_name = line.split(":", 1)[1].strip()
            elif line.startswith("Mute:"):
                current_mute = line.split(":", 1)[1].strip().lower() == "yes"

        if current_name is not None:
            sinks.append(_SinkState(current_name, current_mute))

        return sinks

    def _list_sinks_wpctl(self) -> list[_SinkState]:
        """Parse the Sinks section of `wpctl status`.

        wpctl uses box-drawing characters (│, ├, └) for tree structure.
        Sink lines look like:
            │      52. HDA NVidia Digital Stereo (HDMI)    [vol: 0.00 MUTED]
            │  *   85. HUAWEI FreeGO                       [vol: 0.33]
        """
        output = self._run(["wpctl", "status"])
        sinks: list[_SinkState] = []
        in_sinks = False

        # After stripping tree-drawing chars and whitespace, sink lines look like:
        #   *   85. HUAWEI FreeGO                       [vol: 0.33]
        #       52. HDA NVidia Digital Stereo (HDMI)    [vol: 0.00 MUTED]
        sink_re = re.compile(r"\*?\s*(\d+)\.\s+.+?\[vol:")

        for raw_line in output.splitlines():
            stripped = raw_line.strip()
            if stripped in ("Sinks:", "├─ Sinks:", "└─ Sinks:"):
                in_sinks = True
                continue
            if not in_sinks:
                continue
            # End of the Sinks section when we hit another labelled section
            # (e.g. "Sources:", "├─ Sources:") or an empty line after content.
            if stripped and not raw_line.startswith(" │") and not stripped.startswith("*"):
                # Allow "│" alone (empty tree continuation line).
                if stripped in ("│", ""):
                    continue
                break
            # Strip box-drawing prefix before regex matching.
            cleaned = raw_line.lstrip(" │├└─\t")
            match = sink_re.match(cleaned)
            if match:
                sink_id = match.group(1)
                muted = "MUTED" in raw_line.upper()
                sinks.append(_SinkState(sink_id, muted))

        return sinks

    def _list_sinks_amixer(self) -> list[_SinkState]:
        """Use ALSA's Master simple control as a last-resort fallback."""
        output = self._run(["amixer", "scontrols"])
        for line in output.splitlines():
            match = re.search(r"Simple mixer control '([^']+)'", line)
            if match:
                name = match.group(1)
                # We only attempt the Master control; controlling every card's
                # every control from scontrols is fragile and surprising.
                if name.lower() == "master":
                    return [_SinkState(name, False)]
        return []
