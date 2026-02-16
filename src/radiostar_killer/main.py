"""Orchestrator pipeline for radiostar-killer."""

from pathlib import Path

from radiostar_killer.audio import analyze_audio, group_beats
from radiostar_killer.clips import assign_clips_to_groups, discover_clips
from radiostar_killer.video import build_video


def run(
    clips_dir: Path,
    audio_file: Path,
    output: Path,
    min_beats: int = 2,
    seed: int | None = None,
    resolution: tuple[int, int] = (1920, 1080),
    fps: int = 30,
) -> Path:
    """Run the full music video generation pipeline."""
    print(f"Analyzing audio: {audio_file}")
    audio_info = analyze_audio(audio_file)
    print(f"  Tempo: {audio_info.tempo:.1f} BPM")
    print(f"  Duration: {audio_info.duration:.1f}s")
    print(f"  Beats detected: {len(audio_info.beat_times)}")

    beat_groups = group_beats(audio_info.beat_times, audio_info.duration, min_beats)
    print(f"  Beat groups: {len(beat_groups)}")

    print(f"Discovering clips in: {clips_dir}")
    clip_paths = discover_clips(clips_dir)
    print(f"  Found {len(clip_paths)} clips")

    assignments = assign_clips_to_groups(clip_paths, beat_groups, seed)

    print(f"Building video: {output}")
    print(f"  Resolution: {resolution[0]}x{resolution[1]}, FPS: {fps}")
    result = build_video(assignments, audio_file, output, resolution, fps, seed)

    print(f"Done! Output: {result}")
    return result
