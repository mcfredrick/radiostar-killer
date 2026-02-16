"""Command-line interface for radiostar-killer."""

import argparse
import sys
from pathlib import Path

from radiostar_killer.formats import PRESETS, resolve_format
from radiostar_killer.main import run


def parse_resolution(value: str) -> tuple[int, int]:
    """Parse a resolution string like '1920x1080'."""
    try:
        w, h = value.lower().split("x")
        return int(w), int(h)
    except (ValueError, AttributeError):
        raise argparse.ArgumentTypeError(
            f"Invalid resolution '{value}'. Use format WIDTHxHEIGHT (e.g. 1920x1080)"
        )


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

    args = parser.parse_args()

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
        )
        if isinstance(result, list):
            for p in result:
                print(f"  {p}")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
