# radiostar-killer

Generate music videos by syncing video clips to audio beats. Point it at a folder of video clips and an audio file, and it'll analyze the beat structure, chop and assign clips to beat groups, and export a beat-synced MP4.

## Install

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
git clone https://github.com/mcfredrick/radiostar-killer.git
cd radiostar-killer
uv sync
```

## Usage

```bash
radiostar-killer <clips_dir> <audio_file> [options]
```

### Example

```bash
uv run radiostar-killer ./my-clips ./song.wav -o music-video.mp4 --seed 42
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `-o`, `--output` | `output.mp4` | Output file path |
| `--min-beats` | `2` | Minimum beats per group |
| `--seed` | random | Seed for reproducible clip ordering and trimming |
| `--resolution` | `1920x1080` | Output resolution (`WIDTHxHEIGHT`) |
| `--fps` | `30` | Output frames per second |

## How it works

1. **Beat detection** — Uses [librosa](https://librosa.org/) to analyze the audio file, detect tempo, and extract beat timestamps.
2. **Beat grouping** — Partitions beats into groups of 4. Remainders smaller than `--min-beats` get merged into the previous group.
3. **Clip assignment** — Discovers video files (`.mp4`, `.mov`, `.avi`) in the clips directory, shuffles them, and assigns to beat groups via round-robin. Clips are recycled if there are fewer clips than groups.
4. **Video assembly** — Each clip is trimmed (from a random point) or looped to match its beat group duration, resized to the target resolution, then concatenated. The original audio is overlaid and the final video is exported with H.264/AAC via [moviepy](https://zulko.github.io/moviepy/).

## Development

```bash
# Run tests
uv run pytest

# Run linting
uv run ruff check src/ tests/

# Type checking
uv run mypy src/
```
