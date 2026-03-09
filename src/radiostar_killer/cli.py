"""Command-line interface for radiostar-killer."""

import argparse
import random
import sys
from pathlib import Path

from radiostar_killer.formats import PRESETS, resolve_format
from radiostar_killer.main import run

# Defaults for numeric visual params (defined here so _apply_defaults and
# argparse help strings stay in sync)
_EFFECT_RATE_DEFAULT = 0.75
_TRANSITION_RATE_DEFAULT = 1.0
_TRANSITION_DURATION_DEFAULT = 0.3
_SPLIT_SCREEN_COUNT_DEFAULT = 2


def parse_resolution(value: str) -> tuple[int, int]:
    """Parse a resolution string like '1920x1080'."""
    try:
        w, h = value.lower().split("x")
        return int(w), int(h)
    except (ValueError, AttributeError):
        raise argparse.ArgumentTypeError(
            f"Invalid resolution '{value}'. Use format WIDTHxHEIGHT (e.g. 1920x1080)"
        )


def _apply_randomize(args: argparse.Namespace) -> None:
    """Randomly enable visual flags that weren't explicitly set.

    Boolean flags are randomized if not already enabled. Numeric params are
    randomized if they were not explicitly passed (i.e. still None).
    """
    rng = random.Random()  # fully random — no seed, output is always printed

    if not args.effects:
        args.effects = rng.random() < 0.8
    if not args.transitions:
        args.transitions = rng.random() < 0.7
    if not args.split_screen:
        args.split_screen = rng.random() < 0.6
    if not args.climax_burst:
        args.climax_burst = rng.random() < 0.7

    if args.effect_rate is None:
        args.effect_rate = round(rng.uniform(0.3, 1.0), 2) if args.effects else _EFFECT_RATE_DEFAULT
    if args.transition_rate is None:
        args.transition_rate = round(rng.uniform(0.4, 1.0), 2) if args.transitions else _TRANSITION_RATE_DEFAULT
    if args.transition_duration is None:
        args.transition_duration = round(rng.uniform(0.2, 0.5), 2) if args.transitions else _TRANSITION_DURATION_DEFAULT
    if args.split_screen_count is None:
        args.split_screen_count = rng.randint(1, 3) if args.split_screen else _SPLIT_SCREEN_COUNT_DEFAULT
    # 33% chance of fixing panel count per occurrence rather than randomizing per split
    if args.split_screen and args.split_screen_panels is None and rng.random() < 0.33:
        args.split_screen_panels = rng.choice([2, 4, 6])


def _apply_defaults(args: argparse.Namespace) -> None:
    """Fill in None numeric visual params with their defaults.

    Runs after _apply_randomize (or instead of it) to ensure no None values
    reach run().
    """
    if args.effect_rate is None:
        args.effect_rate = _EFFECT_RATE_DEFAULT
    if args.transition_rate is None:
        args.transition_rate = _TRANSITION_RATE_DEFAULT
    if args.transition_duration is None:
        args.transition_duration = _TRANSITION_DURATION_DEFAULT
    if args.split_screen_count is None:
        args.split_screen_count = _SPLIT_SCREEN_COUNT_DEFAULT


def _build_reproduce_command(args: argparse.Namespace) -> str:
    """Build a fully-specified CLI command that reproduces the current run."""
    parts = ["radiostar-killer", str(args.clips_dir), str(args.audio_file)]

    parts += ["-o", str(args.output)]

    if args.format_name:
        parts += ["--format", args.format_name]
    if args.resolution:
        parts += ["--resolution", f"{args.resolution[0]}x{args.resolution[1]}"]
    if args.fps:
        parts += ["--fps", str(args.fps)]
    if args.min_beats != 2:
        parts += ["--min-beats", str(args.min_beats)]
    if args.seed is not None:
        parts += ["--seed", str(args.seed)]
    if args.shorts:
        parts += ["--shorts"]
        if args.short_duration != 60.0:
            parts += ["--short-duration", str(args.short_duration)]

    if args.effects:
        parts += ["--effects", "--effect-rate", str(args.effect_rate)]
    if args.transitions:
        parts += [
            "--transitions",
            "--transition-rate", str(args.transition_rate),
            "--transition-duration", str(args.transition_duration),
        ]
    if args.split_screen:
        parts += ["--split-screen", "--split-screen-count", str(args.split_screen_count)]
        if args.split_screen_panels is not None:
            parts += ["--split-screen-panels", str(args.split_screen_panels)]
    if args.climax_burst:
        parts += ["--climax-burst"]

    if args.title:
        parts += ["--title", f'"{args.title}"']
    if args.artist:
        parts += ["--artist", f'"{args.artist}"']
    if args.album:
        parts += ["--album", f'"{args.album}"']
    if args.title_card:
        parts += ["--title-card"]
        if args.title_card_duration != 3.5:
            parts += ["--title-card-duration", str(args.title_card_duration)]
    if args.info_overlay:
        parts += ["--info-overlay"]
        if args.info_overlay_duration != 8.0:
            parts += ["--info-overlay-duration", str(args.info_overlay_duration)]

    return " ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="radiostar-killer",
        description="Generate music videos by syncing video clips to audio beats.",
    )
    parser.add_argument(
        "clips_dir",
        type=Path,
        help="Directory containing video clips (.mp4, .mov, .avi)",
    )
    parser.add_argument(
        "audio_file",
        type=Path,
        help="Audio file to analyze for beats",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output.mp4"),
        help="Output video file path (default: output.mp4)",
    )
    parser.add_argument(
        "--min-beats",
        type=int,
        default=2,
        help="Minimum beats per group (default: 2)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible output",
    )
    parser.add_argument(
        "--resolution",
        type=parse_resolution,
        default=None,
        help="Output resolution as WIDTHxHEIGHT (overrides format preset)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=None,
        help="Output frames per second (overrides format preset)",
    )
    parser.add_argument(
        "--format",
        choices=sorted(PRESETS),
        default=None,
        dest="format_name",
        help="Output format preset (default: youtube)",
    )
    parser.add_argument(
        "--shorts",
        action="store_true",
        help="Generate 3 YouTube Shorts from the most energetic sections",
    )
    parser.add_argument(
        "--short-duration",
        type=float,
        default=60.0,
        help="Duration in seconds for each short (default: 60)",
    )
    parser.add_argument(
        "--randomize",
        action="store_true",
        help=(
            "Randomly enable visual flags (effects, transitions, split screen, climax burst). "
            "Explicit flags take priority; only unset flags are randomized. "
            "Prints a reproduce command before processing."
        ),
    )
    parser.add_argument(
        "--effects",
        action="store_true",
        help="Apply random visual effects to clips",
    )
    parser.add_argument(
        "--effect-rate",
        type=float,
        default=None,
        help=f"Proportion of clips to apply effects to (0.0–1.0, default: {_EFFECT_RATE_DEFAULT})",
    )
    parser.add_argument(
        "--transitions",
        action="store_true",
        help="Apply transition effects between clips",
    )
    parser.add_argument(
        "--transition-rate",
        type=float,
        default=None,
        help=f"Proportion of boundaries with transitions (0.0–1.0, default: {_TRANSITION_RATE_DEFAULT})",
    )
    parser.add_argument(
        "--transition-duration",
        type=float,
        default=None,
        help=f"Transition overlap in seconds (default: {_TRANSITION_DURATION_DEFAULT})",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="Song title (required for --title-card and --info-overlay)",
    )
    parser.add_argument(
        "--artist",
        type=str,
        default=None,
        help="Artist name (required for --info-overlay)",
    )
    parser.add_argument(
        "--album",
        type=str,
        default=None,
        help="Album name (optional, for info overlay)",
    )
    parser.add_argument(
        "--title-card",
        action="store_true",
        help="Enable opening title card",
    )
    parser.add_argument(
        "--title-card-duration",
        type=float,
        default=3.5,
        help="Title card duration in seconds before beat-snapping (default: 3.5)",
    )
    parser.add_argument(
        "--info-overlay",
        action="store_true",
        help="Enable MTV/VH1-style song info overlay",
    )
    parser.add_argument(
        "--info-overlay-duration",
        type=float,
        default=8.0,
        help="Info overlay display duration in seconds (default: 8.0)",
    )
    parser.add_argument(
        "--climax-burst",
        action="store_true",
        help=(
            "Inject a 2→4→6→4→2 split screen burst at the song's peak energy moment"
        ),
    )
    parser.add_argument(
        "--split-screen",
        action="store_true",
        help="Inject split screen moments showing 2, 4, or 6 clips simultaneously",
    )
    parser.add_argument(
        "--split-screen-count",
        type=int,
        default=None,
        help=f"Number of split screen occurrences to inject (default: {_SPLIT_SCREEN_COUNT_DEFAULT}, max recommended: 3)",
    )
    parser.add_argument(
        "--split-screen-panels",
        type=int,
        choices=[2, 4, 6],
        default=None,
        help="Fixed panel count per split screen (2, 4, or 6; default: random per occurrence)",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use ultrafast encoding preset and max threads for faster export",
    )

    args = parser.parse_args()

    # Validate overlay flags
    if args.title_card and not args.title:
        parser.error("--title-card requires --title")
    if args.info_overlay:
        if not args.title:
            parser.error("--info-overlay requires --title")
        if not args.artist:
            parser.error("--info-overlay requires --artist")

    if args.randomize:
        _apply_randomize(args)

    _apply_defaults(args)

    if args.randomize:
        enabled = [
            flag for flag, on in [
                ("--effects", args.effects),
                ("--transitions", args.transitions),
                ("--split-screen", args.split_screen),
                ("--climax-burst", args.climax_burst),
            ] if on
        ]
        print(f"[randomize] Enabled: {', '.join(enabled) if enabled else '(none)'}")
        print(f"[randomize] Reproduce with:")
        print(f"  {_build_reproduce_command(args)}")

    # Default to youtube-shorts format when --shorts is used without --format
    format_name = args.format_name
    if args.shorts and format_name is None:
        format_name = "youtube-shorts"

    try:
        preset = resolve_format(format_name, args.resolution, args.fps)
        result = run(
            clips_dir=args.clips_dir,
            audio_file=args.audio_file,
            output=args.output,
            min_beats=args.min_beats,
            seed=args.seed,
            preset=preset,
            shorts=args.shorts,
            short_duration=args.short_duration,
            effects=args.effects,
            effect_rate=args.effect_rate,
            transitions=args.transitions,
            transition_rate=args.transition_rate,
            transition_duration=args.transition_duration,
            title=args.title,
            artist=args.artist,
            album=args.album,
            title_card=args.title_card,
            title_card_duration=args.title_card_duration,
            info_overlay=args.info_overlay,
            info_overlay_duration=args.info_overlay_duration,
            split_screen=args.split_screen,
            split_screen_count=args.split_screen_count,
            split_screen_panels=args.split_screen_panels,
            climax_burst=args.climax_burst,
            fast=args.fast,
        )
        if isinstance(result, list):
            for p in result:
                print(f"  {p}")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
