"""Tests for visual effects and transitions."""

import random

import numpy as np
import pytest
from moviepy import VideoClip

from radiostar_killer.effects import (
    EFFECT_COUNT,
    TRANSITION_TYPES,
    TransitionSpec,
    apply_random_effect,
    compose_with_transitions,
    select_transition,
)


def _make_clip(duration: float = 2.0) -> VideoClip:
    """Create a test clip with uint8 frame data."""

    def make_frame(t: float) -> np.ndarray:
        return np.full((240, 320, 3), [200, 100, 50], dtype=np.uint8)

    return VideoClip(make_frame, duration=duration).with_fps(10)


class TestApplyRandomEffect:
    def test_returns_clip_when_rate_zero(self):
        clip = _make_clip()
        rng = random.Random(42)
        result = apply_random_effect(clip, rng, effect_rate=0.0)
        assert result is clip
        clip.close()

    def test_always_applies_when_rate_one(self):
        """With rate 1.0, every clip should get an effect (not be the same object)."""
        applied = 0
        for seed in range(20):
            clip = _make_clip()
            rng = random.Random(seed)
            result = apply_random_effect(clip, rng, effect_rate=1.0)
            if result is not clip:
                applied += 1
            clip.close()
        assert applied == 20

    def test_reproducible_with_seed(self):
        """Same seed produces same effect selection."""
        clip1 = _make_clip()
        clip2 = _make_clip()
        rng1 = random.Random(42)
        rng2 = random.Random(42)

        r1 = apply_random_effect(clip1, rng1, effect_rate=1.0)
        r2 = apply_random_effect(clip2, rng2, effect_rate=1.0)

        # Both should produce the same frame
        frame1 = r1.get_frame(0)
        frame2 = r2.get_frame(0)
        np.testing.assert_array_equal(frame1, frame2)

        clip1.close()
        clip2.close()

    def test_preserves_duration_and_size(self):
        """Effects should not change clip duration or size."""
        for seed in range(EFFECT_COUNT):
            clip = _make_clip(duration=1.5)
            rng = random.Random(seed)
            result = apply_random_effect(clip, rng, effect_rate=1.0)
            assert result.duration == pytest.approx(1.5)
            assert result.size == (320, 240)
            clip.close()

    def test_each_effect_renders_without_error(self):
        """Every effect in the pool should produce a valid frame."""
        for seed in range(EFFECT_COUNT * 3):
            clip = _make_clip(duration=1.0)
            rng = random.Random(seed)
            result = apply_random_effect(clip, rng, effect_rate=1.0)
            frame = result.get_frame(0)
            assert frame.shape == (240, 320, 3)
            clip.close()


class TestSelectTransition:
    def test_returns_none_when_rate_zero(self):
        rng = random.Random(42)
        result = select_transition(rng, transition_rate=0.0, duration=0.3,
                                   clip_a_duration=2.0, clip_b_duration=2.0)
        assert result is None

    def test_always_returns_when_rate_one(self):
        results = []
        for seed in range(20):
            rng = random.Random(seed)
            result = select_transition(rng, transition_rate=1.0, duration=0.3,
                                       clip_a_duration=2.0, clip_b_duration=2.0)
            results.append(result)
        assert all(r is not None for r in results)

    def test_valid_transition_types(self):
        for seed in range(30):
            rng = random.Random(seed)
            result = select_transition(rng, transition_rate=1.0, duration=0.3,
                                       clip_a_duration=2.0, clip_b_duration=2.0)
            assert result is not None
            assert result.transition_type in TRANSITION_TYPES

    def test_duration_clamped_to_clip_limits(self):
        rng = random.Random(42)
        # clip_b is short (0.5s), clamped to 0.5 * 0.4 = 0.2
        result = select_transition(rng, transition_rate=1.0, duration=0.3,
                                   clip_a_duration=2.0, clip_b_duration=0.5)
        assert result is not None
        assert result.duration == pytest.approx(0.2)

    def test_reproducible_with_seed(self):
        r1 = select_transition(random.Random(42), 1.0, 0.3, 2.0, 2.0)
        r2 = select_transition(random.Random(42), 1.0, 0.3, 2.0, 2.0)
        assert r1 is not None and r2 is not None
        assert r1.transition_type == r2.transition_type
        assert r1.duration == r2.duration


class TestComposeWithTransitions:
    def test_hard_cuts_only(self):
        """All None transitions should produce total duration = sum of clips."""
        clips = [_make_clip(1.0), _make_clip(1.0), _make_clip(1.0)]
        result = compose_with_transitions(clips, [None, None])
        assert result.duration == pytest.approx(3.0)
        for c in clips:
            c.close()

    def test_crossfade_shortens_duration(self):
        """Crossfade transitions should reduce total duration by overlap."""
        clips = [_make_clip(2.0), _make_clip(2.0)]
        spec = TransitionSpec(transition_type="crossfade", duration=0.3)
        result = compose_with_transitions(clips, [spec])
        assert result.duration == pytest.approx(3.7)
        for c in clips:
            c.close()

    def test_slide_transition(self):
        clips = [_make_clip(2.0), _make_clip(2.0)]
        spec = TransitionSpec(transition_type="slide_left", duration=0.3)
        result = compose_with_transitions(clips, [spec])
        assert result.duration == pytest.approx(3.7)
        for c in clips:
            c.close()

    def test_mixed_transitions_and_hard_cuts(self):
        clips = [_make_clip(2.0), _make_clip(2.0), _make_clip(2.0)]
        spec = TransitionSpec(transition_type="crossfade", duration=0.5)
        result = compose_with_transitions(clips, [spec, None])
        # First boundary: 0.5s overlap, second: hard cut
        assert result.duration == pytest.approx(5.5)
        for c in clips:
            c.close()

    def test_empty_clips_raises(self):
        with pytest.raises(ValueError, match="No clips"):
            compose_with_transitions([], [])

    def test_wrong_transitions_length_raises(self):
        clips = [_make_clip(1.0), _make_clip(1.0)]
        with pytest.raises(ValueError, match="len\\(clips\\) - 1"):
            compose_with_transitions(clips, [None, None])
        for c in clips:
            c.close()
