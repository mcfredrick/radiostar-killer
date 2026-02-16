"""End-to-end tests for the full pipeline."""

from pathlib import Path

import pytest
from moviepy import VideoFileClip

from radiostar_killer.main import run


@pytest.mark.e2e
class TestEndToEnd:
    def test_full_pipeline(
        self, tmp_clips_dir: Path, tmp_audio_file: Path, tmp_path: Path
    ):
        output = tmp_path / "output.mp4"

        result = run(
            clips_dir=tmp_clips_dir,
            audio_file=tmp_audio_file,
            output=output,
            min_beats=2,
            seed=42,
            resolution=(320, 240),
            fps=10,
        )

        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0

        # Verify output properties
        clip = VideoFileClip(str(output))
        try:
            # Duration should approximately match audio (6 seconds)
            assert clip.duration == pytest.approx(6.0, abs=1.0)
            # Should have an audio track
            assert clip.audio is not None
            # Resolution should match
            assert clip.size == [320, 240]
        finally:
            clip.close()
