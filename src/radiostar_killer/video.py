"""Video clip preparation, concatenation, and export."""

import random
from pathlib import Path

from moviepy import (
    AudioFileClip,
    VideoFileClip,
    concatenate_videoclips,
)

from radiostar_killer.clips import ClipAssignment


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
    resolution: tuple[int, int],
    fps: int,
    seed: int | None = None,
) -> Path:
    """Build the final beat-synced video from clip assignments.

    Prepares each clip, concatenates them, overlays the audio, and exports.
    """
    rng = random.Random(seed)
    output_path = Path(output_path)

    prepared = []
    for assignment in assignments:
        clip = prepare_clip(
            assignment.path,
            assignment.target_duration,
            resolution,
            fps,
            rng,
        )
        prepared.append(clip)

    final = concatenate_videoclips(prepared, method="compose")

    audio = AudioFileClip(str(audio_path))
    # Trim audio to match video length if needed
    if audio.duration > final.duration:
        audio = audio.subclipped(0, final.duration)
    final = final.with_audio(audio)

    final.write_videofile(
        str(output_path),
        codec="libx264",
        audio_codec="aac",
        fps=fps,
        logger="bar",
    )

    # Clean up
    for clip in prepared:
        clip.close()
    final.close()
    audio.close()

    return output_path
