"""Unit tests for video module."""

from moviepy import ColorClip

from radiostar_killer.video import _resize_crop


class TestResizeCrop:
    def test_landscape_to_portrait(self):
        """Landscape clip → portrait target crops left/right edges."""
        clip = ColorClip(size=(1920, 1080), color=(255, 0, 0), duration=1.0)
        clip = clip.with_fps(10)

        result = _resize_crop(clip, 1080, 1920)

        assert tuple(result.size) == (1080, 1920)
        clip.close()
        result.close()

    def test_portrait_to_landscape(self):
        """Portrait clip → landscape target crops top/bottom edges."""
        clip = ColorClip(size=(1080, 1920), color=(0, 255, 0), duration=1.0)
        clip = clip.with_fps(10)

        result = _resize_crop(clip, 1920, 1080)

        assert tuple(result.size) == (1920, 1080)
        clip.close()
        result.close()

    def test_same_aspect_ratio(self):
        """Same aspect ratio just scales, no crop needed."""
        clip = ColorClip(size=(640, 480), color=(0, 0, 255), duration=1.0)
        clip = clip.with_fps(10)

        result = _resize_crop(clip, 320, 240)

        assert tuple(result.size) == (320, 240)
        clip.close()
        result.close()

    def test_same_resolution(self):
        """Clip already at target resolution is unchanged."""
        clip = ColorClip(size=(320, 240), color=(255, 255, 0), duration=1.0)
        clip = clip.with_fps(10)

        result = _resize_crop(clip, 320, 240)

        assert tuple(result.size) == (320, 240)
        clip.close()
        result.close()

    def test_square_to_landscape(self):
        """Square clip → landscape target crops top/bottom."""
        clip = ColorClip(size=(500, 500), color=(128, 128, 128), duration=1.0)
        clip = clip.with_fps(10)

        result = _resize_crop(clip, 400, 200)

        assert tuple(result.size) == (400, 200)
        clip.close()
        result.close()
