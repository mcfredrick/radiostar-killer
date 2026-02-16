"""Shared test fixtures."""

from pathlib import Path

import numpy as np
import pytest
from moviepy import ColorClip


@pytest.fixture
def tmp_clips_dir(tmp_path: Path) -> Path:
    """Create a directory with short synthetic color clips."""
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()

    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    for i, color in enumerate(colors):
        clip = ColorClip(size=(320, 240), color=color, duration=2.0)
        clip = clip.with_fps(10)
        output = clips_dir / f"clip_{i}.mp4"
        clip.write_videofile(
            str(output),
            codec="libx264",
            audio=False,
            logger=None,
        )
        clip.close()

    return clips_dir


@pytest.fixture
def tmp_audio_file(tmp_path: Path) -> Path:
    """Create a short sine wave audio file."""
    sr = 22050
    duration = 6.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # 440 Hz sine wave
    audio = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)

    import soundfile as sf

    audio_path = tmp_path / "test_audio.wav"
    sf.write(str(audio_path), audio, sr)
    return audio_path
