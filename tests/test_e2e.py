"""End-to-end tests for the full pipeline."""

from pathlib import Path

import pytest
from moviepy import VideoFileClip

from radiostar_killer.formats import FormatPreset
from radiostar_killer.main import run


@pytest.mark.e2e
class TestEndToEnd:
    def test_full_pipeline(
        self, tmp_clips_dir: Path, tmp_audio_file: Path, tmp_path: Path
    ):
        output = tmp_path / "output.mp4"
        preset = FormatPreset(
            name="test",
            resolution=(320, 240),
            fps=10,
        )

        result = run(
            clips_dir=tmp_clips_dir,
            audio_file=tmp_audio_file,
            output=output,
            min_beats=2,
            seed=42,
            preset=preset,
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

    def test_full_pipeline_with_effects_and_transitions(
        self, tmp_clips_dir: Path, tmp_audio_file: Path, tmp_path: Path
    ):
        output = tmp_path / "output_fx.mp4"
        preset = FormatPreset(
            name="test",
            resolution=(320, 240),
            fps=10,
        )

        result = run(
            clips_dir=tmp_clips_dir,
            audio_file=tmp_audio_file,
            output=output,
            min_beats=2,
            seed=42,
            preset=preset,
            effects=True,
            effect_rate=0.75,
            transitions=True,
            transition_rate=1.0,
            transition_duration=0.3,
        )

        assert result == output
        assert output.exists()
        assert output.stat().st_size > 0

        clip = VideoFileClip(str(output))
        try:
            # Duration should be slightly shorter due to transitions
            assert clip.duration == pytest.approx(6.0, abs=2.0)
            assert clip.audio is not None
            assert clip.size == [320, 240]
        finally:
            clip.close()
