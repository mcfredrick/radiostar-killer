"""Video clip preparation, concatenation, and export."""

import random
from pathlib import Path

from moviepy import (
    AudioFileClip,
    VideoFileClip,
    concatenate_videoclips,
)

from radiostar_killer.clips import ClipAssignment
from radiostar_killer.formats import FormatPreset


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

    clip = clip.resized(resolution)
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
) -> Path:
    """Build the final beat-synced video from clip assignments.

    Prepares each clip, concatenates them, overlays the audio, and exports.
    When audio_start/audio_end are set, trims the audio to that range.
    """
    rng = random.Random(seed)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    prepared = []
    for assignment in assignments:
        clip = prepare_clip(
            assignment.path,
            assignment.target_duration,
            preset.resolution,
            preset.fps,
            rng,
        )
        prepared.append(clip)

    final = concatenate_videoclips(prepared, method="compose")

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
