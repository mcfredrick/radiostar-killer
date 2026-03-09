"""Tests for format presets and resolution helpers."""

import pytest

from radiostar_killer.formats import PRESETS, resolve_format


class TestPresets:
    def test_all_presets_have_valid_resolution(self):
        for name, preset in PRESETS.items():
            assert isinstance(preset.resolution, tuple), (
                f"{name} resolution not a tuple"
            )
            w, h = preset.resolution
            assert w > 0 and h > 0, f"{name} has non-positive resolution"

    def test_all_presets_have_positive_fps(self):
        for name, preset in PRESETS.items():
            assert preset.fps > 0, f"{name} has non-positive fps"

    def test_expected_presets_exist(self):
        expected = {"youtube", "youtube-shorts", "tiktok", "instagram-reels"}
        assert set(PRESETS.keys()) == expected

    def test_youtube_is_landscape(self):
        p = PRESETS["youtube"]
        assert p.resolution[0] > p.resolution[1]

    def test_vertical_presets_are_portrait(self):
        for name in ("youtube-shorts", "tiktok", "instagram-reels"):
            p = PRESETS[name]
            assert p.resolution[1] > p.resolution[0], f"{name} should be portrait"

    def test_youtube_shorts_has_max_duration(self):
        assert PRESETS["youtube-shorts"].max_duration == 180.0


class TestResolveFormat:
    def test_defaults_to_youtube(self):
        preset = resolve_format()
        assert preset.name == "youtube"

    def test_explicit_format(self):
        preset = resolve_format("tiktok")
        assert preset.name == "tiktok"
        assert preset.bitrate == "12M"

    def test_resolution_override(self):
        preset = resolve_format("youtube", resolution_override=(1280, 720))
        assert preset.resolution == (1280, 720)
        # Other fields unchanged
        assert preset.name == "youtube"
        assert preset.fps == 30

    def test_fps_override(self):
        preset = resolve_format("youtube", fps_override=60)
        assert preset.fps == 60
        assert preset.resolution == (1920, 1080)

    def test_both_overrides(self):
        preset = resolve_format(
            "tiktok",
            resolution_override=(720, 1280),
            fps_override=24,
        )
        assert preset.resolution == (720, 1280)
        assert preset.fps == 24
        assert preset.bitrate == "12M"  # not overridden

    def test_unknown_format_raises(self):
        with pytest.raises(ValueError, match="Unknown format"):
            resolve_format("nonexistent")

    def test_no_overrides_returns_preset_as_is(self):
        preset = resolve_format("instagram-reels")
        assert preset == PRESETS["instagram-reels"]
