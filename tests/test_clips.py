"""Tests for clip discovery and assignment."""

from pathlib import Path

import pytest

from radiostar_killer.clips import (
    ClipAssignment,
    assign_clips_to_groups,
    discover_clips,
)


class TestDiscoverClips:
    def test_finds_supported_extensions(self, tmp_clips_dir: Path):
        clips = discover_clips(tmp_clips_dir)
        assert len(clips) == 3
        assert all(p.suffix == ".mp4" for p in clips)

    def test_ignores_unsupported_extensions(self, tmp_clips_dir: Path):
        (tmp_clips_dir / "notes.txt").write_text("not a video")
        (tmp_clips_dir / "image.png").write_bytes(b"\x89PNG")
        clips = discover_clips(tmp_clips_dir)
        assert len(clips) == 3

    def test_empty_dir_raises(self, tmp_path: Path):
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(ValueError, match="No video clips found"):
            discover_clips(empty)

    def test_missing_dir_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            discover_clips(tmp_path / "nonexistent")

    def test_returns_sorted(self, tmp_clips_dir: Path):
        clips = discover_clips(tmp_clips_dir)
        assert clips == sorted(clips)


class TestAssignClipsToGroups:
    def test_basic_assignment(self, tmp_clips_dir: Path):
        paths = discover_clips(tmp_clips_dir)
        groups = [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0)]
        assignments = assign_clips_to_groups(paths, groups, seed=42)

        assert len(assignments) == 3
        assert all(isinstance(a, ClipAssignment) for a in assignments)
        assert all(a.original_duration > 0 for a in assignments)

    def test_target_durations_match_groups(self, tmp_clips_dir: Path):
        paths = discover_clips(tmp_clips_dir)
        groups = [(0.0, 1.5), (1.5, 3.0)]
        assignments = assign_clips_to_groups(paths, groups, seed=42)

        for a, (start, end) in zip(assignments, groups):
            assert a.target_duration == pytest.approx(end - start)

    def test_recycling_when_fewer_clips(self, tmp_clips_dir: Path):
        paths = discover_clips(tmp_clips_dir)
        # 5 groups but only 3 clips
        groups = [(i, i + 1.0) for i in range(5)]
        assignments = assign_clips_to_groups(paths, groups, seed=42)

        assert len(assignments) == 5
        used_paths = [a.path for a in assignments]
        # Should recycle: indices 3 and 4 reuse clips 0 and 1 from shuffled
        assert len(set(used_paths)) <= 3

    def test_seed_reproducibility(self, tmp_clips_dir: Path):
        paths = discover_clips(tmp_clips_dir)
        groups = [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0)]

        a1 = assign_clips_to_groups(paths, groups, seed=123)
        a2 = assign_clips_to_groups(paths, groups, seed=123)

        assert [a.path for a in a1] == [a.path for a in a2]

    def test_different_seeds_differ(self, tmp_clips_dir: Path):
        paths = discover_clips(tmp_clips_dir)
        groups = [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0)]

        a1 = assign_clips_to_groups(paths, groups, seed=1)
        a2 = assign_clips_to_groups(paths, groups, seed=99)

        # With 3 clips shuffled differently, order should differ
        # (not guaranteed but highly likely)
        paths1 = [a.path for a in a1]
        paths2 = [a.path for a in a2]
        assert paths1 != paths2
