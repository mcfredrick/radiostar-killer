# CLAUDE.md

## Project Overview

**radiostar-killer** is a Python CLI that generates beat-synced music videos. Given a directory of video clips and an audio file, it detects beats, groups them, assigns clips to groups, and exports a final MP4.

## Commands

```bash
uv sync                          # install all deps (including dev)
uv run pytest                    # run all tests
uv run pytest -m "not e2e"       # run fast unit tests only
uv run pytest -m e2e             # run e2e tests (slower, generates real video)
uv run ruff check src/ tests/    # lint
uv run ruff check --fix src/ tests/  # lint with auto-fix
uv run mypy src/                 # type check
uv run radiostar-killer --help   # CLI usage
```

## Architecture

The pipeline flows through five modules in order:

```
cli.py → main.py → audio.py → clips.py → video.py
                    formats.py (preset config)
                    effects.py (visual effects & transitions)
```

### Module Responsibilities

| Module | Purpose |
|--------|---------|
| `cli.py` | argparse entry point, parses args and calls `main.run()` |
| `main.py` | Orchestrator — wires together audio analysis, clip assignment, and video export; handles shorts generation path |
| `audio.py` | `analyze_audio()` uses librosa for beat detection; `group_beats()` partitions beat timestamps; `analyze_energy()` finds high-energy sections via RMS |
| `clips.py` | `discover_clips()` finds video files; `assign_clips_to_groups()` shuffles and round-robins clips to beat groups |
| `video.py` | `prepare_clip()` trims or loops a clip to fit a duration; `build_video()` concatenates clips, optionally applies effects/transitions, overlays audio, exports MP4 using `FormatPreset` |
| `formats.py` | `FormatPreset` dataclass + `PRESETS` dict (youtube, youtube-shorts, tiktok, instagram-reels) + `resolve_format()` helper |
| `effects.py` | `apply_random_effect()` picks from 11 visual effects (8 built-in moviepy + 3 custom); `select_transition()` and `compose_with_transitions()` handle crossfade/slide transitions between clips |

### Key Data Structures

- **`FormatPreset`** (frozen dataclass): name, resolution, fps, codec, audio_codec, bitrate, audio_bitrate, max_duration
- **`AudioInfo`** (dataclass): tempo, beat_times, duration, sample_rate
- **`EnergySection`** (dataclass): start, end, mean_energy
- **`ClipAssignment`** (dataclass): path, target_duration, original_duration
- **`TransitionSpec`** (dataclass): transition_type, duration
- Beat groups are `list[tuple[float, float]]` — each tuple is `(start_time, end_time)` in seconds

### Pipeline Flow

**Normal path** (`--format`):
1. **Beat detection**: librosa analyzes audio → tempo + beat timestamps
2. **Beat grouping**: Beats partitioned into groups of 4. Remainder < `min_beats` merges into previous group
3. **Clip discovery**: Scans directory for `.mp4`, `.mov`, `.avi` files
4. **Clip assignment**: Shuffled round-robin. If fewer clips than groups, clips are recycled
5. **Effects** (optional): If `--effects`, random visual effects applied per-clip based on `--effect-rate`
6. **Video assembly**: Each clip trimmed from random start (if too long) or looped (if too short), resized, concatenated (or composed with transitions if `--transitions`), audio overlaid, exported using preset codec/bitrate settings

**Shorts path** (`--shorts`):
1. **Beat detection**: Same as normal
2. **Energy analysis**: `analyze_energy()` computes RMS energy with a sliding window, greedily selects top 3 non-overlapping high-energy sections
3. **Per-section pipeline**: For each section, beats are filtered and made relative, grouped, assigned clips, and exported as a separate video with `audio_start`/`audio_end` trimming

## Dependencies

- **librosa** — audio/beat analysis (pulls in numba/llvmlite)
- **moviepy** — video editing/export (uses ffmpeg via imageio-ffmpeg)
- **numpy/scipy** — numerical support for librosa
- **numba < 0.63 / llvmlite < 0.46** — pinned to avoid build failures with newer setuptools

## Testing

- `tests/test_audio.py` — unit tests for `group_beats()` (8 tests) and `analyze_energy()` (4 tests)
- `tests/test_clips.py` — unit tests for `discover_clips()` and `assign_clips_to_groups()` (10 tests)
- `tests/test_effects.py` — unit tests for `apply_random_effect()`, `select_transition()`, and `compose_with_transitions()` (16 tests)
- `tests/test_formats.py` — unit tests for `PRESETS` validation and `resolve_format()` (13 tests)
- `tests/test_e2e.py` — full pipeline tests using synthetic color clips and a sine wave audio file, including effects+transitions variant (marked `@pytest.mark.e2e`)
- `tests/conftest.py` — shared fixtures: `tmp_clips_dir` (3 color clips, 320x240, 10fps) and `tmp_audio_file` (6s sine wave)

## Important Notes

- **Always add documentation when implementing new features.** Update `README.md` (user-facing usage, examples, options table) and `CLAUDE.md` (architecture, module responsibilities, data structures, tests) to reflect any new functionality.
- Input paths must be local filesystem paths, not SMB/network URLs. On macOS, mounted shares are at `/Volumes/<share_name>/`
- The `.gitignore` excludes all video/audio files and the `output.*` file — don't commit media
- Clip scanning is top-level only (not recursive into subdirectories)
- Python 3.12 is used (set in `.python-version`) due to numba/llvmlite compatibility
