"""Title card and MTV/VH1-style info overlay for music videos."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from moviepy import (
    ColorClip,
    CompositeVideoClip,
    TextClip,
    VideoClip,
)
from moviepy.video.fx import CrossFadeIn, CrossFadeOut


@dataclass(frozen=True)
class TitleCardConfig:
    """Configuration for the opening title card."""

    title: str
    subtitle: str | None = None
    duration: float = 3.5
    fade_duration: float = 0.8
    bg_color: tuple[int, int, int] = (0, 0, 0)
    text_color: str = "white"
    font: str = "Arial"


@dataclass(frozen=True)
class InfoOverlayConfig:
    """Configuration for the MTV/VH1-style song info overlay."""

    title: str
    artist: str
    album: str | None = None
    display_duration: float = 8.0
    fade_in_duration: float = 0.5
    fade_out_duration: float = 1.5
    delay: float = 1.0
    font: str = "Arial"
    text_color: str = "white"


def snap_to_nearest_beat(
    target_duration: float,
    beat_times: np.ndarray,
) -> float:
    """Find the beat time closest to target_duration.

    Returns target_duration unchanged if beat_times is empty.
    """
    if len(beat_times) == 0:
        return target_duration

    idx = int(np.argmin(np.abs(beat_times - target_duration)))
    return float(beat_times[idx])


def create_title_card(
    config: TitleCardConfig,
    resolution: tuple[int, int],
    fps: int,
) -> VideoClip:
    """Create a full-screen title card clip.

    Returns a clip with the title (and optional subtitle) centered on
    a solid background, with fade-in and fade-out.
    """
    width, height = resolution

    bg = ColorClip(size=resolution, color=config.bg_color, duration=config.duration)

    max_text_w = int(width * 0.8)
    title_font_size = width // 18
    title_clip = TextClip(
        text=config.title,
        font_size=title_font_size,
        color=config.text_color,
        font=config.font,
        size=(max_text_w, None),
        text_align="center",
    )

    layers: list[VideoClip] = [bg]

    if config.subtitle:
        subtitle_font_size = width // 28
        subtitle_clip = TextClip(
            text=config.subtitle,
            font_size=subtitle_font_size,
            color=config.text_color,
            font=config.font,
            size=(max_text_w, None),
            text_align="center",
        )

        # Stack title and subtitle vertically centered
        gap = height // 30
        total_h = title_clip.h + gap + subtitle_clip.h
        title_y = (height - total_h) // 2
        subtitle_y = title_y + title_clip.h + gap

        title_clip = title_clip.with_position(("center", title_y))
        subtitle_clip = subtitle_clip.with_position(("center", subtitle_y))

        title_clip = title_clip.with_duration(config.duration)
        subtitle_clip = subtitle_clip.with_duration(config.duration)

        layers.extend([title_clip, subtitle_clip])
    else:
        title_clip = title_clip.with_position("center")
        title_clip = title_clip.with_duration(config.duration)
        layers.append(title_clip)

    card = CompositeVideoClip(layers, size=resolution)
    card = card.with_fps(fps)
    card = card.with_duration(config.duration)

    fade = min(config.fade_duration, config.duration / 2)
    card = card.with_effects([CrossFadeIn(fade), CrossFadeOut(fade)])

    return card


def create_info_overlay(
    config: InfoOverlayConfig,
    resolution: tuple[int, int],
    fps: int,
) -> VideoClip:
    """Create an MTV/VH1-style song info overlay.

    Returns a transparent-background CompositeVideoClip at the full
    resolution that appears after config.delay, shows song info with
    a semi-transparent background bar, then fades out.
    """
    width, height = resolution
    margin_x = width // 30
    margin_y = height // 25

    title_font_size = width // 36
    artist_font_size = width // 44
    album_font_size = width // 50
    line_gap = height // 120
    max_overlay_text_w = int(width * 0.45)

    # Build text clips
    title_clip = TextClip(
        text=config.title,
        font_size=title_font_size,
        color=config.text_color,
        font=config.font,
        size=(max_overlay_text_w, None),
    )
    artist_clip = TextClip(
        text=config.artist,
        font_size=artist_font_size,
        color=config.text_color,
        font=config.font,
        size=(max_overlay_text_w, None),
    )

    text_clips = [title_clip, artist_clip]
    if config.album:
        album_clip = TextClip(
            text=config.album,
            font_size=album_font_size,
            color=config.text_color,
            font=config.font,
            size=(max_overlay_text_w, None),
        )
        text_clips.append(album_clip)

    # Calculate background bar dimensions
    padding_x = width // 60
    padding_y = height // 80
    max_text_w = max(c.w for c in text_clips)
    total_text_h = sum(c.h for c in text_clips) + line_gap * (len(text_clips) - 1)

    bar_w = max_text_w + 2 * padding_x
    bar_h = total_text_h + 2 * padding_y

    # Position: bottom-left
    bar_x = margin_x
    bar_y = height - margin_y - bar_h

    # Semi-transparent background bar
    bar = ColorClip(size=(bar_w, bar_h), color=(0, 0, 0))
    bar = bar.with_opacity(0.7)
    bar = bar.with_position((bar_x, bar_y))

    # Position text lines inside the bar
    overlay_duration = config.display_duration
    positioned_texts: list[VideoClip] = []
    current_y = bar_y + padding_y
    for tc in text_clips:
        tc = tc.with_position((bar_x + padding_x, current_y))
        tc = tc.with_duration(overlay_duration)
        positioned_texts.append(tc)
        current_y += tc.h + line_gap

    bar = bar.with_duration(overlay_duration)

    # Compose all layers
    overlay_layers: list[VideoClip] = [bar] + positioned_texts
    overlay = CompositeVideoClip(
        overlay_layers,
        size=resolution,
    )
    overlay = overlay.with_duration(overlay_duration)
    overlay = overlay.with_start(config.delay)

    # Apply fades
    overlay = overlay.with_effects([
        CrossFadeIn(config.fade_in_duration),
        CrossFadeOut(config.fade_out_duration),
    ])

    return overlay
