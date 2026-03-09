"""Visual effects and transitions for beat-synced video clips."""

import random
from dataclasses import dataclass

import numpy as np
from moviepy import CompositeVideoClip, VideoClip
from moviepy.video.fx import (
    BlackAndWhite,
    CrossFadeIn,
    CrossFadeOut,
    GammaCorrection,
    InvertColors,
    LumContrast,
    MirrorX,
    MirrorY,
    MultiplyColor,
    Painting,
    SlideIn,
)
from PIL import Image
from scipy.ndimage import gaussian_filter


def _random_gamma(rng: random.Random) -> GammaCorrection:
    return GammaCorrection(gamma=rng.uniform(0.5, 1.5))


def _random_brightness(rng: random.Random) -> MultiplyColor:
    return MultiplyColor(factor=rng.uniform(0.7, 1.4))


def _random_contrast(rng: random.Random) -> LumContrast:
    return LumContrast(
        lum=rng.uniform(-20, 20),
        contrast=rng.uniform(-50, 50),
    )


def _black_and_white(_rng: random.Random) -> BlackAndWhite:
    return BlackAndWhite()


def _invert_colors(_rng: random.Random) -> InvertColors:
    return InvertColors()


def _mirror_x(_rng: random.Random) -> MirrorX:
    return MirrorX()


def _mirror_y(_rng: random.Random) -> MirrorY:
    return MirrorY()


def _random_painting(rng: random.Random) -> Painting:
    return Painting(
        saturation=rng.uniform(1.0, 2.0),
        black=rng.uniform(0.003, 0.01),
    )


def _make_zoom_in(rng: random.Random, clip: VideoClip) -> VideoClip:
    """Apply a gradual zoom-in effect over the clip's duration."""
    end_zoom = rng.uniform(1.1, 1.3)
    w, h = clip.size
    duration = clip.duration

    def zoom_frame(get_frame: object, t: float) -> np.ndarray:
        frame = clip.get_frame(t)
        progress = t / duration if duration > 0 else 0.0
        zoom = 1.0 + (end_zoom - 1.0) * progress

        # Crop center region, then resize back
        new_w = int(w / zoom)
        new_h = int(h / zoom)
        x_start = (w - new_w) // 2
        y_start = (h - new_h) // 2

        cropped = frame[y_start : y_start + new_h, x_start : x_start + new_w]
        img = Image.fromarray(cropped.astype(np.uint8))
        resized = img.resize((w, h), Image.Resampling.LANCZOS)
        return np.asarray(resized)

    return clip.transform(zoom_frame)


def _make_blur(rng: random.Random, clip: VideoClip) -> VideoClip:
    """Apply a gaussian blur effect to every frame."""
    sigma = rng.uniform(1.0, 3.0)

    def blur_frame(get_frame: object, t: float) -> np.ndarray:
        frame = clip.get_frame(t)
        return gaussian_filter(frame, sigma=(sigma, sigma, 0))  # type: ignore[no-any-return]

    return clip.transform(blur_frame)


def _make_color_tint(rng: random.Random, clip: VideoClip) -> VideoClip:
    """Multiply each RGB channel by a random factor for a color tint."""
    factors = np.array(
        [rng.uniform(0.7, 1.3), rng.uniform(0.7, 1.3), rng.uniform(0.7, 1.3)]
    )

    def tint_frame(get_frame: object, t: float) -> np.ndarray:
        frame = clip.get_frame(t).astype(np.float64)
        frame *= factors
        return np.clip(frame, 0, 255).astype(np.uint8)  # type: ignore[no-any-return]

    return clip.transform(tint_frame)


# Built-in effects that can be applied via with_effects()
_BUILTIN_EFFECTS = [
    _random_gamma,
    _random_brightness,
    _random_contrast,
    _black_and_white,
    _invert_colors,
    _mirror_x,
    _mirror_y,
    _random_painting,
]

# Custom effects that transform the clip directly
_CUSTOM_EFFECTS = [
    _make_zoom_in,
    _make_blur,
    _make_color_tint,
]

EFFECT_COUNT = len(_BUILTIN_EFFECTS) + len(_CUSTOM_EFFECTS)

# Named effects for explicit testing and selection.
# Builtin effects take (rng) and return an fx object; custom effects take (rng, clip) and return a clip.
BUILTIN_NAMED: dict[str, object] = {
    "gamma": _random_gamma,
    "brightness": _random_brightness,
    "contrast": _random_contrast,
    "black_and_white": _black_and_white,
    "invert": _invert_colors,
    "mirror_x": _mirror_x,
    "mirror_y": _mirror_y,
    "painting": _random_painting,
}

CUSTOM_NAMED: dict[str, object] = {
    "zoom_in": _make_zoom_in,
    "blur": _make_blur,
    "color_tint": _make_color_tint,
}


def apply_named_effect(name: str, clip: VideoClip, rng: random.Random) -> VideoClip:
    """Apply a specific named effect to a clip. Raises KeyError for unknown names."""
    if name in BUILTIN_NAMED:
        effect = BUILTIN_NAMED[name](rng)  # type: ignore[operator]
        return clip.with_effects([effect])
    if name in CUSTOM_NAMED:
        return CUSTOM_NAMED[name](rng, clip)  # type: ignore[operator]
    raise KeyError(f"Unknown effect '{name}'. Available: {sorted(list(BUILTIN_NAMED) + list(CUSTOM_NAMED))}")


def apply_random_effect(
    clip: VideoClip,
    rng: random.Random,
    effect_rate: float,
) -> VideoClip:
    """Maybe apply a random visual effect to a clip.

    Returns the original clip unchanged if the random roll exceeds effect_rate,
    or a new clip with a random effect applied.
    """
    if rng.random() >= effect_rate:
        return clip

    total = len(_BUILTIN_EFFECTS) + len(_CUSTOM_EFFECTS)
    idx = rng.randrange(total)

    if idx < len(_BUILTIN_EFFECTS):
        effect = _BUILTIN_EFFECTS[idx](rng)
        return clip.with_effects([effect])
    else:
        custom_idx = idx - len(_BUILTIN_EFFECTS)
        return _CUSTOM_EFFECTS[custom_idx](rng, clip)


# --- Transitions ---

TRANSITION_TYPES = [
    "crossfade",
    "slide_left",
    "slide_right",
    "slide_top",
    "slide_bottom",
]

_SLIDE_DIRECTIONS = {
    "slide_left": "left",
    "slide_right": "right",
    "slide_top": "top",
    "slide_bottom": "bottom",
}


@dataclass
class TransitionSpec:
    """Describes a transition between two clips."""

    transition_type: str
    duration: float


def select_transition(
    rng: random.Random,
    transition_rate: float,
    duration: float,
    clip_a_duration: float,
    clip_b_duration: float,
) -> TransitionSpec | None:
    """Select a random transition for a clip boundary.

    Returns None if the random roll exceeds transition_rate (hard cut).
    Duration is clamped to avoid overlap exceeding clip lengths.
    """
    if rng.random() >= transition_rate:
        return None

    clamped = min(duration, clip_a_duration * 0.4, clip_b_duration * 0.4)
    if clamped <= 0:
        return None

    transition_type = rng.choice(TRANSITION_TYPES)
    return TransitionSpec(transition_type=transition_type, duration=clamped)


def compose_with_transitions(
    clips: list[VideoClip],
    transitions: list[TransitionSpec | None],
) -> VideoClip:
    """Compose clips with transition overlaps into a single CompositeVideoClip.

    Each entry in transitions corresponds to the boundary between clips[i]
    and clips[i+1]. None means a hard cut (no overlap).
    """
    if not clips:
        raise ValueError("No clips to compose")
    if len(transitions) != len(clips) - 1:
        raise ValueError("transitions must have len(clips) - 1 entries")

    # Calculate start times accounting for overlaps
    timed_clips: list[VideoClip] = []
    current_time = 0.0

    for i, clip in enumerate(clips):
        # Apply crossfade-out to outgoing clip if there's a transition after it
        trans_out = transitions[i] if i < len(transitions) else None
        if trans_out is not None:
            clip = clip.with_effects([CrossFadeOut(trans_out.duration)])

        # Apply crossfade-in and optional slide to incoming clip
        trans_in = transitions[i - 1] if i > 0 else None
        if trans_in is not None:
            fx = [CrossFadeIn(trans_in.duration)]
            direction = _SLIDE_DIRECTIONS.get(trans_in.transition_type)
            if direction:
                fx.append(SlideIn(trans_in.duration, direction))
            clip = clip.with_effects(fx)

        clip = clip.with_start(current_time)
        timed_clips.append(clip)

        # Advance time: full duration minus any overlap with the next clip
        overlap = trans_out.duration if trans_out is not None else 0.0
        current_time += clip.duration - overlap

    return CompositeVideoClip(timed_clips)
