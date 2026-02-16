"""Tests for audio beat analysis and grouping."""

import numpy as np

from radiostar_killer.audio import group_beats


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
