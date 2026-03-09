"""Streaming format presets for video export."""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class FormatPreset:
    name: str
    resolution: tuple[int, int]
    fps: int
    codec: str = "libx264"
    audio_codec: str = "aac"
    bitrate: str | None = None
    audio_bitrate: str | None = None
    max_duration: float | None = None


PRESETS: dict[str, FormatPreset] = {
    "youtube": FormatPreset(
        name="youtube",
        resolution=(1920, 1080),
        fps=30,
    ),
    "youtube-shorts": FormatPreset(
        name="youtube-shorts",
        resolution=(1080, 1920),
        fps=30,
        max_duration=180.0,
    ),
    "tiktok": FormatPreset(
        name="tiktok",
        resolution=(1080, 1920),
        fps=30,
        bitrate="12M",
        audio_bitrate="256k",
    ),
    "instagram-reels": FormatPreset(
        name="instagram-reels",
        resolution=(1080, 1920),
        fps=30,
        bitrate="3500k",
        audio_bitrate="128k",
    ),
}


def resolve_format(
    format_name: str | None = None,
    resolution_override: tuple[int, int] | None = None,
    fps_override: int | None = None,
) -> FormatPreset:
    """Resolve a format preset with optional CLI overrides.

    Defaults to 'youtube' when no format name is given.
    """
    name = format_name or "youtube"
    if name not in PRESETS:
        raise ValueError(
            f"Unknown format '{name}'. "
            f"Available formats: {', '.join(sorted(PRESETS))}"
        )
    preset = PRESETS[name]
    if resolution_override is not None:
        preset = replace(preset, resolution=resolution_override)
    if fps_override is not None:
        preset = replace(preset, fps=fps_override)
    return preset
