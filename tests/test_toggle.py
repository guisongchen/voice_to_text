"""Tests for toggle module process matching and kill logic."""
from unittest.mock import patch, MagicMock

from voice_to_text.toggle import find_processes


class TestFindProcesses:
    def _mock_pgrep(self, output):
        """Return a mock subprocess.run result for pgrep."""
        result = MagicMock()
        result.returncode = 0
        result.stdout = output
        return result

    def test_matches_daemon_module(self):
        output = "12345 /home/ccc/projects/voice_to_text/.venv/bin/python3 -m voice_to_text --start-recording\n"
        with patch("voice_to_text.toggle.subprocess.run", return_value=self._mock_pgrep(output)):
            pids = find_processes()
        assert pids == ["12345"]

    def test_skips_toggle_script(self):
        output = (
            "12345 /home/ccc/.venv/bin/python3 -m voice_to_text\n"
            "12346 /home/ccc/.venv/bin/python3 scripts/voice-to-text-t\n"
        )
        with patch("voice_to_text.toggle.subprocess.run", return_value=self._mock_pgrep(output)):
            pids = find_processes()
        assert pids == ["12345"]

    def test_skips_listener(self):
        output = (
            "12345 /home/ccc/.venv/bin/python3 -m voice_to_text\n"
            "12346 /home/ccc/.venv/bin/python3 scripts/lp998_listener.py\n"
        )
        with patch("voice_to_text.toggle.subprocess.run", return_value=self._mock_pgrep(output)):
            pids = find_processes()
        assert pids == ["12345"]

    def test_skips_grep_and_bash(self):
        output = (
            "12345 grep voice.to.text\n"
            "12346 /bin/bash -c voice-to-text\n"
            "12347 bash scripts/voice-to-text-t\n"
        )
        with patch("voice_to_text.toggle.subprocess.run", return_value=self._mock_pgrep(output)):
            pids = find_processes()
        assert pids == []

    def test_skips_non_daemon_matches(self):
        """Editors and log viewers that mention voice_to_text should not match."""
        output = (
            "12345 code /home/ccc/projects/voice_to_text/service.py\n"
            "12346 tail -f /tmp/voice_to_text.log\n"
        )
        with patch("voice_to_text.toggle.subprocess.run", return_value=self._mock_pgrep(output)):
            pids = find_processes()
        assert pids == []

    def test_empty_output(self):
        with patch("voice_to_text.toggle.subprocess.run", return_value=self._mock_pgrep("")):
            pids = find_processes()
        assert pids == []

    def test_pgrep_not_found(self):
        with patch("voice_to_text.toggle.subprocess.run", side_effect=FileNotFoundError):
            pids = find_processes()
        assert pids == []
