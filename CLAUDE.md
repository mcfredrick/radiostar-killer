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

The pipeline flows through four modules in order:

```
cli.py → main.py → audio.py → clips.py → video.py
```

### Module Responsibilities

| Module | Purpose |
|--------|---------|
| `cli.py` | argparse entry point, parses args and calls `main.run()` |
| `main.py` | Orchestrator — wires together audio analysis, clip assignment, and video export |
| `audio.py` | `analyze_audio()` uses librosa for beat detection; `group_beats()` partitions beat timestamps into groups of 4 |
| `clips.py` | `discover_clips()` finds video files; `assign_clips_to_groups()` shuffles and round-robins clips to beat groups |
| `video.py` | `prepare_clip()` trims or loops a clip to fit a duration; `build_video()` concatenates clips, overlays audio, exports MP4 |

### Key Data Structures

- **`AudioInfo`** (dataclass): tempo, beat_times, duration, sample_rate
- **`ClipAssignment`** (dataclass): path, target_duration, original_duration
- Beat groups are `list[tuple[float, float]]` — each tuple is `(start_time, end_time)` in seconds

### Pipeline Flow

1. **Beat detection**: librosa analyzes audio → tempo + beat timestamps
2. **Beat grouping**: Beats partitioned into groups of 4. Remainder < `min_beats` merges into previous group
3. **Clip discovery**: Scans directory for `.mp4`, `.mov`, `.avi` files
4. **Clip assignment**: Shuffled round-robin. If fewer clips than groups, clips are recycled
5. **Video assembly**: Each clip trimmed from random start (if too long) or looped (if too short), resized, concatenated, audio overlaid, exported as H.264/AAC

## Dependencies

- **librosa** — audio/beat analysis (pulls in numba/llvmlite)
- **moviepy** — video editing/export (uses ffmpeg via imageio-ffmpeg)
- **numpy/scipy** — numerical support for librosa
- **numba < 0.63 / llvmlite < 0.46** — pinned to avoid build failures with newer setuptools

## Testing

- `tests/test_audio.py` — unit tests for `group_beats()` (8 tests covering exact multiples, remainders, edge cases)
- `tests/test_clips.py` — unit tests for `discover_clips()` and `assign_clips_to_groups()` (10 tests)
- `tests/test_e2e.py` — full pipeline test using synthetic color clips and a sine wave audio file (marked `@pytest.mark.e2e`)
- `tests/conftest.py` — shared fixtures: `tmp_clips_dir` (3 color clips, 320x240, 10fps) and `tmp_audio_file` (6s sine wave)

## Important Notes

- Input paths must be local filesystem paths, not SMB/network URLs. On macOS, mounted shares are at `/Volumes/<share_name>/`
- The `.gitignore` excludes all video/audio files and the `output.*` file — don't commit media
- Clip scanning is top-level only (not recursive into subdirectories)
- Python 3.12 is used (set in `.python-version`) due to numba/llvmlite compatibility
