"""Tests for config module consistency."""
from pathlib import Path

from voice_to_text.config import SOCKET_PATH, SOCKET_FILE


def test_socket_path_and_file_agree():
    """SOCKET_PATH (str) and SOCKET_FILE (Path) must reference the same file."""
    assert SOCKET_FILE == Path(SOCKET_PATH)


def test_model_choices_contains_default():
    from voice_to_text.config import MODEL_CHOICES, MODEL_SIZE_DEFAULT
    assert MODEL_SIZE_DEFAULT in MODEL_CHOICES
