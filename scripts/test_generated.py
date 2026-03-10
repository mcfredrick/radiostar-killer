#!/usr/bin/env python3
"""Preview an algorithmically generated visualizer style with a click track.

The click track produces an 880 Hz sine burst on every beat so you can verify
that the visual animation aligns with the tempo.

Usage:
    uv run scripts/test_generated.py --style plasma --tempo 120
    uv run scripts/test_generated.py --style radial_pulse --tempo 90 --duration 8
    uv run scripts/test_generated.py --style spectrum_bars --tempo 140 --output bars.mp4
    uv run scripts/test_generated.py --list
"""

import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from radiostar_killer.generated import STYLES, make_generated_clip

SAMPLE_RATE = 44100
DEFAULT_TEMPO = 120.0
DEFAULT_DURATION = 8.0
DEFAULT_RESOLUTION = (1280, 720)
DEFAULT_FPS = 30


def _make_click_track(duration: float, tempo: float) -> np.ndarray:
    """Generate a mono float32 click track with a 880 Hz sine burst on each beat.

    Beat times match np.arange(0, duration, 60/tempo) — identical to what the
    visualizer generators receive — so visual flashes and audio clicks coincide.
    """
    beat_interval = 60.0 / tempo
    n_samples = int(duration * SAMPLE_RATE)
    audio = np.zeros(n_samples, dtype=np.float32)

    t_beat = 0.0
    while t_beat < duration:
        s = int(t_beat * SAMPLE_RATE)
        click_dur = 0.015  # 15 ms
        n = int(click_dur * SAMPLE_RATE)
        t_arr = np.linspace(0, click_dur, n, dtype=np.float32)
        # Exponentially-decayed sine: sharp attack, quick fade
        click = np.sin(2 * np.pi * 880 * t_arr) * np.exp(-t_arr * 200)
        end = min(s + n, n_samples)
        audio[s:end] += click[: end - s]
        t_beat += beat_interval

    return np.clip(audio, -1.0, 1.0)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preview a generated visualizer style with a beat-aligned click track.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--style", help="Visualizer style name")
    parser.add_argument(
        "--tempo", type=float, default=DEFAULT_TEMPO,
        help=f"BPM (default: {DEFAULT_TEMPO})",
    )
    parser.add_argument(
        "--duration", type=float, default=DEFAULT_DURATION,
        help=f"Clip length in seconds (default: {DEFAULT_DURATION})",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("test_generated_output.mp4"),
    )
    parser.add_argument(
        "--resolution", default="1280x720",
        help="Output resolution as WIDTHxHEIGHT (default: 1280x720)",
    )
    parser.add_argument(
        "--fps", type=int, default=DEFAULT_FPS,
        help=f"Frames per second (default: {DEFAULT_FPS})",
    )
    parser.add_argument(
        "--no-click", action="store_true",
        help="Omit the click track (silent output for visual inspection only)",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List available visualizer styles and exit",
    )
    args = parser.parse_args()

    if args.list:
        print("Available styles:")
        for name in STYLES:
            print(f"  {name}")
        return

    if not args.style:
        parser.error("--style is required (or use --list)")
    if args.style not in STYLES:
        print(f"Unknown style '{args.style}'. Available: {STYLES}", file=sys.stderr)
        sys.exit(1)

    w, h = (int(x) for x in args.resolution.lower().split("x"))
    resolution = (w, h)

    beat_interval = 60.0 / args.tempo
    beat_times = np.arange(0, args.duration, beat_interval)

    print(
        f"Generating '{args.style}' ({args.duration}s, {args.tempo} BPM, "
        f"{len(beat_times)} beats) ..."
    )
    clip = make_generated_clip(
        style=args.style,
        duration=args.duration,
        resolution=resolution,
        fps=args.fps,
        tempo=args.tempo,
        beat_times=beat_times,
    )

    wav_path: Path | None = None
    if not args.no_click:
        from moviepy import AudioFileClip

        click_audio = _make_click_track(args.duration, args.tempo)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = Path(f.name)
        wavfile.write(str(wav_path), SAMPLE_RATE, click_audio)
        audio = AudioFileClip(str(wav_path))
        clip = clip.with_audio(audio)
        print(f"  Click track: {len(beat_times)} beats at {args.tempo} BPM")

    print(f"Writing {args.output} ...")
    write_kwargs: dict[str, object] = {
        "fps": args.fps,
        "codec": "libx264",
        "logger": None,
    }
    if args.no_click:
        write_kwargs["audio"] = False
    else:
        write_kwargs["audio_codec"] = "aac"

    clip.write_videofile(str(args.output), **write_kwargs)  # type: ignore[arg-type]

    if wav_path is not None:
        wav_path.unlink(missing_ok=True)

    print(f"Done: {args.output}")


if __name__ == "__main__":
    main()
