"""Beat analysis, beat-group partitioning, and energy analysis."""

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


@dataclass
class EnergySection:
    start: float
    end: float
    mean_energy: float


def analyze_energy(
    path: Path | str,
    window_duration: float = 60.0,
    num_sections: int = 3,
) -> list[EnergySection]:
    """Find the most energetic non-overlapping sections of an audio file.

    Uses librosa RMS energy with a sliding window approach.
    Returns up to num_sections sections sorted by start time.
    """
    path = Path(path)
    y, sr = librosa.load(str(path), sr=None)
    duration = librosa.get_duration(y=y, sr=sr)

    # Clamp window to full duration if audio is shorter
    window = min(window_duration, duration)
    if window < 15.0:
        window = min(15.0, duration)

    # Compute RMS energy per frame
    rms = librosa.feature.rms(y=y)[0]
    frame_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)

    # Compute mean energy for each 1-second step position
    candidates: list[tuple[float, float, float]] = []
    step = 1.0
    pos = 0.0
    while pos + window <= duration + 0.01:
        end = min(pos + window, duration)
        mask = (frame_times >= pos) & (frame_times < end)
        if np.any(mask):
            mean_e = float(np.mean(rms[mask]))
            candidates.append((pos, end, mean_e))
        pos += step

    # If no candidates (very short audio), use the whole thing
    if not candidates:
        mean_e = float(np.mean(rms)) if len(rms) > 0 else 0.0
        return [EnergySection(start=0.0, end=duration, mean_energy=mean_e)]

    # Sort by energy descending and greedily pick non-overlapping
    candidates.sort(key=lambda c: c[2], reverse=True)
    selected: list[EnergySection] = []
    for start, end, energy in candidates:
        if len(selected) >= num_sections:
            break
        # Check for overlap with already-selected sections
        overlaps = any(
            not (end <= s.start or start >= s.end) for s in selected
        )
        if not overlaps:
            selected.append(EnergySection(start=start, end=end, mean_energy=energy))

    # Sort by start time
    selected.sort(key=lambda s: s.start)
    return selected
