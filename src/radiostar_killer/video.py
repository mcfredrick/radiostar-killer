"""Video clip preparation, concatenation, and export."""

import random
from pathlib import Path

from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    VideoClip,
    VideoFileClip,
    concatenate_videoclips,
)

from radiostar_killer.clips import ClipAssignment
from radiostar_killer.effects import (
    apply_random_effect,
    compose_with_transitions,
    select_transition,
)
from radiostar_killer.formats import FormatPreset
from radiostar_killer.overlays import (
    InfoOverlayConfig,
    TitleCardConfig,
    create_info_overlay,
    create_title_card,
)
from radiostar_killer.generated import GeneratedClipsConfig, inject_generated_clips
from radiostar_killer.splitscreen import (
    CLIMAX_PANEL_SEQUENCE,
    ClimaxBurstConfig,
    SplitScreenConfig,
    inject_climax_burst,
    inject_split_screens,
)


def _resize_crop(
    clip: VideoFileClip,
    target_w: int,
    target_h: int,
) -> VideoFileClip:
    """Resize clip to cover target resolution, then center-crop to fit.

    Preserves aspect ratio by scaling to fill (no black bars, no stretching),
    then cropping the excess from the center.
    """
    src_w, src_h = clip.size
    scale = max(target_w / src_w, target_h / src_h)
    clip = clip.resized(scale)

    # Center-crop to exact target
    cur_w, cur_h = clip.size
    x_center = cur_w / 2
    y_center = cur_h / 2
    clip = clip.cropped(
        x1=x_center - target_w / 2,
        y1=y_center - target_h / 2,
        x2=x_center + target_w / 2,
        y2=y_center + target_h / 2,
    )
    return clip


def prepare_clip(
    path: Path,
    target_duration: float,
    resolution: tuple[int, int],
    fps: int,
    rng: random.Random | None = None,
) -> VideoFileClip:
    """Load a clip and trim or loop it to match target_duration.

    If the clip is longer than target, trim from a random start point.
    If shorter, loop it. All clips are resized to the target resolution.
    """
    clip = VideoFileClip(str(path))

    if clip.duration > target_duration:
        # Trim from a random start point
        if rng is None:
            rng = random.Random()
        max_start = clip.duration - target_duration
        start = rng.uniform(0, max_start)
        clip = clip.subclipped(start, start + target_duration)
    elif clip.duration < target_duration:
        # Loop the clip to fill target duration
        n_loops = int(target_duration / clip.duration) + 1
        clip = concatenate_videoclips([clip] * n_loops)
        clip = clip.subclipped(0, target_duration)

    clip = _resize_crop(clip, *resolution)
    clip = clip.with_fps(fps)
    return clip


def build_video(
    assignments: list[ClipAssignment],
    audio_path: Path | str,
    output_path: Path | str,
    preset: FormatPreset,
    seed: int | None = None,
    audio_start: float = 0.0,
    audio_end: float | None = None,
    effects: bool = False,
    effect_rate: float = 0.75,
    transitions: bool = False,
    transition_rate: float = 1.0,
    transition_duration: float = 0.3,
    title_card_config: TitleCardConfig | None = None,
    info_overlay_config: InfoOverlayConfig | None = None,
    split_screen_config: SplitScreenConfig | None = None,
    climax_burst_config: ClimaxBurstConfig | None = None,
    generated_clips_config: GeneratedClipsConfig | None = None,
    fast: bool = False,
) -> Path:
    """Build the final beat-synced video from clip assignments.

    Prepares each clip, concatenates them, overlays the audio, and exports.
    When audio_start/audio_end are set, trims the audio to that range.
    Optionally applies random visual effects and transitions between clips.
    """
    rng = random.Random(seed)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if generated_clips_config is not None:
        assignments = inject_generated_clips(
            assignments, generated_clips_config, preset.resolution, rng
        )

    prepared = []
    for assignment in assignments:
        if assignment.generator is not None:
            clip = VideoClip(assignment.generator, duration=assignment.target_duration)
            clip = clip.with_fps(preset.fps)
        else:
            clip = prepare_clip(
                assignment.path,
                assignment.target_duration,
                preset.resolution,
                preset.fps,
                rng,
            )
        if effects:
            clip = apply_random_effect(clip, rng, effect_rate)
        prepared.append(clip)

    if split_screen_config is not None and len(prepared) > 1:
        prepared = inject_split_screens(
            prepared, split_screen_config, preset.resolution, preset.fps, rng
        )

    if climax_burst_config is not None and len(prepared) >= len(CLIMAX_PANEL_SEQUENCE):
        prepared = inject_climax_burst(
            prepared, climax_burst_config, preset.resolution, preset.fps, rng
        )

    if transitions and len(prepared) > 1:
        transition_specs = [
            select_transition(
                rng,
                transition_rate,
                transition_duration,
                prepared[i].duration,
                prepared[i + 1].duration,
            )
            for i in range(len(prepared) - 1)
        ]
        final = compose_with_transitions(prepared, transition_specs)
    else:
        final = concatenate_videoclips(prepared, method="compose")

    # Prepend title card if configured
    if title_card_config is not None:
        title_clip = create_title_card(
            title_card_config, preset.resolution, preset.fps
        )
        final = concatenate_videoclips([title_clip, final], method="compose")

    # Composite info overlay if configured
    if info_overlay_config is not None:
        overlay = create_info_overlay(
            info_overlay_config, preset.resolution, preset.fps
        )
        # Ensure overlay doesn't exceed video duration
        overlay_end = info_overlay_config.delay + info_overlay_config.display_duration
        if overlay_end <= final.duration:
            final = CompositeVideoClip([final, overlay])
        else:
            # Truncate overlay to fit within video
            remaining = final.duration - info_overlay_config.delay
            if remaining > 0:
                overlay = overlay.with_duration(remaining)
                final = CompositeVideoClip([final, overlay])

    audio = AudioFileClip(str(audio_path))
    # Trim audio to the specified range if set
    if audio_start > 0.0 or audio_end is not None:
        end = audio_end if audio_end is not None else audio.duration
        audio = audio.subclipped(audio_start, end)
    # Trim audio to match video length if needed
    if audio.duration > final.duration:
        audio = audio.subclipped(0, final.duration)
    final = final.with_audio(audio)

    # Build ffmpeg params from preset
    ffmpeg_params: list[str] = []
    if fast:
        ffmpeg_params.extend(["-preset", "ultrafast", "-threads", "0"])
    if preset.bitrate:
        ffmpeg_params.extend(["-b:v", preset.bitrate])

    write_kwargs: dict[str, object] = {
        "codec": preset.codec,
        "audio_codec": preset.audio_codec,
        "fps": preset.fps,
        "logger": "bar",
    }
    if preset.audio_bitrate:
        write_kwargs["audio_bitrate"] = preset.audio_bitrate
    if ffmpeg_params:
        write_kwargs["ffmpeg_params"] = ffmpeg_params

    final.write_videofile(str(output_path), **write_kwargs)  # type: ignore[arg-type]

    # Clean up
    for clip in prepared:
        clip.close()
    final.close()
    audio.close()

    return output_path
