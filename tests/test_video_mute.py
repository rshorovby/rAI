"""Tests for stripping audio before Gemini upload."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from video_mute import strip_audio_for_upload


def test_strip_audio_ffmpeg_missing(tmp_path: Path):
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"fake")
    with patch("video_mute.shutil.which", return_value=None):
        path, tmp = strip_audio_for_upload(src)
    assert path == src
    assert tmp is None


def test_strip_audio_success(tmp_path: Path):
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"fake-video")
    with patch("video_mute.shutil.which", return_value="/usr/bin/ffmpeg"):
        with patch("video_mute.subprocess.run") as run:

            def _side_effect(cmd, **kwargs):
                out = Path(cmd[-1])
                out.write_bytes(b"muted")
                return MagicMock(returncode=0, stderr=b"")

            run.side_effect = _side_effect
            path, tmp = strip_audio_for_upload(src)

    assert tmp is not None
    assert path == tmp
    assert path.read_bytes() == b"muted"
    assert "-an" in run.call_args[0][0]
    tmp.unlink()


def test_strip_audio_ffmpeg_fails_falls_back(tmp_path: Path):
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"fake")
    with patch("video_mute.shutil.which", return_value="/usr/bin/ffmpeg"):
        with patch(
            "video_mute.subprocess.run",
            return_value=MagicMock(returncode=1, stderr=b"error"),
        ):
            path, tmp = strip_audio_for_upload(src)
    assert path == src
    assert tmp is None
