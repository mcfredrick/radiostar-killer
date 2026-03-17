"""Algorithmically generated visualizer clips synced to music.

Each style is a pure-numpy renderer that produces frames as (H, W, 3) uint8
arrays. Frames are beat-reactive: proximity to the nearest beat drives
brightness, pulse intensity, or bar height depending on style.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from moviepy import VideoClip

from radiostar_killer.clips import ClipAssignment

STYLES = [
    "plasma",
    "radial_pulse",
    "spectrum_bars",
    "waveform",
    "starfield",
    "tunnel",
    "grid_pulse",
]


@dataclass
class GeneratedClipsConfig:
    rate: float  # fraction of clip assignments to replace (0.0–1.0)
    style: str  # one of STYLES, or "random" to pick per clip
    tempo: float
    beat_times: np.ndarray
    overlay_alpha: float | None = None  # when set, composite over source video


def _beat_envelope(t: float, beat_times: np.ndarray, decay: float = 8.0) -> float:
    """0→1 intensity that peaks on each beat and decays exponentially between them."""
    if len(beat_times) == 0:
        return 0.5
    return float(np.exp(-decay * np.abs(beat_times - t).min()))


def _hsv_to_rgb(h: np.ndarray, s: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Vectorized HSV→RGB. All inputs in [0,1]; output shape is input_shape+(3,) in [0,1]."""
    i = (h * 6).astype(int) % 6
    f = h * 6 - np.floor(h * 6)
    p = v * (1 - s)
    q = v * (1 - f * s)
    tv = v * (1 - (1 - f) * s)
    r = np.select([i == 0, i == 1, i == 2, i == 3, i == 4], [v, q, p, p, tv], default=v)
    g = np.select([i == 0, i == 1, i == 2, i == 3, i == 4], [tv, v, v, q, p], default=p)
    b = np.select([i == 0, i == 1, i == 2, i == 3, i == 4], [p, p, tv, v, v], default=q)
    return np.stack([r, g, b], axis=-1)


def _hue_to_rgb(hue: float) -> np.ndarray:
    """Scalar hue [0,1] → float32 RGB array [0,1] at full saturation and value."""
    h6 = hue * 6
    hi = int(h6) % 6
    f = h6 - int(h6)
    sector_rgb: list[tuple[float, float, float]] = [
        (1.0, f, 0.0), (1 - f, 1.0, 0.0), (0.0, 1.0, f),
        (0.0, 1 - f, 1.0), (f, 0.0, 1.0), (1.0, 0.0, 1 - f),
    ]
    return np.array(sector_rgb[hi], dtype=np.float32)


def _plasma_frame_fn(
    W: int, H: int, tempo: float, beat_times: np.ndarray, energy: float
) -> Callable[[float], np.ndarray]:
    """Classic demo-scene plasma: overlapping sine waves mapped to HSV color.

    Tempo controls wave animation speed; beats pulse saturation and brightness.
    """
    x = np.linspace(0, 4 * np.pi, W, dtype=np.float32)
    y = np.linspace(0, 4 * np.pi, H, dtype=np.float32)
    X, Y = np.meshgrid(x, y)  # (H, W)
    R = np.sqrt(X**2 + Y**2)
    speed = tempo / 60.0  # beats per second

    def frame(t: float) -> np.ndarray:
        bi = _beat_envelope(t, beat_times)
        phase = t * speed
        v = (
            np.sin(X * 0.5 + phase)
            + np.sin(Y * 0.5 + phase * 0.71)
            + np.sin((X + Y) * 0.35 + phase * 1.3)
            + np.sin(R * 0.4 + phase * 0.9)
        )
        v = (v + 4) / 8  # normalize to [0, 1]
        hue = (v + t * 0.05) % 1.0
        sat = np.full_like(v, float(np.clip(0.7 + 0.3 * bi, 0.0, 1.0)))
        val = np.clip(energy * (0.4 + 0.6 * bi) + v * 0.2, 0.0, 1.0)
        return (_hsv_to_rgb(hue, sat, val) * 255).astype(np.uint8)

    return frame


def _radial_pulse_frame_fn(
    W: int, H: int, tempo: float, beat_times: np.ndarray, energy: float
) -> Callable[[float], np.ndarray]:
    """Colored rings burst from center on each beat and expand outward.

    Each beat emits a uniquely-hued ring; rings fade as they travel.
    """
    cx, cy = W / 2.0, H / 2.0
    Y_g, X_g = np.mgrid[0:H, 0:W]
    dist = np.sqrt((X_g - cx) ** 2 + (Y_g - cy) ** 2).astype(np.float32)
    max_d = float(np.sqrt(cx**2 + cy**2))
    ring_speed = max_d * 1.5  # px/s — reaches screen edge in ~0.67 s

    def frame(t: float) -> np.ndarray:
        rgb = np.zeros((H, W, 3), dtype=np.float32)
        for idx, beat_t in enumerate(beat_times):
            if beat_t > t:
                break
            age = t - beat_t
            radius = age * ring_speed
            if radius > max_d * 1.5:
                continue
            ring_w = 12.0 + energy * 10
            mask = np.exp(-((dist - radius) ** 2) / (2 * ring_w**2))  # (H, W)
            hue = (idx * 0.13 + t * 0.03) % 1.0
            # Scalar HSV → RGB for ring color
            h6 = hue * 6
            hi = int(h6) % 6
            f = h6 - int(h6)
            sector_rgb: list[tuple[float, float, float]] = [
                (1.0, f, 0.0), (1 - f, 1.0, 0.0), (0.0, 1.0, f),
                (0.0, 1 - f, 1.0), (f, 0.0, 1.0), (1.0, 0.0, 1 - f),
            ]
            color = np.array(sector_rgb[hi], dtype=np.float32)
            intensity = np.exp(-age * 1.5) * energy
            rgb += mask[:, :, np.newaxis] * color * intensity
        return np.clip(rgb * 255, 0, 255).astype(np.uint8)

    return frame


def _spectrum_bars_frame_fn(
    W: int, H: int, tempo: float, beat_times: np.ndarray, energy: float
) -> Callable[[float], np.ndarray]:
    """EQ-style spectrum bars simulated from tempo + beat envelope.

    Bar heights pulse on each beat; each bar has a distinct hue with a
    brightness gradient (bright at top, dimmer at base).
    """
    N = 32
    bar_w = max(1, W // N)
    i_arr = np.arange(N, dtype=np.float32)

    def frame(t: float) -> np.ndarray:
        bi = _beat_envelope(t, beat_times)
        rgb = np.zeros((H, W, 3), dtype=np.float32)
        # Higher bars decay more from beats (simulates natural frequency rolloff)
        freq_decay = 1.0 - i_arr / N * 0.5
        # Per-bar oscillation at tempo harmonics keeps motion between beats
        osc = 0.3 * np.sin(t * tempo / 60 * 2 * np.pi * (1 + i_arr * 0.15))
        heights_frac = np.clip(
            (bi * freq_decay + np.maximum(0.0, osc)) * energy, 0.0, 1.0
        )
        heights_px = (heights_frac * H * 0.9).astype(int)
        for i in range(N):
            h_px = heights_px[i]
            if h_px == 0:
                continue
            x0 = i * bar_w + 1
            x1 = min(x0 + bar_w - 2, W)
            y0 = H - h_px
            hue = float(i) / N
            rows = np.arange(h_px, dtype=np.float32)
            frac = rows / max(h_px - 1, 1)  # 0 at top of bar, 1 at bottom
            val = 1.0 - 0.4 * frac  # bright at top, dimmer at base
            colors = _hsv_to_rgb(
                np.full(h_px, hue),
                np.full(h_px, 0.9),
                val,
            )  # (h_px, 3)
            rgb[y0:H, x0:x1] = colors[:, np.newaxis, :]
        return np.clip(rgb * 255, 0, 255).astype(np.uint8)

    return frame


def _waveform_frame_fn(
    W: int, H: int, tempo: float, beat_times: np.ndarray, energy: float
) -> Callable[[float], np.ndarray]:
    """Multiple glowing sine waves that pulse in amplitude and thickness on each beat.

    Each wave has a distinct hue cycling over time. Beat envelope widens the
    glow radius, making waves bloom on every hit.
    """
    N = 5
    x = np.linspace(0, 2 * np.pi, W, dtype=np.float32)[np.newaxis, :]  # (1, W)
    Y_grid = np.arange(H, dtype=np.float32)[:, np.newaxis]  # (H, 1)
    wave_freqs = (1.0 + np.arange(N) * 0.7).astype(np.float32)
    wave_speeds = (1.0 + np.arange(N) * 0.3).astype(np.float32)
    speed = tempo / 60.0

    def frame(t: float) -> np.ndarray:
        bi = _beat_envelope(t, beat_times)
        img = np.zeros((H, W, 3), dtype=np.float32)
        sigma = 1.5 + bi * 5.0  # glow width blooms on beat

        for i in range(N):
            phase = t * speed * float(wave_speeds[i])
            amp = (0.06 + 0.10 * bi) * H
            y_wave = H / 2.0 + amp * np.sin(x * float(wave_freqs[i]) + phase)  # (1, W)
            dist2 = (Y_grid - y_wave) ** 2  # (H, W)
            glow = np.exp(-dist2 / (2.0 * sigma**2))  # (H, W)
            hue = (float(i) / N + t * 0.04) % 1.0
            color = _hue_to_rgb(hue)
            brightness = (0.4 + 0.6 * bi) * energy
            img += glow[:, :, np.newaxis] * color * brightness

        return np.clip(img * 255, 0, 255).astype(np.uint8)

    return frame


def _starfield_frame_fn(
    W: int, H: int, tempo: float, beat_times: np.ndarray, energy: float
) -> Callable[[float], np.ndarray]:
    """Stars fly outward from center; beats surge their brightness and size.

    Each star has a fixed angle and staggered phase so they stream continuously.
    Half the stars are rainbow (hue from angle); the other half are white.
    Stars are rendered as gaussian blobs that grow on each beat.
    """
    cx, cy = W / 2.0, H / 2.0
    rng = np.random.default_rng(42)
    N = 200
    angles = rng.uniform(0, 2 * np.pi, N).astype(np.float32)
    offsets = rng.uniform(0, 2.0, N).astype(np.float32)
    is_white = rng.random(N) < 0.5  # fixed per star: True = white, False = rainbow
    max_r = float(np.sqrt(cx**2 + cy**2)) * 1.05
    period = 2.0  # seconds for one star to cross the screen
    BASE_R = 4.0  # gaussian radius at rest
    BEAT_R = 3.0  # extra radius added at peak beat
    LOOP_R = 8    # pixel neighborhood to scatter (covers ~2 sigma at max size)

    def frame(t: float) -> np.ndarray:
        bi = _beat_envelope(t, beat_times)
        r_frac = ((t + offsets) % period) / period  # [0,1] per star
        r = r_frac * max_r
        xs = (cx + r * np.cos(angles)).astype(int)
        ys = (cy + r * np.sin(angles)).astype(int)

        img = np.zeros((H, W, 3), dtype=np.float32)
        brightness = r_frac * energy * (0.6 + 1.0 * bi)

        # Rainbow colors for non-white stars
        hues = (angles / (2.0 * np.pi) + t * 0.05) % 1.0
        rainbow = _hsv_to_rgb(hues, np.ones(N, dtype=np.float32), np.ones(N, dtype=np.float32))
        colors = np.where(is_white[:, np.newaxis], np.ones((N, 3), dtype=np.float32), rainbow)

        # Gaussian blob radius pulses on beat
        glow_r = BASE_R + BEAT_R * bi
        inv_2r2 = 1.0 / (2.0 * glow_r**2)

        for dy in range(-LOOP_R, LOOP_R + 1):
            for dx in range(-LOOP_R, LOOP_R + 1):
                w = float(np.exp(-(dx**2 + dy**2) * inv_2r2))
                if w < 0.04:
                    continue
                ys_off = np.clip(ys + dy, 0, H - 1)
                xs_off = np.clip(xs + dx, 0, W - 1)
                np.add.at(img[:, :, 0], (ys_off, xs_off), colors[:, 0] * brightness * w)
                np.add.at(img[:, :, 1], (ys_off, xs_off), colors[:, 1] * brightness * w)
                np.add.at(img[:, :, 2], (ys_off, xs_off), colors[:, 2] * brightness * w)

        img += bi * energy * 0.04
        return np.clip(img * 255, 0, 255).astype(np.uint8)

    return frame


def _tunnel_frame_fn(
    W: int, H: int, tempo: float, beat_times: np.ndarray, energy: float
) -> Callable[[float], np.ndarray]:
    """Zoom tunnel: concentric rings rush toward the viewer while hue rotates.

    Ring density and zoom speed are driven by tempo; beats pulse brightness.
    Hue varies by screen angle, creating a spinning color wheel effect.
    """
    cx, cy = W / 2.0, H / 2.0
    Y_g, X_g = np.mgrid[0:H, 0:W]
    dx = (X_g - cx).astype(np.float32)
    dy = (Y_g - cy).astype(np.float32)
    r_norm = (np.sqrt(dx**2 + dy**2) / float(np.sqrt(cx**2 + cy**2))).astype(np.float32)
    angle = np.arctan2(dy, dx).astype(np.float32)  # (H, W) in (-pi, pi)
    speed = tempo / 60.0 * 0.4  # ring zoom speed

    def frame(t: float) -> np.ndarray:
        bi = _beat_envelope(t, beat_times)
        # Rings move outward (zoom-in illusion): modulate by distance
        ring_phase = (r_norm * 5.0 - t * speed) % 1.0  # (H, W)

        # Hue from screen angle + slow rotation
        hue = (angle / (2.0 * np.pi) + t * 0.06) % 1.0  # (H, W)
        sat = np.full_like(hue, 0.9)
        # Value: ring stripes modulated by beat
        val = np.clip(ring_phase * energy * (0.5 + 0.5 * bi), 0.0, 1.0)
        # Fade out singularity at center
        center_fade = np.clip(r_norm / 0.05, 0.0, 1.0)
        val = val * center_fade

        rgb = _hsv_to_rgb(hue, sat, val)
        return np.clip(rgb * 255, 0, 255).astype(np.uint8)

    return frame


def _grid_pulse_frame_fn(
    W: int, H: int, tempo: float, beat_times: np.ndarray, energy: float
) -> Callable[[float], np.ndarray]:
    """Grid of glowing dots that ripple outward from center on each beat.

    Each dot's hue comes from its distance to the screen center. A continuous
    ripple wave propagates outward; the beat envelope pulses dot radius and brightness.
    """
    cx, cy = W / 2.0, H / 2.0
    spacing = max(16, min(W, H) // 20)

    # Pixel coordinate grids
    Y_px, X_px = np.mgrid[0:H, 0:W]

    # Nearest dot center for every pixel (vectorized mod-based snapping)
    dot_x = (np.round((X_px - spacing / 2) / spacing) * spacing + spacing / 2).astype(np.float32)
    dot_y = (np.round((Y_px - spacing / 2) / spacing) * spacing + spacing / 2).astype(np.float32)
    dot_x = np.clip(dot_x, 0, W - 1)
    dot_y = np.clip(dot_y, 0, H - 1)

    # Each pixel's distance to its nearest dot center
    dist_to_dot = np.sqrt((X_px - dot_x) ** 2 + (Y_px - dot_y) ** 2).astype(np.float32)

    # Each pixel's dot's distance from screen center (for ripple + color)
    dot_dist_center = np.sqrt((dot_x - cx) ** 2 + (dot_y - cy) ** 2).astype(np.float32)
    max_dist = float(dot_dist_center.max()) + 1.0

    wave_speed = max_dist * 0.8  # ripple crosses screen in ~1.25s

    def frame(t: float) -> np.ndarray:
        bi = _beat_envelope(t, beat_times)
        dot_r = float(spacing) * (0.25 + 0.20 * bi)  # dot radius pulses on beat
        dot_mask = np.exp(-dist_to_dot**2 / (2.0 * dot_r**2))  # (H, W)

        # Ripple wave propagating outward from center
        wave_r = (t * wave_speed) % (max_dist * 1.1)
        ripple = np.exp(-((dot_dist_center - wave_r) ** 2) / (wave_speed * 0.12) ** 2)

        brightness = np.clip((ripple * 0.7 + bi * 0.4) * energy, 0.0, 1.0)

        # Hue from dot distance to center + slow drift
        hue = (dot_dist_center / max_dist + t * 0.08) % 1.0
        sat = np.full_like(hue, 0.9)
        val = dot_mask * brightness

        rgb = _hsv_to_rgb(hue, sat, val)
        return np.clip(rgb * 255, 0, 255).astype(np.uint8)

    return frame


_FACTORIES: dict[str, Callable[..., Callable[[float], np.ndarray]]] = {
    "plasma": _plasma_frame_fn,
    "radial_pulse": _radial_pulse_frame_fn,
    "spectrum_bars": _spectrum_bars_frame_fn,
    "waveform": _waveform_frame_fn,
    "starfield": _starfield_frame_fn,
    "tunnel": _tunnel_frame_fn,
    "grid_pulse": _grid_pulse_frame_fn,
}


def _make_overlay_clip(
    frame_fn: Callable[[float], np.ndarray],
    duration: float,
    fps: int,
    overlay_alpha: float,
) -> VideoClip:
    """Wrap a frame function into an RGBA VideoClip for overlay compositing.

    Alpha is luminance-based: dark areas become transparent, bright areas opaque.
    A simple last-frame cache avoids computing frames twice per timestamp
    (once for the RGB clip, once for the mask).
    """
    _cache: list = [None, None]  # [last_t, last_frame]

    def get_frame(t: float) -> np.ndarray:
        if _cache[0] != t:
            _cache[0] = t
            _cache[1] = frame_fn(t)
        return _cache[1]  # type: ignore[return-value]

    def mask_frame(t: float) -> np.ndarray:
        rgb = get_frame(t).astype(np.float32)
        return np.clip(rgb.mean(axis=2) / 255.0 * overlay_alpha, 0.0, 1.0)

    clip = VideoClip(get_frame, duration=duration).with_fps(fps)
    mask = VideoClip(mask_frame, duration=duration).with_fps(fps)
    return clip.with_mask(mask)


def make_generated_clip(
    style: str,
    duration: float,
    resolution: tuple[int, int],
    fps: int,
    tempo: float,
    beat_times: np.ndarray,
    energy: float = 0.8,
    overlay_alpha: float | None = None,
) -> VideoClip:
    """Return a VideoClip rendered by the named visualizer style.

    When overlay_alpha is set (0.0–1.0), the clip carries a luminance-based
    alpha mask so it can be composited over video footage: dark pixels become
    transparent, bright visual elements show through at full opacity.
    """
    if style not in _FACTORIES:
        raise ValueError(f"Unknown style '{style}'. Choose from: {STYLES}")
    W, H = resolution
    frame_fn = _FACTORIES[style](W, H, tempo, beat_times, energy)
    if overlay_alpha is not None:
        return _make_overlay_clip(frame_fn, duration, fps, overlay_alpha)
    return VideoClip(frame_fn, duration=duration).with_fps(fps)


def inject_generated_clips(
    assignments: list[ClipAssignment],
    config: GeneratedClipsConfig,
    resolution: tuple[int, int],
    rng: random.Random,
) -> list[ClipAssignment]:
    """Replace a random subset of clip assignments with generated visualizer clips.

    For each selected assignment, the real clip is swapped for a visualizer
    generator whose beat_times are derived from tempo, so beats align to t=0
    of the clip regardless of position in the song.

    When config.overlay_alpha is set, the assignment retains its original path
    so the video is still loaded as the base layer, and the generator is
    composited on top with luminance-based transparency.
    """
    beat_interval = 60.0 / config.tempo
    W, H = resolution
    result: list[ClipAssignment] = []
    for assignment in assignments:
        if rng.random() < config.rate:
            chosen = rng.choice(STYLES) if config.style == "random" else config.style
            # Local beat times from t=0 so visual is always in tempo phase
            local_beats = np.arange(
                0.0,
                assignment.target_duration + beat_interval * 0.5,
                beat_interval,
            )
            gen = _FACTORIES[chosen](W, H, config.tempo, local_beats, energy=0.8)
            result.append(
                ClipAssignment(
                    path=assignment.path,
                    target_duration=assignment.target_duration,
                    original_duration=assignment.original_duration,
                    generator=gen,
                    overlay_alpha=config.overlay_alpha,
                )
            )
        else:
            result.append(assignment)
    return result
