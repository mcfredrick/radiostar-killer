#!/usr/bin/env python3
"""Render demo clips for each visualizer style (or a selected subset).

Writes one MP4 per style to the output directory. Use --include-overlay to
also render each style composited over real video footage, and --reel to
concatenate everything into a single demo_all.mp4.

Usage:
    # Render all styles (standalone)
    uv run scripts/demo_visualizers.py

    # Render only the four new styles
    uv run scripts/demo_visualizers.py --new-only

    # Standalone + overlay variants (requires source clips)
    uv run scripts/demo_visualizers.py --clips /path/to/clips --include-overlay

    # Custom overlay opacity
    uv run scripts/demo_visualizers.py --clips /path/to/clips --include-overlay --overlay-alpha 0.8

    # Full demo reel at 90 BPM, 10s each
    uv run scripts/demo_visualizers.py --clips /path/to/clips --include-overlay --reel --tempo 90 --duration 10

    # Silent output (no click track)
    uv run scripts/demo_visualizers.py --no-click
"""

import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.io import wavfile

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from radiostar_killer.generated import STYLES, _FACTORIES, _make_overlay_clip, make_generated_clip

SAMPLE_RATE = 44100
DEFAULT_TEMPO = 120.0
DEFAULT_DURATION = 8.0
DEFAULT_RESOLUTION = (1280, 720)
DEFAULT_FPS = 30
DEFAULT_OVERLAY_ALPHA = 0.8
NEW_STYLES = ["waveform", "starfield", "tunnel", "grid_pulse"]


def _make_click_track(duration: float, tempo: float) -> np.ndarray:
    beat_interval = 60.0 / tempo
    n_samples = int(duration * SAMPLE_RATE)
    audio = np.zeros(n_samples, dtype=np.float32)
    t_beat = 0.0
    while t_beat < duration:
        s = int(t_beat * SAMPLE_RATE)
        n = int(0.015 * SAMPLE_RATE)
        t_arr = np.linspace(0, 0.015, n, dtype=np.float32)
        click = np.sin(2 * np.pi * 880 * t_arr) * np.exp(-t_arr * 200)
        end = min(s + n, n_samples)
        audio[s:end] += click[: end - s]
        t_beat += beat_interval
    return np.clip(audio, -1.0, 1.0)


def _load_clips(clips_dir: Path) -> list[Path]:
    exts = {".mp4", ".mov", ".avi"}
    clips = sorted(p for p in clips_dir.iterdir() if p.suffix.lower() in exts)
    if not clips:
        print(f"No video clips found in {clips_dir}", file=sys.stderr)
        sys.exit(1)
    return clips


def _resize_crop(clip, w: int, h: int):
    src_w, src_h = clip.size
    scale = max(w / src_w, h / src_h)
    clip = clip.resized(scale)
    cw, ch = clip.size
    return clip.cropped(
        x1=cw / 2 - w / 2, y1=ch / 2 - h / 2,
        x2=cw / 2 + w / 2, y2=ch / 2 + h / 2,
    )


def _prepare_base(path: Path, duration: float, resolution: tuple[int, int], fps: int):
    from moviepy import VideoFileClip, concatenate_videoclips as cv
    clip = VideoFileClip(str(path))
    clip = _resize_crop(clip, *resolution)
    if clip.duration < duration:
        n = int(duration / clip.duration) + 1
        clip = cv([clip] * n).subclipped(0, duration)
    else:
        clip = clip.subclipped(0, duration)
    return clip.with_fps(fps)


def _attach_click(clip, duration: float, tempo: float):
    from moviepy import AudioFileClip
    click_audio = _make_click_track(duration, tempo)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = Path(f.name)
    wavfile.write(str(wav_path), SAMPLE_RATE, click_audio)
    audio = AudioFileClip(str(wav_path))
    return clip.with_audio(audio), wav_path


def _render_style(
    style: str,
    duration: float,
    resolution: tuple[int, int],
    fps: int,
    tempo: float,
    overlay_alpha: float | None,
    base_clip_path: Path | None,
    with_click: bool,
    output_path: Path,
) -> None:
    from moviepy import CompositeVideoClip

    beat_interval = 60.0 / tempo
    beat_times = np.arange(0.0, duration, beat_interval)
    W, H = resolution

    if overlay_alpha is not None and base_clip_path is not None:
        base = _prepare_base(base_clip_path, duration, resolution, fps)
        frame_fn = _FACTORIES[style](W, H, tempo, beat_times, energy=0.8)
        overlay = _make_overlay_clip(frame_fn, duration, fps, overlay_alpha)
        clip = CompositeVideoClip([base, overlay], size=resolution)
    else:
        clip = make_generated_clip(
            style=style, duration=duration, resolution=resolution,
            fps=fps, tempo=tempo, beat_times=beat_times,
        )

    wav_path: Path | None = None
    if with_click:
        clip, wav_path = _attach_click(clip, duration, tempo)

    write_kwargs: dict[str, object] = {"fps": fps, "codec": "libx264", "logger": None}
    if with_click:
        write_kwargs["audio_codec"] = "aac"
    else:
        write_kwargs["audio"] = False

    clip.write_videofile(str(output_path), **write_kwargs)  # type: ignore[arg-type]

    if wav_path is not None:
        wav_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render demo clips for visualizer styles.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--styles", nargs="+", default=None, metavar="STYLE",
        help=f"Styles to render (default: all). Choices: {', '.join(STYLES)}",
    )
    parser.add_argument(
        "--new-only", action="store_true",
        help=f"Render only the four new styles: {', '.join(NEW_STYLES)}",
    )
    parser.add_argument("--tempo", type=float, default=DEFAULT_TEMPO, help="BPM (default: 120)")
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION, help="Seconds per style (default: 8)")
    parser.add_argument("--resolution", default="1280x720", help="WIDTHxHEIGHT (default: 1280x720)")
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS, help="Frames per second (default: 30)")
    parser.add_argument("--outdir", type=Path, default=Path("."), help="Output directory (default: current dir)")
    parser.add_argument(
        "--clips", type=Path, default=None,
        help="Directory of source video clips (base layer for overlay demos).",
    )
    parser.add_argument(
        "--include-overlay", action="store_true",
        help="Also render each style as an overlay on source clips. Requires --clips.",
    )
    parser.add_argument(
        "--overlay-alpha", type=float, default=DEFAULT_OVERLAY_ALPHA, metavar="ALPHA",
        help=f"Overlay opacity for --include-overlay (default: {DEFAULT_OVERLAY_ALPHA})",
    )
    parser.add_argument("--no-click", action="store_true", help="Omit click track (silent output)")
    parser.add_argument(
        "--reel", action="store_true",
        help="Also concatenate all rendered clips into demo_all.mp4",
    )
    parser.add_argument("--list", action="store_true", help="List available styles and exit")
    args = parser.parse_args()

    if args.list:
        print("All styles:")
        for s in STYLES:
            tag = "(new)" if s in NEW_STYLES else "     "
            print(f"  {tag}  {s}")
        return

    if args.include_overlay and args.clips is None:
        parser.error("--include-overlay requires --clips")

    if args.new_only and args.styles:
        parser.error("--new-only and --styles are mutually exclusive")

    if args.new_only:
        selected = NEW_STYLES
    elif args.styles:
        unknown = [s for s in args.styles if s not in STYLES]
        if unknown:
            print(f"Unknown styles: {unknown}. Available: {STYLES}", file=sys.stderr)
            sys.exit(1)
        selected = args.styles
    else:
        selected = STYLES

    w, h = (int(x) for x in args.resolution.lower().split("x"))
    resolution = (w, h)
    args.outdir.mkdir(parents=True, exist_ok=True)

    clip_paths: list[Path] = []
    if args.clips:
        clip_paths = _load_clips(args.clips)

    # Build the list of (style, overlay_alpha, base_clip_path, output_path) jobs
    jobs: list[tuple[str, float | None, Path | None, Path]] = []
    for style in selected:
        jobs.append((style, None, None, args.outdir / f"demo_{style}.mp4"))
    if args.include_overlay:
        for i, style in enumerate(selected):
            base_path = clip_paths[i % len(clip_paths)]
            jobs.append((
                style,
                args.overlay_alpha,
                base_path,
                args.outdir / f"demo_{style}_overlay.mp4",
            ))

    output_files: list[Path] = []
    for idx, (style, alpha, base_path, out) in enumerate(jobs, 1):
        variant = f"overlay α={alpha}" if alpha is not None else "standalone"
        print(f"[{idx}/{len(jobs)}] {style} ({variant}) → {out}")
        _render_style(
            style=style,
            duration=args.duration,
            resolution=resolution,
            fps=args.fps,
            tempo=args.tempo,
            overlay_alpha=alpha,
            base_clip_path=base_path,
            with_click=not args.no_click,
            output_path=out,
        )
        output_files.append(out)

    if args.reel and len(output_files) > 1:
        from moviepy import VideoFileClip, concatenate_videoclips

        reel_path = args.outdir / "demo_all.mp4"
        print(f"\nConcatenating reel → {reel_path}")
        clips = [VideoFileClip(str(p)) for p in output_files]
        reel = concatenate_videoclips(clips)
        write_kwargs = {"fps": args.fps, "codec": "libx264", "logger": None}
        if args.no_click:
            write_kwargs["audio"] = False  # type: ignore[assignment]
        reel.write_videofile(str(reel_path), **write_kwargs)  # type: ignore[arg-type]
        print(f"Reel: {reel_path}")

    print(f"\nDone. {len(output_files)} file(s) in {args.outdir}/")


if __name__ == "__main__":
    main()
