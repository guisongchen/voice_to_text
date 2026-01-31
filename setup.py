"""
Setup script for voice-to-text package.
"""

from setuptools import setup, find_packages

setup(
    name="voice-to-text",
    version="1.0.0",
    description="Voice-to-Text Input Tool",
    author="Your Name",
    packages=find_packages(),
    install_requires=[
        "openai-whisper>=20250625",
        "pyaudio>=0.2.14",
        "numpy>=1.24.0",
    ],
    entry_points={
        "console_scripts": [
            "voice-to-text=voice_to_text.cli.voice_to_text_cli:main",
            "record=voice_to_text.cli.record_cli:main",
        ],
    },
    python_requires=">=3.10",
)