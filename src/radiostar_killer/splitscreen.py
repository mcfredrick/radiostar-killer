"""Split screen compositing for beat-synced music videos."""

import random
from dataclasses import dataclass

import numpy as np
from moviepy import CompositeVideoClip, VideoClip, concatenate_videoclips

# ---------------------------------------------------------------------------
# Climax burst constants — edit these to tune the feature
# ---------------------------------------------------------------------------

# Panel counts for each step of the burst sequence
CLIMAX_PANEL_SEQUENCE: list[int] = [2, 4, 6, 4, 2]

# Tempo (BPM) at or above which each step lasts a full bar; below = half bar
FAST_TEMPO_THRESHOLD_BPM: float = 120.0

# Number of beats per bar
BEATS_PER_BAR: int = 4

# Duration multiplier (in bars) per step for fast / slow tempo
BARS_PER_PANEL_FAST: float = 1.0
BARS_PER_PANEL_SLOW: float = 0.5

# ---------------------------------------------------------------------------
# Panel clip selection constants — edit these to tune mode probabilities
# ---------------------------------------------------------------------------

# "different"  — each panel gets a random clip from the pool (original behaviour)
# "same_clip"  — all panels duplicate the same clip
# "same_parts" — all panels show different temporal windows of the same clip
PANEL_MODE_DIFFERENT = "different"
PANEL_MODE_SAME_CLIP = "same_clip"
PANEL_MODE_SAME_PARTS = "same_parts"

PANEL_MODES: list[str] = [PANEL_MODE_DIFFERENT, PANEL_MODE_SAME_CLIP, PANEL_MODE_SAME_PARTS]
PANEL_MODE_WEIGHTS: list[float] = [0.5, 0.25, 0.25]  # must sum to 1.0

# ---------------------------------------------------------------------------
# Layout constants — edit these to tune grid vs radial probability
# ---------------------------------------------------------------------------

LAYOUT_GRID = "grid"
LAYOUT_RADIAL = "radial"

# Default weights (used by inject_split_screens)
LAYOUT_MODES: list[str] = [LAYOUT_GRID, LAYOUT_RADIAL]
LAYOUT_WEIGHTS: list[float] = [0.6, 0.4]

# Climax burst weights — radial gets a higher share for visual impact
CLIMAX_LAYOUT_WEIGHTS: list[float] = [0.3, 0.7]


@dataclass(frozen=True)
class SplitScreenConfig:
    """Configuration for split screen injection."""

    count: int = 2
    panels: int | None = None  # None = random choice of 2, 4, or 6
    min_gap: int = 3  # minimum clips between two split screen positions

    def __post_init__(self) -> None:
        if self.panels is not None and self.panels not in (2, 4, 6):
            raise ValueError(f"panels must be 2, 4, or 6, got {self.panels}")
        if self.count < 1:
            raise ValueError(f"count must be >= 1, got {self.count}")


_VALID_PANELS = [2, 4, 6]


def _panel_cells(
    panel_count: int,
    resolution: tuple[int, int],
) -> list[tuple[int, int, int, int]]:
    """Return (x, y, cell_w, cell_h) for each panel cell."""
    w, h = resolution
    if panel_count == 2:
        cw, ch = w // 2, h
        return [(0, 0, cw, ch), (cw, 0, cw, ch)]
    elif panel_count == 4:
        cw, ch = w // 2, h // 2
        return [
            (0, 0, cw, ch),
            (cw, 0, cw, ch),
            (0, ch, cw, ch),
            (cw, ch, cw, ch),
        ]
    elif panel_count == 6:
        cw, ch = w // 3, h // 2
        return [
            (0, 0, cw, ch),
            (cw, 0, cw, ch),
            (2 * cw, 0, cw, ch),
            (0, ch, cw, ch),
            (cw, ch, cw, ch),
            (2 * cw, ch, cw, ch),
        ]
    else:
        raise ValueError(f"panel_count must be 2, 4, or 6, got {panel_count}")


def _resize_crop(clip: VideoClip, cell_w: int, cell_h: int) -> VideoClip:
    """Scale clip to cover cell, then center-crop to exact cell size."""
    src_w, src_h = clip.size
    scale = max(cell_w / src_w, cell_h / src_h)
    clip = clip.resized(scale)
    cur_w, cur_h = clip.size
    xc, yc = cur_w / 2, cur_h / 2
    return clip.cropped(
        x1=xc - cell_w / 2,
        y1=yc - cell_h / 2,
        x2=xc + cell_w / 2,
        y2=yc + cell_h / 2,
    )


def _loop_to_duration(clip: VideoClip, duration: float) -> VideoClip:
    """Loop clip until it reaches at least duration, then trim."""
    if clip.duration >= duration:
        return clip.subclipped(0, duration)
    n = int(duration / clip.duration) + 1
    looped = concatenate_videoclips([clip] * n)
    return looped.subclipped(0, duration)


def _select_panel_clips(
    clips_pool: list[VideoClip],
    n_panels: int,
    rng: random.Random,
    target_duration: float | None = None,
    mode: str | None = None,
) -> list[VideoClip]:
    """Return n_panels clips drawn from clips_pool using a randomly chosen mode.

    Modes:
      "different"  — pick n_panels clips independently at random (with replacement)
      "same_clip"  — pick one clip and duplicate it across all panels
      "same_parts" — pick one clip and create n_panels staggered temporal windows

    Pass mode explicitly to override the random selection (useful for tests).
    """
    if mode is None:
        mode = rng.choices(PANEL_MODES, weights=PANEL_MODE_WEIGHTS, k=1)[0]

    if mode == PANEL_MODE_SAME_CLIP:
        base = rng.choice(clips_pool)
        return [base] * n_panels

    if mode == PANEL_MODE_SAME_PARTS:
        base = rng.choice(clips_pool)
        dur = target_duration if target_duration is not None else base.duration
        # Stagger each panel by an equal fraction of the base clip's duration
        offset_step = max(base.duration / n_panels, 0.01)
        result = []
        for i in range(n_panels):
            start = i * offset_step
            looped = _loop_to_duration(base, start + dur)
            result.append(looped.subclipped(start, start + dur))
        return result

    # PANEL_MODE_DIFFERENT (default)
    return rng.choices(clips_pool, k=n_panels)


def _compose_radial(
    clips: list[VideoClip],
    resolution: tuple[int, int],
    fps: int,
) -> VideoClip:
    """Composite N clips into radial pie-slice panels around the frame centre.

    Each clip is scaled to fill the full frame; a precomputed per-pixel angle
    map assigns each pixel to the appropriate pie slice. Works for any N in
    _VALID_PANELS.
    """
    w, h = resolution
    n = len(clips)
    target_duration = max(c.duration for c in clips)

    # Resize every clip to full frame and normalise duration
    full_clips = [
        _loop_to_duration(_resize_crop(c, w, h), target_duration).with_fps(fps)
        for c in clips
    ]

    # Precompute per-pixel panel index (angle 0 = right, CCW)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    angles = np.arctan2(yy - h / 2, xx - w / 2)       # -π … π
    angles = (angles + 2 * np.pi) % (2 * np.pi)       # 0 … 2π
    slice_size = 2 * np.pi / n
    pixel_panel = np.clip((angles / slice_size).astype(np.int32), 0, n - 1)

    def make_frame(t: float) -> np.ndarray:
        frames = [c.get_frame(t) for c in full_clips]
        out = np.empty((h, w, 3), dtype=np.uint8)
        for p in range(n):
            mask = pixel_panel == p
            out[mask] = frames[p][mask]
        return out

    return VideoClip(make_frame, duration=target_duration).with_fps(fps)


def compose_split_screen(
    clips: list[VideoClip],
    resolution: tuple[int, int],
    fps: int,
    layout: str = LAYOUT_GRID,
) -> VideoClip:
    """Composite N clips (N must be 2, 4, or 6) into a split screen frame.

    layout="grid"   — rectangular cell grid (default)
    layout="radial" — pie-slice radial layout centred on the frame

    Shorter clips loop to fill the longest panel's duration.
    """
    panel_count = len(clips)
    if panel_count not in _VALID_PANELS:
        raise ValueError(f"compose_split_screen requires 2, 4, or 6 clips, got {panel_count}")

    if layout == LAYOUT_RADIAL:
        return _compose_radial(clips, resolution, fps)

    # Grid layout
    cells = _panel_cells(panel_count, resolution)
    target_duration = max(c.duration for c in clips)

    positioned = []
    for clip, (x, y, cw, ch) in zip(clips, cells):
        cell_clip = _resize_crop(clip, cw, ch)
        cell_clip = _loop_to_duration(cell_clip, target_duration)
        cell_clip = cell_clip.with_fps(fps).with_position((x, y))
        positioned.append(cell_clip)

    return CompositeVideoClip(positioned, size=resolution)


def inject_split_screens(
    prepared: list[VideoClip],
    config: SplitScreenConfig,
    resolution: tuple[int, int],
    fps: int,
    rng: random.Random,
) -> list[VideoClip]:
    """Replace runs of N consecutive clips with a split screen composite.

    Each occurrence randomly selects a panel clip mode (different / same_clip /
    same_parts) and a layout (grid or radial). Picks up to config.count
    injection points, spaced at least config.min_gap clips apart.
    Returns a new list (original is not modified).
    """
    if len(prepared) < 2:
        return list(prepared)

    def pick_panels() -> int:
        return config.panels if config.panels is not None else rng.choice(_VALID_PANELS)

    candidates = list(range(len(prepared) - 1))
    rng.shuffle(candidates)

    selected: list[tuple[int, int]] = []
    used: set[int] = set()

    for idx in candidates:
        if len(selected) >= config.count:
            break

        panels = pick_panels()
        end = idx + panels

        if end > len(prepared):
            for p in sorted(_VALID_PANELS):
                if idx + p <= len(prepared):
                    panels = p
                    end = idx + p
                    break
            else:
                continue

        conflict = any(
            abs(idx - si) < config.min_gap or abs(end - (si + sp)) < config.min_gap
            for si, sp in selected
        )
        if conflict:
            continue

        for pos in range(idx, end):
            used.add(pos)
        selected.append((idx, panels))

    if not selected:
        return list(prepared)

    result = list(prepared)
    for start_idx, panels in sorted(selected, reverse=True):
        pool = result[start_idx : start_idx + panels]
        target_dur = max(c.duration for c in pool)
        panel_clips = _select_panel_clips(pool, panels, rng, target_duration=target_dur)
        layout = rng.choices(LAYOUT_MODES, weights=LAYOUT_WEIGHTS, k=1)[0]
        composite = compose_split_screen(panel_clips, resolution, fps, layout=layout)
        result[start_idx : start_idx + panels] = [composite]

    return result


# ---------------------------------------------------------------------------
# Climax burst
# ---------------------------------------------------------------------------


@dataclass
class ClimaxBurstConfig:
    """Wires audio analysis results into build_video() for the climax burst."""

    climax_time: float
    tempo: float
    beat_groups: list[tuple[float, float]]


def climax_panel_duration(tempo: float) -> float:
    """Return step duration (seconds) based on tempo.

    Fast tempo (>= FAST_TEMPO_THRESHOLD_BPM) → BARS_PER_PANEL_FAST bars.
    Slow tempo → BARS_PER_PANEL_SLOW bars.
    """
    bars = BARS_PER_PANEL_FAST if tempo >= FAST_TEMPO_THRESHOLD_BPM else BARS_PER_PANEL_SLOW
    return bars * BEATS_PER_BAR * (60.0 / tempo)


def build_climax_burst(
    clips_pool: list[VideoClip],
    tempo: float,
    resolution: tuple[int, int],
    fps: int,
    rng: random.Random,
    layout: str | None = None,
) -> VideoClip:
    """Build the climax burst sequence defined by CLIMAX_PANEL_SEQUENCE.

    Each step independently picks a panel clip mode (different / same_clip /
    same_parts) and a layout (grid or radial, biased toward radial via
    CLIMAX_LAYOUT_WEIGHTS). Steps are concatenated into a single clip.

    Pass layout explicitly to override random selection (useful for testing).
    """
    step_duration = climax_panel_duration(tempo)
    steps: list[VideoClip] = []

    for n_panels in CLIMAX_PANEL_SEQUENCE:
        panel_clips = _select_panel_clips(
            clips_pool, n_panels, rng, target_duration=step_duration
        )
        sized = [_loop_to_duration(c, step_duration) for c in panel_clips]
        step_layout = layout or rng.choices(LAYOUT_MODES, weights=CLIMAX_LAYOUT_WEIGHTS, k=1)[0]
        steps.append(compose_split_screen(sized, resolution, fps, layout=step_layout))

    return concatenate_videoclips(steps, method="compose")


def inject_climax_burst(
    prepared: list[VideoClip],
    config: ClimaxBurstConfig,
    resolution: tuple[int, int],
    fps: int,
    rng: random.Random,
) -> list[VideoClip]:
    """Replace a run of clips at the peak energy position with a climax burst.

    Finds the beat group containing config.climax_time, replaces
    len(CLIMAX_PANEL_SEQUENCE) consecutive clips starting there with the
    burst composite. Falls back to the last valid position if near the end.
    Uses all prepared clips as the panel source pool.
    """
    burst_len = len(CLIMAX_PANEL_SEQUENCE)
    if len(prepared) < burst_len:
        return list(prepared)

    target_idx = 0
    for i, (start, end) in enumerate(config.beat_groups):
        if start <= config.climax_time < end:
            target_idx = i
            break
    else:
        target_idx = min(
            range(len(config.beat_groups)),
            key=lambda i: abs(config.beat_groups[i][0] - config.climax_time),
        )

    target_idx = min(target_idx, len(prepared) - burst_len)

    burst = build_climax_burst(prepared, config.tempo, resolution, fps, rng)

    result = list(prepared)
    result[target_idx : target_idx + burst_len] = [burst]
    return result
