"""Clip discovery and beat-group assignment."""

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from moviepy import VideoFileClip

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".avi"}


@dataclass
class ClipAssignment:
    path: Path
    target_duration: float
    original_duration: float
    # When set, this clip is rendered algorithmically instead of loaded from path.
    generator: Callable[[float], np.ndarray] | None = field(default=None, repr=False)


def discover_clips(directory: Path | str) -> list[Path]:
    """Scan a directory for supported video files.

    Returns sorted list of paths. Raises FileNotFoundError if directory
    doesn't exist, ValueError if no clips found.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"Clips directory not found: {directory}")

    clips = sorted(
        p
        for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not clips:
        raise ValueError(f"No video clips found in {directory}")
    return clips


def assign_clips_to_groups(
    paths: list[Path],
    beat_groups: list[tuple[float, float]],
    seed: int | None = None,
) -> list[ClipAssignment]:
    """Assign clips to beat groups via shuffled round-robin.

    Reads original durations from each clip file. If there are fewer clips
    than groups, clips are recycled.
    """
    rng = random.Random(seed)
    shuffled = list(paths)
    rng.shuffle(shuffled)

    # Cache original durations
    durations: dict[Path, float] = {}
    for p in paths:
        clip = VideoFileClip(str(p))
        durations[p] = clip.duration
        clip.close()

    assignments = []
    for i, (start, end) in enumerate(beat_groups):
        clip_path = shuffled[i % len(shuffled)]
        target_dur = end - start
        assignments.append(
            ClipAssignment(
                path=clip_path,
                target_duration=target_dur,
                original_duration=durations[clip_path],
            )
        )
    return assignments
