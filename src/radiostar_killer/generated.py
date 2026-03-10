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

STYLES = ["plasma", "radial_pulse", "spectrum_bars"]


@dataclass
class GeneratedClipsConfig:
    rate: float  # fraction of clip assignments to replace (0.0–1.0)
    style: str  # one of STYLES, or "random" to pick per clip
    tempo: float
    beat_times: np.ndarray


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


_FACTORIES: dict[str, Callable[..., Callable[[float], np.ndarray]]] = {
    "plasma": _plasma_frame_fn,
    "radial_pulse": _radial_pulse_frame_fn,
    "spectrum_bars": _spectrum_bars_frame_fn,
}


def make_generated_clip(
    style: str,
    duration: float,
    resolution: tuple[int, int],
    fps: int,
    tempo: float,
    beat_times: np.ndarray,
    energy: float = 0.8,
) -> VideoClip:
    """Return a VideoClip rendered by the named visualizer style."""
    if style not in _FACTORIES:
        raise ValueError(f"Unknown style '{style}'. Choose from: {STYLES}")
    W, H = resolution
    frame_fn = _FACTORIES[style](W, H, tempo, beat_times, energy)
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
                )
            )
        else:
            result.append(assignment)
    return result
