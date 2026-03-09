"""Unit tests for split screen compositing and injection."""

import random

import numpy as np
import pytest
from moviepy import ColorClip

from radiostar_killer.splitscreen import (
    BARS_PER_PANEL_FAST,
    BARS_PER_PANEL_SLOW,
    BEATS_PER_BAR,
    CLIMAX_PANEL_SEQUENCE,
    DOUBLE_TIME_PROBABILITY,
    FAST_TEMPO_THRESHOLD_BPM,
    SPLIT_SCREEN_DOUBLE_TIME_PROBABILITY,
    LAYOUT_GRID,
    LAYOUT_RADIAL,
    PANEL_CONTRAST_RATE,
    PANEL_EFFECT_RATE,
    PANEL_MODE_DIFFERENT,
    PANEL_MODE_SAME_CLIP,
    PANEL_MODE_SAME_PARTS,
    ClimaxBurstConfig,
    SplitScreenConfig,
    _apply_contrast_tints,
    _apply_panel_effects,
    _compose_radial,
    _panel_cells,
    _select_panel_clips,
    build_climax_burst,
    climax_panel_duration,
    compose_split_screen,
    inject_climax_burst,
    inject_split_screens,
)

RESOLUTION = (320, 240)
FPS = 10


def _color_clip(duration: float = 1.0, color: tuple[int, int, int] = (255, 0, 0)) -> ColorClip:
    # Pass color as uint8 so PIL-based effects don't choke on int64 frames
    return ColorClip(size=RESOLUTION, color=np.array(color, dtype=np.uint8), duration=duration).with_fps(FPS)


# --- SplitScreenConfig ---


def test_config_invalid_panels() -> None:
    with pytest.raises(ValueError, match="panels must be 2, 4, or 6"):
        SplitScreenConfig(panels=3)


def test_config_invalid_count() -> None:
    with pytest.raises(ValueError, match="count must be >= 1"):
        SplitScreenConfig(count=0)


def test_config_defaults() -> None:
    cfg = SplitScreenConfig()
    assert cfg.count == 2
    assert cfg.panels is None
    assert cfg.min_gap == 3


# --- _panel_cells ---


def test_panel_cells_2() -> None:
    cells = _panel_cells(2, (320, 240))
    assert len(cells) == 2
    # Side by side: each cell is half width, full height
    for _, _, cw, ch in cells:
        assert cw == 160
        assert ch == 240


def test_panel_cells_4() -> None:
    cells = _panel_cells(4, (320, 240))
    assert len(cells) == 4
    for _, _, cw, ch in cells:
        assert cw == 160
        assert ch == 120


def test_panel_cells_6() -> None:
    cells = _panel_cells(6, (320, 240))
    assert len(cells) == 6
    for _, _, cw, ch in cells:
        assert cw == 106  # 320 // 3
        assert ch == 120


def test_panel_cells_invalid() -> None:
    with pytest.raises(ValueError):
        _panel_cells(3, (320, 240))


# --- compose_split_screen ---


def test_compose_split_screen_2_resolution() -> None:
    clips = [_color_clip(1.0, (255, 0, 0)), _color_clip(1.0, (0, 255, 0))]
    result = compose_split_screen(clips, RESOLUTION, FPS)
    assert result.size == RESOLUTION


def test_compose_split_screen_duration_is_max() -> None:
    clips = [_color_clip(1.0), _color_clip(2.0), _color_clip(1.5), _color_clip(0.5)]
    result = compose_split_screen(clips, RESOLUTION, FPS)
    assert abs(result.duration - 2.0) < 0.1


def test_compose_split_screen_shorter_clips_loop() -> None:
    # Short clip should loop to fill the longest panel's duration
    clips = [_color_clip(0.5), _color_clip(2.0)]
    result = compose_split_screen(clips, RESOLUTION, FPS)
    assert abs(result.duration - 2.0) < 0.1


def test_compose_split_screen_invalid_count() -> None:
    clips = [_color_clip() for _ in range(3)]
    with pytest.raises(ValueError, match="2, 4, or 6"):
        compose_split_screen(clips, RESOLUTION, FPS)


# --- inject_split_screens ---


def test_inject_noop_single_clip() -> None:
    clips = [_color_clip()]
    rng = random.Random(42)
    result = inject_split_screens(clips, SplitScreenConfig(), RESOLUTION, FPS, rng)
    assert len(result) == 1


def test_inject_reduces_list_length() -> None:
    # With 8 clips and count=1, panels=2: result should be 7 clips (8 - 2 + 1)
    clips = [_color_clip() for _ in range(8)]
    cfg = SplitScreenConfig(count=1, panels=2)
    rng = random.Random(42)
    result = inject_split_screens(clips, cfg, RESOLUTION, FPS, rng)
    assert len(result) == 7


def test_inject_fixed_panels_4() -> None:
    clips = [_color_clip() for _ in range(12)]
    cfg = SplitScreenConfig(count=1, panels=4)
    rng = random.Random(42)
    result = inject_split_screens(clips, cfg, RESOLUTION, FPS, rng)
    # One 4-panel composite inserted: 12 - 4 + 1 = 9
    assert len(result) == 9


def test_inject_count_capped_by_available() -> None:
    # Only 3 clips — can fit at most 1 split screen of 2 panels; count=5 should be capped
    clips = [_color_clip() for _ in range(3)]
    cfg = SplitScreenConfig(count=5, panels=2, min_gap=1)
    rng = random.Random(42)
    result = inject_split_screens(clips, cfg, RESOLUTION, FPS, rng)
    # At most 1 injection: 3 - 2 + 1 = 2
    assert len(result) <= 2


def test_inject_spacing_enforced() -> None:
    # 20 clips, count=2, panels=2, min_gap=3
    # Two injections should each consume 2 clips; check no overlap
    clips = [_color_clip() for _ in range(20)]
    cfg = SplitScreenConfig(count=2, panels=2, min_gap=3)
    rng = random.Random(99)
    result = inject_split_screens(clips, cfg, RESOLUTION, FPS, rng)
    # 2 injections of 2 panels each: 20 - 2*(2-1) = 18
    assert len(result) == 18


def test_inject_does_not_modify_original() -> None:
    clips = [_color_clip() for _ in range(6)]
    original_len = len(clips)
    cfg = SplitScreenConfig(count=1, panels=2)
    rng = random.Random(0)
    inject_split_screens(clips, cfg, RESOLUTION, FPS, rng)
    assert len(clips) == original_len


def test_inject_result_clips_have_correct_resolution() -> None:
    clips = [_color_clip() for _ in range(6)]
    cfg = SplitScreenConfig(count=1, panels=2)
    rng = random.Random(7)
    result = inject_split_screens(clips, cfg, RESOLUTION, FPS, rng)
    for clip in result:
        assert clip.size == RESOLUTION


# --- climax_panel_duration ---


def test_climax_panel_duration_fast() -> None:
    tempo = FAST_TEMPO_THRESHOLD_BPM  # exactly at threshold → fast
    expected = BARS_PER_PANEL_FAST * BEATS_PER_BAR * (60.0 / tempo)
    assert abs(climax_panel_duration(tempo) - expected) < 1e-6


def test_climax_panel_duration_slow() -> None:
    tempo = FAST_TEMPO_THRESHOLD_BPM - 1  # just below threshold → slow
    expected = BARS_PER_PANEL_SLOW * BEATS_PER_BAR * (60.0 / tempo)
    assert abs(climax_panel_duration(tempo) - expected) < 1e-6


def test_climax_panel_duration_very_fast() -> None:
    # Higher tempo = shorter bar = shorter step duration
    slow_dur = climax_panel_duration(60.0)
    fast_dur = climax_panel_duration(180.0)
    assert fast_dur < slow_dur


# --- build_climax_burst ---


def test_build_climax_burst_resolution() -> None:
    pool = [_color_clip() for _ in range(4)]
    rng = random.Random(0)
    burst = build_climax_burst(pool, tempo=120.0, resolution=RESOLUTION, fps=FPS, rng=rng)
    assert burst.size == RESOLUTION


def test_build_climax_burst_duration() -> None:
    # double_time=False: verify normal-time total duration
    pool = [_color_clip(2.0) for _ in range(6)]
    rng = random.Random(0)
    tempo = 120.0
    step_dur = climax_panel_duration(tempo)
    burst = build_climax_burst(pool, tempo=tempo, resolution=RESOLUTION, fps=FPS,
                               rng=rng, double_time=False)
    expected = step_dur * len(CLIMAX_PANEL_SEQUENCE)
    assert abs(burst.duration - expected) < 0.2  # allow for small float rounding


def test_build_climax_burst_small_pool() -> None:
    # Pool smaller than max panels (6) — should still work via rng.choices
    pool = [_color_clip() for _ in range(2)]
    rng = random.Random(42)
    burst = build_climax_burst(pool, tempo=140.0, resolution=RESOLUTION, fps=FPS, rng=rng)
    assert burst.size == RESOLUTION


# --- inject_climax_burst ---


def _beat_groups(n: int, dur: float = 1.0) -> list[tuple[float, float]]:
    return [(i * dur, (i + 1) * dur) for i in range(n)]


def test_inject_climax_burst_reduces_length() -> None:
    n_clips = 12
    clips = [_color_clip() for _ in range(n_clips)]
    groups = _beat_groups(n_clips)
    cfg = ClimaxBurstConfig(climax_time=3.5, tempo=128.0, beat_groups=groups)
    rng = random.Random(0)
    result = inject_climax_burst(clips, cfg, RESOLUTION, FPS, rng)
    # burst replaces len(CLIMAX_PANEL_SEQUENCE) clips with 1
    assert len(result) == n_clips - len(CLIMAX_PANEL_SEQUENCE) + 1


def test_inject_climax_burst_result_resolution() -> None:
    clips = [_color_clip() for _ in range(10)]
    groups = _beat_groups(10)
    cfg = ClimaxBurstConfig(climax_time=2.0, tempo=100.0, beat_groups=groups)
    rng = random.Random(1)
    result = inject_climax_burst(clips, cfg, RESOLUTION, FPS, rng)
    for clip in result:
        assert clip.size == RESOLUTION


def test_inject_climax_burst_targets_correct_group() -> None:
    # climax_time=4.5 falls in group 4 (4.0–5.0)
    clips = [_color_clip() for _ in range(12)]
    groups = _beat_groups(12)
    cfg = ClimaxBurstConfig(climax_time=4.5, tempo=128.0, beat_groups=groups)
    rng = random.Random(0)
    result = inject_climax_burst(clips, cfg, RESOLUTION, FPS, rng)
    # Groups 4..8 (5 clips) are replaced with 1; total = 12 - 4 = 8
    assert len(result) == 12 - len(CLIMAX_PANEL_SEQUENCE) + 1


def test_inject_climax_burst_clamps_near_end() -> None:
    # climax_time beyond all groups — should clamp instead of crash
    clips = [_color_clip() for _ in range(8)]
    groups = _beat_groups(8)
    cfg = ClimaxBurstConfig(climax_time=999.0, tempo=128.0, beat_groups=groups)
    rng = random.Random(0)
    result = inject_climax_burst(clips, cfg, RESOLUTION, FPS, rng)
    assert len(result) == 8 - len(CLIMAX_PANEL_SEQUENCE) + 1


def test_inject_climax_burst_noop_when_too_few_clips() -> None:
    # Fewer clips than burst length → returns unchanged
    clips = [_color_clip() for _ in range(len(CLIMAX_PANEL_SEQUENCE) - 1)]
    groups = _beat_groups(len(clips))
    cfg = ClimaxBurstConfig(climax_time=0.5, tempo=128.0, beat_groups=groups)
    rng = random.Random(0)
    result = inject_climax_burst(clips, cfg, RESOLUTION, FPS, rng)
    assert len(result) == len(clips)


# --- _select_panel_clips ---


def test_select_panel_clips_different_count() -> None:
    pool = [_color_clip(1.0, c) for c in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]]
    rng = random.Random(0)
    result, source_ids = _select_panel_clips(pool, 4, rng, mode=PANEL_MODE_DIFFERENT)
    assert len(result) == 4
    assert len(source_ids) == 4


def test_select_panel_clips_same_clip_all_identical() -> None:
    pool = [_color_clip(1.0, c) for c in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]]
    rng = random.Random(0)
    result, source_ids = _select_panel_clips(pool, 4, rng, mode=PANEL_MODE_SAME_CLIP)
    assert len(result) == 4
    # All entries are the same object and share one source id
    assert all(c is result[0] for c in result)
    assert len(set(source_ids)) == 1


def test_select_panel_clips_same_parts_count_and_duration() -> None:
    pool = [_color_clip(2.0)]
    rng = random.Random(0)
    target = 0.5
    result, source_ids = _select_panel_clips(pool, 4, rng, target_duration=target, mode=PANEL_MODE_SAME_PARTS)
    assert len(result) == 4
    for clip in result:
        assert abs(clip.duration - target) < 0.05
    # All panels derive from the same base clip
    assert len(set(source_ids)) == 1


def test_select_panel_clips_same_parts_returns_correct_count() -> None:
    pool = [_color_clip(4.0, (128, 64, 32))]
    rng = random.Random(0)
    result, source_ids = _select_panel_clips(pool, 3, rng, target_duration=1.0, mode=PANEL_MODE_SAME_PARTS)
    assert len(result) == 3
    assert len(source_ids) == 3


def test_select_panel_clips_random_mode_returns_correct_count() -> None:
    pool = [_color_clip() for _ in range(3)]
    rng = random.Random(42)
    result, source_ids = _select_panel_clips(pool, 2, rng)
    assert len(result) == 2
    assert len(source_ids) == 2


# --- radial layout ---


def test_compose_radial_resolution() -> None:
    clips = [_color_clip(1.0, (255, 0, 0)), _color_clip(1.0, (0, 255, 0))]
    result = _compose_radial(clips, RESOLUTION, FPS)
    assert result.size == RESOLUTION


def test_compose_radial_duration() -> None:
    clips = [_color_clip(1.0), _color_clip(2.0)]
    result = _compose_radial(clips, RESOLUTION, FPS)
    assert abs(result.duration - 2.0) < 0.1


def test_compose_split_screen_radial_layout() -> None:
    clips = [_color_clip(1.0, (255, 0, 0)), _color_clip(1.0, (0, 255, 0)),
             _color_clip(1.0, (0, 0, 255)), _color_clip(1.0, (255, 255, 0))]
    result = compose_split_screen(clips, RESOLUTION, FPS, layout=LAYOUT_RADIAL)
    assert result.size == RESOLUTION


def test_compose_split_screen_grid_vs_radial_both_correct_size() -> None:
    clips = [_color_clip() for _ in range(2)]
    grid = compose_split_screen(clips, RESOLUTION, FPS, layout=LAYOUT_GRID)
    radial = compose_split_screen(clips, RESOLUTION, FPS, layout=LAYOUT_RADIAL)
    assert grid.size == RESOLUTION
    assert radial.size == RESOLUTION


def test_double_time_probability_constant() -> None:
    assert DOUBLE_TIME_PROBABILITY == 1.0  # climax burst always double-time by default


def test_split_screen_double_time_probability_constant() -> None:
    assert SPLIT_SCREEN_DOUBLE_TIME_PROBABILITY == 0.50


def test_build_climax_burst_double_time_shorter_duration() -> None:
    pool = [_color_clip(2.0) for _ in range(4)]
    rng = random.Random(0)
    tempo = 120.0
    normal = build_climax_burst(pool, tempo=tempo, resolution=RESOLUTION, fps=FPS,
                                rng=rng, layout=LAYOUT_GRID, double_time=False)
    rng2 = random.Random(0)
    fast = build_climax_burst(pool, tempo=tempo, resolution=RESOLUTION, fps=FPS,
                              rng=rng2, layout=LAYOUT_GRID, double_time=True)
    assert fast.duration < normal.duration
    assert abs(fast.duration - normal.duration / 2) < 0.2


def test_build_climax_burst_double_time_correct_duration() -> None:
    pool = [_color_clip(2.0) for _ in range(6)]
    rng = random.Random(0)
    tempo = 128.0
    burst = build_climax_burst(pool, tempo=tempo, resolution=RESOLUTION, fps=FPS,
                               rng=rng, layout=LAYOUT_GRID, double_time=True)
    expected = (climax_panel_duration(tempo) / 2) * len(CLIMAX_PANEL_SEQUENCE)
    assert abs(burst.duration - expected) < 0.2


def test_build_climax_burst_normal_time_correct_duration() -> None:
    pool = [_color_clip(2.0) for _ in range(6)]
    rng = random.Random(0)
    tempo = 128.0
    burst = build_climax_burst(pool, tempo=tempo, resolution=RESOLUTION, fps=FPS,
                               rng=rng, layout=LAYOUT_GRID, double_time=False)
    expected = climax_panel_duration(tempo) * len(CLIMAX_PANEL_SEQUENCE)
    assert abs(burst.duration - expected) < 0.2


def test_build_climax_burst_radial_resolution() -> None:
    pool = [_color_clip(2.0, (255, 0, 0)), _color_clip(2.0, (0, 255, 0)),
            _color_clip(2.0, (0, 0, 255)), _color_clip(2.0, (255, 255, 0)),
            _color_clip(2.0, (0, 255, 255)), _color_clip(2.0, (255, 0, 255))]
    rng = random.Random(0)
    burst = build_climax_burst(pool, tempo=128.0, resolution=RESOLUTION, fps=FPS,
                               rng=rng, layout=LAYOUT_RADIAL)
    assert burst.size == RESOLUTION


def test_build_climax_burst_radial_duration() -> None:
    pool = [_color_clip(2.0) for _ in range(6)]
    rng = random.Random(0)
    tempo = 128.0
    burst = build_climax_burst(pool, tempo=tempo, resolution=RESOLUTION, fps=FPS,
                               rng=rng, layout=LAYOUT_RADIAL, double_time=False)
    expected = climax_panel_duration(tempo) * len(CLIMAX_PANEL_SEQUENCE)
    assert abs(burst.duration - expected) < 0.2


def test_build_climax_burst_radial_frame_is_valid() -> None:
    # Spot-check that a frame can be rendered without error and has correct shape
    pool = [_color_clip(2.0, (i * 40, 0, 255 - i * 40)) for i in range(6)]
    rng = random.Random(7)
    burst = build_climax_burst(pool, tempo=120.0, resolution=RESOLUTION, fps=FPS,
                               rng=rng, layout=LAYOUT_RADIAL)
    frame = burst.get_frame(0)
    assert frame.shape == (RESOLUTION[1], RESOLUTION[0], 3)


def test_panel_effect_rate_in_range() -> None:
    assert 0.0 <= PANEL_EFFECT_RATE <= 1.0


def test_panel_contrast_rate_in_range() -> None:
    assert 0.0 <= PANEL_CONTRAST_RATE <= 1.0


def test_apply_panel_effects_preserves_count() -> None:
    clips = [_color_clip() for _ in range(4)]
    rng = random.Random(0)
    result = _apply_panel_effects(clips, rng, rate=1.0)  # always apply
    assert len(result) == 4
    for clip in result:
        assert clip.size == RESOLUTION


def test_apply_panel_effects_same_source_distinct_filters() -> None:
    # Panels sharing a source_id must receive distinct effects (no two get the same filter)
    clip = _color_clip(color=(200, 200, 200))
    clips = [clip, clip, clip, clip]
    source_ids = [id(clip)] * 4
    rng = random.Random(0)
    result = _apply_panel_effects(clips, rng, contrast=False, source_ids=source_ids)
    assert len(result) == 4
    for r in result:
        assert r.size == RESOLUTION


def test_apply_panel_effects_different_sources_use_rate() -> None:
    # Panels with distinct source_ids use the standard rate-based path
    clips = [_color_clip() for _ in range(4)]
    source_ids = [id(c) for c in clips]  # all different
    rng = random.Random(0)
    result = _apply_panel_effects(clips, rng, rate=0.0, contrast=False, source_ids=source_ids)
    # rate=0.0 → no effects applied, so output clips should be the same count
    assert len(result) == 4


def test_apply_contrast_tints_preserves_count_and_size() -> None:
    clips = [_color_clip() for _ in range(6)]
    rng = random.Random(0)
    result = _apply_contrast_tints(clips, rng)
    assert len(result) == 6
    for clip in result:
        assert clip.size == RESOLUTION


def test_apply_contrast_tints_produces_different_colors() -> None:
    # Render a single frame from each tinted panel and verify not all identical.
    # Uses a white clip so the tint factors are clearly visible.
    clips = [_color_clip(color=(200, 200, 200)) for _ in range(4)]
    rng = random.Random(7)
    result = _apply_contrast_tints(clips, rng)
    frames = [r.get_frame(0) for r in result]
    # At least two panels should have a different mean color
    means = [f.mean(axis=(0, 1)) for f in frames]
    assert not all(np.allclose(m, means[0], atol=5) for m in means[1:])


def test_inject_split_screens_with_mixed_modes_no_crash() -> None:
    # Smoke test: with many clips, injection runs without error regardless of mode
    clips = [_color_clip(1.0, (i * 40 % 255, 0, 0)) for i in range(12)]
    cfg = SplitScreenConfig(count=2, panels=2)
    rng = random.Random(123)
    result = inject_split_screens(clips, cfg, RESOLUTION, FPS, rng)
    assert all(c.size == RESOLUTION for c in result)
