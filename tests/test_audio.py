"""Tests for audio beat analysis and grouping."""

from pathlib import Path

import numpy as np
import pytest

from radiostar_killer.audio import analyze_energy, group_beats


class TestGroupBeats:
    def test_exact_multiple_of_4(self):
        beats = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5])
        groups = group_beats(beats, duration=4.0)
        assert len(groups) == 2
        assert groups[0] == (0.0, 2.0)
        assert groups[1] == (2.0, 4.0)

    def test_remainder_merged_into_previous(self):
        # 5 beats: group of 4 + 1 remainder (< min_beats=2), merge into prev
        beats = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
        groups = group_beats(beats, duration=3.0, min_beats=2)
        assert len(groups) == 1
        assert groups[0] == (0.0, 3.0)

    def test_remainder_standalone(self):
        # 6 beats: group of 4 + 2 remainder (>= min_beats=2), standalone
        beats = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 2.5])
        groups = group_beats(beats, duration=3.0, min_beats=2)
        assert len(groups) == 2
        assert groups[0] == (0.0, 2.0)
        assert groups[1] == (2.0, 3.0)

    def test_fewer_beats_than_min(self):
        # Only 1 beat, min_beats=2: still creates one group
        beats = np.array([0.5])
        groups = group_beats(beats, duration=2.0, min_beats=2)
        assert len(groups) == 1
        assert groups[0] == (0.5, 2.0)

    def test_empty_beats(self):
        beats = np.array([])
        groups = group_beats(beats, duration=5.0)
        assert groups == [(0.0, 5.0)]

    def test_min_beats_1(self):
        # 5 beats with min_beats=1: remainder of 1 is standalone
        beats = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
        groups = group_beats(beats, duration=3.0, min_beats=1)
        assert len(groups) == 2
        assert groups[0] == (0.0, 2.0)
        assert groups[1] == (2.0, 3.0)

    def test_exactly_4_beats(self):
        beats = np.array([0.0, 1.0, 2.0, 3.0])
        groups = group_beats(beats, duration=4.0)
        assert len(groups) == 1
        assert groups[0] == (0.0, 4.0)

    def test_three_beats_min_beats_2(self):
        # 3 beats, no full group of 4, remainder=3 >= min_beats=2
        beats = np.array([0.0, 1.0, 2.0])
        groups = group_beats(beats, duration=3.0, min_beats=2)
        assert len(groups) == 1
        assert groups[0] == (0.0, 3.0)


class TestAnalyzeEnergy:
    @pytest.fixture
    def loud_quiet_audio(self, tmp_path: Path) -> Path:
        """Create a 20s audio file: first 10s loud, last 10s quiet."""
        import soundfile as sf

        sr = 22050
        duration = 20.0
        n_samples = int(sr * duration)
        t = np.linspace(0, duration, n_samples, endpoint=False)

        audio = np.zeros(n_samples, dtype=np.float32)
        # Loud section: first 10 seconds
        loud_end = int(sr * 10)
        audio[:loud_end] = (np.sin(2 * np.pi * 440 * t[:loud_end]) * 0.9).astype(
            np.float32
        )
        # Quiet section: last 10 seconds
        audio[loud_end:] = (np.sin(2 * np.pi * 440 * t[loud_end:]) * 0.01).astype(
            np.float32
        )

        path = tmp_path / "loud_quiet.wav"
        sf.write(str(path), audio, sr)
        return path

    def test_finds_loud_section(self, loud_quiet_audio: Path):
        sections = analyze_energy(loud_quiet_audio, window_duration=8.0, num_sections=1)
        assert len(sections) == 1
        # The loud section is in the first 10 seconds
        assert sections[0].start < 5.0

    def test_returns_non_overlapping(self, loud_quiet_audio: Path):
        sections = analyze_energy(loud_quiet_audio, window_duration=5.0, num_sections=3)
        for i in range(len(sections) - 1):
            assert sections[i].end <= sections[i + 1].start

    def test_sorted_by_start_time(self, loud_quiet_audio: Path):
        sections = analyze_energy(loud_quiet_audio, window_duration=5.0, num_sections=3)
        starts = [s.start for s in sections]
        assert starts == sorted(starts)

    def test_fewer_sections_when_audio_short(self, tmp_path: Path):
        """When audio is too short for N non-overlapping windows, return fewer."""
        import soundfile as sf

        sr = 22050
        duration = 8.0
        n_samples = int(sr * duration)
        t = np.linspace(0, duration, n_samples, endpoint=False)
        audio = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)

        path = tmp_path / "short.wav"
        sf.write(str(path), audio, sr)

        # Request 3 sections with 5s windows from 8s audio — can't fit 3
        sections = analyze_energy(path, window_duration=5.0, num_sections=3)
        assert len(sections) < 3
        assert len(sections) >= 1
