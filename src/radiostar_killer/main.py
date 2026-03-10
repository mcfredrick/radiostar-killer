"""Orchestrator pipeline for radiostar-killer."""

from pathlib import Path

import numpy as np

from radiostar_killer.audio import analyze_audio, analyze_energy, find_peak_energy_time, group_beats
from radiostar_killer.clips import assign_clips_to_groups, discover_clips
from radiostar_killer.formats import PRESETS, FormatPreset
from radiostar_killer.generated import GeneratedClipsConfig
from radiostar_killer.overlays import (
    InfoOverlayConfig,
    TitleCardConfig,
    snap_to_nearest_beat,
)
from radiostar_killer.splitscreen import ClimaxBurstConfig, SplitScreenConfig
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
    title: str | None = None,
    artist: str | None = None,
    album: str | None = None,
    title_card: bool = False,
    title_card_duration: float = 3.5,
    info_overlay: bool = False,
    info_overlay_duration: float = 8.0,
    split_screen: bool = False,
    split_screen_count: int = 2,
    split_screen_panels: int | None = None,
    climax_burst: bool = False,
    generated_clips: bool = False,
    generated_rate: float = 0.3,
    generated_style: str = "random",
    fast: bool = False,
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

    if fast:
        print("  Fast encoding enabled (ultrafast preset, max threads)")
    if effects:
        print(f"  Effects enabled (rate: {effect_rate:.0%})")
    if transitions:
        print(f"  Transitions enabled (rate: {transition_rate:.0%}, "
              f"duration: {transition_duration}s)")

    # Build overlay configs
    title_card_config = None
    if title_card and title:
        snapped = snap_to_nearest_beat(title_card_duration, audio_info.beat_times)
        print(f"  Title card: {snapped:.2f}s (snapped from {title_card_duration:.2f}s)")
        title_card_config = TitleCardConfig(
            title=title,
            subtitle=artist,
            duration=snapped,
        )

    info_overlay_config = None
    if info_overlay and title and artist:
        print(f"  Info overlay: {info_overlay_duration:.1f}s")
        info_overlay_config = InfoOverlayConfig(
            title=title,
            artist=artist,
            album=album,
            display_duration=info_overlay_duration,
        )

    split_screen_config = None
    if split_screen:
        split_screen_config = SplitScreenConfig(
            count=split_screen_count,
            panels=split_screen_panels,
        )
        panels_label = str(split_screen_panels) if split_screen_panels else "random"
        print(f"  Split screen: up to {split_screen_count} occurrences, panels={panels_label}")

    # Climax burst is built per-path below (needs beat_groups), so just flag it here
    if climax_burst:
        print("  Climax burst: enabled (2→4→6→4→2 panels at peak energy)")

    generated_clips_config = None
    if generated_clips:
        generated_clips_config = GeneratedClipsConfig(
            rate=generated_rate,
            style=generated_style,
            tempo=audio_info.tempo,
            beat_times=audio_info.beat_times,
        )
        print(f"  Generated clips: enabled (rate: {generated_rate:.0%}, style: {generated_style})")

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
            title_card_config=title_card_config,
            info_overlay_config=info_overlay_config,
            split_screen_config=split_screen_config,
            climax_burst=climax_burst,
            generated_clips_config=generated_clips_config,
            fast=fast,
        )

    beat_groups = group_beats(audio_info.beat_times, audio_info.duration, min_beats)
    print(f"  Beat groups: {len(beat_groups)}")

    assignments = assign_clips_to_groups(clip_paths, beat_groups, seed)

    climax_burst_config = None
    if climax_burst:
        peak_time = find_peak_energy_time(audio_file)
        print(f"  Climax burst peak: {peak_time:.2f}s")
        climax_burst_config = ClimaxBurstConfig(
            climax_time=peak_time,
            tempo=audio_info.tempo,
            beat_groups=beat_groups,
        )

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
        title_card_config=title_card_config,
        info_overlay_config=info_overlay_config,
        split_screen_config=split_screen_config,
        climax_burst_config=climax_burst_config,
        generated_clips_config=generated_clips_config,
        fast=fast,
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
    title_card_config: TitleCardConfig | None = None,
    info_overlay_config: InfoOverlayConfig | None = None,
    split_screen_config: SplitScreenConfig | None = None,
    climax_burst: bool = False,
    generated_clips_config: GeneratedClipsConfig | None = None,
    fast: bool = False,
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

        section_climax_config = None
        if climax_burst:
            # Use the section midpoint as the climax time within each short
            section_mid = section.start + (section.end - section.start) / 2
            section_climax_config = ClimaxBurstConfig(
                climax_time=section_mid - section.start,  # relative to section
                tempo=audio_info.tempo,
                beat_groups=beat_groups,
            )

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
            title_card_config=title_card_config,
            info_overlay_config=info_overlay_config,
            split_screen_config=split_screen_config,
            climax_burst_config=section_climax_config,
            generated_clips_config=generated_clips_config,
            fast=fast,
        )
        output_paths.append(short_output)

    print(f"\nDone! Generated {len(output_paths)} shorts")
    return output_paths
