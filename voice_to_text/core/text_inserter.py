"""
Text insertion using xdotool.
"""

import subprocess

from .config import XDOTOOL_TIMEOUT


class TextInserter:
    """Text insertion using xdotool."""

    def __init__(self):
        """Initialize text inserter."""
        pass

    def check_xdotool(self):
        """
        Check if xdotool is installed.

        Returns:
            True if xdotool is available, False otherwise
        """
        try:
            result = subprocess.run(
                ['xdotool', 'version'],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def insert_text(self, text):
        """
        Insert text at cursor position using xdotool.

        Args:
            text: Text to insert

        Returns:
            True if successful, False otherwise
        """
        if not text or not text.strip():
            print("  (No text to insert)")
            return False

        try:
            # Use xdotool to type the text directly at cursor
            subprocess.run(
                ['xdotool', 'type', '--clearmodifiers', '--', text],
                check=True,
                timeout=XDOTOOL_TIMEOUT
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"  ✗ Error inserting text: {e}")
            return False
        except subprocess.TimeoutExpired:
            print("  ✗ Error: xdotool timed out")
            return False

    def cleanup(self):
        """Clean up resources."""
        # Nothing to clean up for xdotool
        pass