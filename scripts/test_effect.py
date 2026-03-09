#!/usr/bin/env python3
"""Test a specific effect or split-screen layout by applying it explicitly to clips.

Usage examples:
    uv run scripts/test_effect.py --clips /path/to/clips --effect mirror_x
    uv run scripts/test_effect.py --clips /path/to/clips --effect splitscreen-4
    uv run scripts/test_effect.py --clips /path/to/clips --effect climax-burst
    uv run scripts/test_effect.py --clips /path/to/clips --effect climax-burst --tempo 95
    uv run scripts/test_effect.py --clips /path/to/clips --effect blur --output test_blur.mp4
    uv run scripts/test_effect.py --list
"""

import argparse
import inspect
import random
import sys
from pathlib import Path

from moviepy import VideoFileClip, concatenate_videoclips

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from radiostar_killer.effects import BUILTIN_NAMED, CUSTOM_NAMED, apply_named_effect
from radiostar_killer.splitscreen import (
    PANEL_EFFECT_RATE,
    _apply_panel_effects,
    build_climax_burst,
    compose_split_screen,
)

RESOLUTION = (1280, 720)
FPS = 30
CLIP_DURATION = 3.0  # seconds per clip in output
SEED = 42
DEFAULT_TEMPO = 120.0

SPLITSCREEN_PANELS = {"splitscreen-2": 2, "splitscreen-4": 4, "splitscreen-6": 6}
ALL_EFFECTS = sorted(list(BUILTIN_NAMED) + list(CUSTOM_NAMED) + list(SPLITSCREEN_PANELS) + ["climax-burst"])


def _kwargs_for(func: object, args: argparse.Namespace) -> dict[str, object]:
    """Return kwargs to forward from argparse args to func.

    Matches optional keyword parameters (those with defaults) by name against
    attributes in the argparse namespace. Adding a new --my-flag arg and a
    matching my_flag=None parameter to the target function is all that's needed
    — no manual wiring required.
    """
    sig = inspect.signature(func)  # type: ignore[arg-type]
    return {
        name: getattr(args, name)
        for name, param in sig.parameters.items()
        if param.default is not inspect.Parameter.empty and hasattr(args, name)
    }


def _load_clips(clips_dir: Path) -> list[Path]:
    exts = {".mp4", ".mov", ".avi"}
    clips = [p for p in clips_dir.iterdir() if p.suffix.lower() in exts]
    if not clips:
        print(f"No video clips found in {clips_dir}", file=sys.stderr)
        sys.exit(1)
    return sorted(clips)


def _resize_crop(clip: VideoFileClip, w: int, h: int) -> VideoFileClip:
    src_w, src_h = clip.size
    scale = max(w / src_w, h / src_h)
    clip = clip.resized(scale)
    cw, ch = clip.size
    return clip.cropped(
        x1=cw / 2 - w / 2,
        y1=ch / 2 - h / 2,
        x2=cw / 2 + w / 2,
        y2=ch / 2 + h / 2,
    )


def _prepare(path: Path, duration: float) -> VideoFileClip:
    clip = VideoFileClip(str(path))
    clip = _resize_crop(clip, *RESOLUTION)
    if clip.duration < duration:
        n = int(duration / clip.duration) + 1
        from moviepy import concatenate_videoclips as cv
        clip = cv([clip] * n).subclipped(0, duration)
    else:
        clip = clip.subclipped(0, duration)
    return clip.with_fps(FPS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test a specific effect on video clips.")
    parser.add_argument("--clips", type=Path, help="Directory containing source clips")
    parser.add_argument("--effect", help="Effect name to apply")
    parser.add_argument("--output", type=Path, default=Path("test_effect_output.mp4"))
    parser.add_argument("--duration", type=float, default=CLIP_DURATION, help="Seconds per clip (default: 3)")
    parser.add_argument("--tempo", type=float, default=DEFAULT_TEMPO, help="BPM for climax-burst step duration (default: 120)")
    parser.add_argument("--layout", choices=["grid", "radial"], default=None, help="Force split screen layout for climax-burst or splitscreen-N (default: random)")
    parser.add_argument("--double-time", action=argparse.BooleanOptionalAction, default=None, help="Force double-time for climax-burst (default: random 70%%)")
    parser.add_argument("--panel-effect-rate", type=float, default=PANEL_EFFECT_RATE,
                        help=f"Probability each split-screen panel gets a random filter (default: {PANEL_EFFECT_RATE})")
    parser.add_argument("--contrast", action=argparse.BooleanOptionalAction, default=None,
                        help="Force contrast tint mode for split-screen panels (default: random)")
    parser.add_argument("--seed", type=int, default=SEED, help="RNG seed for reproducible results")
    parser.add_argument("--list", action="store_true", help="List all available effects and exit")
    args = parser.parse_args()

    if args.list:
        print("Available effects:")
        for name in ALL_EFFECTS:
            print(f"  {name}")
        return

    if not args.clips or not args.effect:
        parser.error("--clips and --effect are required (or use --list)")

    if args.effect not in ALL_EFFECTS:
        print(f"Unknown effect '{args.effect}'. Run --list to see options.", file=sys.stderr)
        sys.exit(1)

    rng = random.Random(args.seed)
    clip_paths = _load_clips(args.clips)

    # Climax burst: 2→4→6→4→2 panel sequence at given tempo
    if args.effect == "climax-burst":
        print(f"Building climax burst (tempo={args.tempo} BPM) from {len(clip_paths)} clip(s)...")
        pool = [_prepare(p, args.duration) for p in clip_paths]
        result = build_climax_burst(pool, args.tempo, RESOLUTION, FPS, rng,
                                    **_kwargs_for(build_climax_burst, args))

    # Split screen: need exactly N clips
    elif args.effect in SPLITSCREEN_PANELS:
        panels = SPLITSCREEN_PANELS[args.effect]
        # Cycle paths to get exactly `panels` clips
        selected = [clip_paths[i % len(clip_paths)] for i in range(panels)]
        mode = "contrast" if args.contrast else ("random effects" if args.contrast is False else "random mode")
        print(f"Compositing {panels}-panel split screen from {len(selected)} clips ({mode})...")
        loaded = [_prepare(p, args.duration) for p in selected]
        loaded = _apply_panel_effects(loaded, rng, rate=args.panel_effect_rate,
                                      **_kwargs_for(_apply_panel_effects, args))
        result = compose_split_screen(loaded, RESOLUTION, FPS, layout=args.layout or "grid")
    else:
        # Per-clip effect: apply to every clip, then concatenate
        print(f"Applying '{args.effect}' to {len(clip_paths)} clip(s)...")
        clips = []
        for path in clip_paths:
            clip = _prepare(path, args.duration)
            clip = apply_named_effect(args.effect, clip, rng)
            clips.append(clip)
        result = concatenate_videoclips(clips)

    print(f"Writing {args.output} ...")
    result.write_videofile(str(args.output), fps=FPS, codec="libx264", audio=False, logger=None)
    print(f"Done: {args.output}")


if __name__ == "__main__":
    main()
