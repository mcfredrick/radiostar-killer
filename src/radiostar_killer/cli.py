"""Command-line interface for radiostar-killer."""

import argparse
import sys
from pathlib import Path

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
        default=(1920, 1080),
        help="Output resolution as WIDTHxHEIGHT (default: 1920x1080)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="Output frames per second (default: 30)",
    )

    args = parser.parse_args()

    try:
        run(
            clips_dir=args.clips_dir,
            audio_file=args.audio_file,
            output=args.output,
            min_beats=args.min_beats,
            seed=args.seed,
            resolution=args.resolution,
            fps=args.fps,
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
