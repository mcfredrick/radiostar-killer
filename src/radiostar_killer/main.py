"""Orchestrator pipeline for radiostar-killer."""

from pathlib import Path

import numpy as np

from radiostar_killer.audio import analyze_audio, analyze_energy, group_beats
from radiostar_killer.clips import assign_clips_to_groups, discover_clips
from radiostar_killer.formats import PRESETS, FormatPreset
from radiostar_killer.video import build_video


def run(
    clips_dir: Path,
    audio_file: Path,
    output: Path,
    min_beats: int = 2,
    seed: int | None = None,
    preset: FormatPreset = PRESETS["youtube"],
    shorts: bool = False,
    short_duration: float = 60.0,
    effects: bool = False,
    effect_rate: float = 0.75,
    transitions: bool = False,
    transition_rate: float = 1.0,
    transition_duration: float = 0.3,
) -> Path | list[Path]:
    """Run the full music video generation pipeline.

    When shorts=True, generates up to 3 short videos from the most
    energetic sections instead of a full-length video.
    """
    print(f"Analyzing audio: {audio_file}")
    audio_info = analyze_audio(audio_file)
    print(f"  Tempo: {audio_info.tempo:.1f} BPM")
    print(f"  Duration: {audio_info.duration:.1f}s")
    print(f"  Beats detected: {len(audio_info.beat_times)}")

    print(f"Discovering clips in: {clips_dir}")
    clip_paths = discover_clips(clips_dir)
    print(f"  Found {len(clip_paths)} clips")

    if effects:
        print(f"  Effects enabled (rate: {effect_rate:.0%})")
    if transitions:
        print(f"  Transitions enabled (rate: {transition_rate:.0%}, "
              f"duration: {transition_duration}s)")

    if shorts:
        return _build_shorts(
            clips_dir=clips_dir,
            audio_file=audio_file,
            output=output,
            audio_info=audio_info,
            clip_paths=clip_paths,
            min_beats=min_beats,
            seed=seed,
            short_duration=short_duration,
            effects=effects,
            effect_rate=effect_rate,
            transitions=transitions,
            transition_rate=transition_rate,
            transition_duration=transition_duration,
        )

    beat_groups = group_beats(audio_info.beat_times, audio_info.duration, min_beats)
    print(f"  Beat groups: {len(beat_groups)}")

    assignments = assign_clips_to_groups(clip_paths, beat_groups, seed)

    print(f"Building video: {output}")
    res = preset.resolution
    print(f"  Format: {preset.name}, Resolution: {res[0]}x{res[1]}, FPS: {preset.fps}")
    result = build_video(
        assignments,
        audio_file,
        output,
        preset,
        seed,
        effects=effects,
        effect_rate=effect_rate,
        transitions=transitions,
        transition_rate=transition_rate,
        transition_duration=transition_duration,
    )

    print(f"Done! Output: {result}")
    return result


def _build_shorts(
    clips_dir: Path,
    audio_file: Path,
    output: Path,
    audio_info: object,
    clip_paths: list[Path],
    min_beats: int,
    seed: int | None,
    short_duration: float,
    effects: bool = False,
    effect_rate: float = 0.75,
    transitions: bool = False,
    transition_rate: float = 1.0,
    transition_duration: float = 0.3,
) -> list[Path]:
    """Build YouTube Shorts from the most energetic sections."""
    from radiostar_killer.audio import AudioInfo

    assert isinstance(audio_info, AudioInfo)

    shorts_preset = PRESETS["youtube-shorts"]
    print(f"Analyzing energy for shorts (window={short_duration}s)...")
    sections = analyze_energy(
        audio_file, window_duration=short_duration, num_sections=3
    )
    print(f"  Found {len(sections)} energetic sections")

    output_paths: list[Path] = []
    stem = output.stem

    for i, section in enumerate(sections):
        print(f"\nBuilding short {i + 1}/{len(sections)}: "
              f"{section.start:.1f}s - {section.end:.1f}s "
              f"(energy: {section.mean_energy:.4f})")

        # Filter beats to this section's time range
        section_beats = audio_info.beat_times[
            (audio_info.beat_times >= section.start)
            & (audio_info.beat_times < section.end)
        ]

        section_duration = section.end - section.start

        # Make beat times relative to section start
        relative_beats = section_beats - section.start

        beat_groups = group_beats(
            np.array(relative_beats), section_duration, min_beats
        )
        print(f"  Beat groups: {len(beat_groups)}")

        assignments = assign_clips_to_groups(clip_paths, beat_groups, seed)

        short_output = output.parent / f"{stem}_short_{i + 1}.mp4"
        print(f"  Output: {short_output}")

        build_video(
            assignments,
            audio_file,
            short_output,
            shorts_preset,
            seed,
            audio_start=section.start,
            audio_end=section.end,
            effects=effects,
            effect_rate=effect_rate,
            transitions=transitions,
            transition_rate=transition_rate,
            transition_duration=transition_duration,
        )
        output_paths.append(short_output)

    print(f"\nDone! Generated {len(output_paths)} shorts")
    return output_paths
