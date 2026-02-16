"""Beat analysis and beat-group partitioning."""

from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
from numpy.typing import NDArray


@dataclass
class AudioInfo:
    tempo: float
    beat_times: NDArray[np.floating]
    duration: float
    sample_rate: int


def analyze_audio(path: Path | str) -> AudioInfo:
    """Load an audio file and return beat analysis."""
    path = Path(path)
    y, sr = librosa.load(str(path), sr=None)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    duration = librosa.get_duration(y=y, sr=sr)
    return AudioInfo(
        tempo=float(tempo),
        beat_times=beat_times,
        duration=float(duration),
        sample_rate=int(sr),
    )


def group_beats(
    beat_times: NDArray[np.floating],
    duration: float,
    min_beats: int = 2,
) -> list[tuple[float, float]]:
    """Partition beat timestamps into groups of 4.

    Each group becomes a (start_time, end_time) tuple.
    Remainder beats fewer than min_beats are merged into the previous group.
    If there are fewer total beats than min_beats, one group spans the whole duration.
    """
    n = len(beat_times)
    if n == 0:
        return [(0.0, duration)]

    group_size = 4
    groups: list[tuple[float, float]] = []
    i = 0

    while i < n:
        remaining = n - i
        if remaining < group_size:
            if remaining < min_beats and groups:
                # Merge remainder into previous group
                prev_start, _ = groups.pop()
                end = duration
                groups.append((prev_start, end))
            else:
                # Standalone group for remainder
                start = float(beat_times[i])
                end = duration
                groups.append((start, end))
            break
        else:
            start = float(beat_times[i])
            if i + group_size < n:
                end = float(beat_times[i + group_size])
            else:
                end = duration
            groups.append((start, end))
            i += group_size

    return groups
