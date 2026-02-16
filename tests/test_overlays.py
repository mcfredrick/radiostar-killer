"""Tests for the overlays module."""

import numpy as np
import pytest
from moviepy import CompositeVideoClip

from radiostar_killer.overlays import (
    InfoOverlayConfig,
    TitleCardConfig,
    create_info_overlay,
    create_title_card,
    snap_to_nearest_beat,
)


class TestTitleCardConfig:
    def test_defaults(self):
        config = TitleCardConfig(title="Test")
        assert config.title == "Test"
        assert config.subtitle is None
        assert config.duration == 3.5
        assert config.fade_duration == 0.8
        assert config.bg_color == (0, 0, 0)
        assert config.text_color == "white"
        assert config.font == "Arial"

    def test_frozen(self):
        config = TitleCardConfig(title="Test")
        with pytest.raises(AttributeError):
            config.title = "Changed"  # type: ignore[misc]


class TestInfoOverlayConfig:
    def test_defaults(self):
        config = InfoOverlayConfig(title="Song", artist="Artist")
        assert config.title == "Song"
        assert config.artist == "Artist"
        assert config.album is None
        assert config.display_duration == 8.0
        assert config.fade_in_duration == 0.5
        assert config.fade_out_duration == 1.5
        assert config.delay == 1.0
        assert config.text_color == "white"

    def test_frozen(self):
        config = InfoOverlayConfig(title="Song", artist="Artist")
        with pytest.raises(AttributeError):
            config.artist = "Changed"  # type: ignore[misc]


class TestSnapToNearestBeat:
    def test_snaps_to_closest_beat(self):
        beats = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        assert snap_to_nearest_beat(3.3, beats) == 3.0
        assert snap_to_nearest_beat(3.7, beats) == 4.0

    def test_exact_match(self):
        beats = np.array([1.0, 2.0, 3.0])
        assert snap_to_nearest_beat(2.0, beats) == 2.0

    def test_empty_beats_returns_target(self):
        beats = np.array([])
        assert snap_to_nearest_beat(3.5, beats) == 3.5

    def test_single_beat(self):
        beats = np.array([2.5])
        assert snap_to_nearest_beat(10.0, beats) == 2.5

    def test_snaps_to_first_when_equidistant(self):
        # numpy argmin returns the first index for ties
        beats = np.array([2.0, 4.0])
        result = snap_to_nearest_beat(3.0, beats)
        assert result in (2.0, 4.0)


class TestCreateTitleCard:
    def test_correct_dimensions(self):
        config = TitleCardConfig(title="Test Title", duration=2.0)
        card = create_title_card(config, (320, 240), 10)
        try:
            assert card.size == (320, 240)
            assert card.duration == 2.0
        finally:
            card.close()

    def test_with_subtitle(self):
        config = TitleCardConfig(title="Title", subtitle="Subtitle", duration=2.0)
        card = create_title_card(config, (320, 240), 10)
        try:
            assert card.size == (320, 240)
            assert card.duration == 2.0
        finally:
            card.close()

    def test_without_subtitle(self):
        config = TitleCardConfig(title="Title Only", duration=2.0)
        card = create_title_card(config, (320, 240), 10)
        try:
            assert card.size == (320, 240)
        finally:
            card.close()

    def test_resolution_scaling(self):
        config = TitleCardConfig(title="Hi-Res", duration=1.0)
        card = create_title_card(config, (1920, 1080), 30)
        try:
            assert card.size == (1920, 1080)
            assert card.fps == 30
        finally:
            card.close()

    def test_renders_frame(self):
        config = TitleCardConfig(title="Render Test", duration=1.0)
        card = create_title_card(config, (320, 240), 10)
        try:
            frame = card.get_frame(0.5)
            assert frame.shape == (240, 320, 3)
        finally:
            card.close()


class TestCreateInfoOverlay:
    def test_correct_dimensions(self):
        config = InfoOverlayConfig(title="Song", artist="Artist")
        overlay = create_info_overlay(config, (320, 240), 10)
        try:
            assert overlay.size == (320, 240)
        finally:
            overlay.close()

    def test_with_album(self):
        config = InfoOverlayConfig(
            title="Song", artist="Artist", album="Album"
        )
        overlay = create_info_overlay(config, (320, 240), 10)
        try:
            assert overlay.size == (320, 240)
        finally:
            overlay.close()

    def test_without_album(self):
        config = InfoOverlayConfig(title="Song", artist="Artist")
        overlay = create_info_overlay(config, (320, 240), 10)
        try:
            assert overlay.size == (320, 240)
        finally:
            overlay.close()

    def test_duration_matches_display_duration(self):
        config = InfoOverlayConfig(
            title="Song", artist="Artist", display_duration=5.0
        )
        overlay = create_info_overlay(config, (320, 240), 10)
        try:
            assert overlay.duration == 5.0
        finally:
            overlay.close()

    def test_start_equals_delay(self):
        config = InfoOverlayConfig(
            title="Song", artist="Artist", delay=2.0
        )
        overlay = create_info_overlay(config, (320, 240), 10)
        try:
            assert overlay.start == 2.0
        finally:
            overlay.close()

    def test_resolution_scaling(self):
        config = InfoOverlayConfig(title="Song", artist="Artist")
        overlay = create_info_overlay(config, (1920, 1080), 30)
        try:
            assert overlay.size == (1920, 1080)
        finally:
            overlay.close()
