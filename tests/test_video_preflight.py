import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from video_preflight import Preflight, _parse_rate, check_video, progress_text


def _good(**overrides) -> Preflight:
    values = dict(width=1920, height=1080, fps=60.0, duration_sec=12.4, brightness=120)
    values.update(overrides)
    return Preflight(**values)


def test_parse_rate():
    assert _parse_rate("30000/1001") == pytest.approx(29.97, abs=0.01)
    assert _parse_rate("60/1") == 60
    assert _parse_rate("0/0") is None
    assert _parse_rate("") is None


def test_good_video_has_no_tips():
    assert _good().tips() == []


def test_tips_for_low_fps_low_res_dark():
    video = _good(width=640, height=360, fps=15.0, brightness=20)
    assert video.tips() == ["pf_tip_low_fps", "pf_tip_low_res", "pf_tip_dark"]


def test_vertical_video_uses_short_side():
    assert _good(width=1080, height=1920).short_side == 1080


def test_progress_text_watching():
    text = progress_text("ru", _good(), watching=True)
    assert "12 с · 1080p · 60 кадров/с" in text
    assert "Смотрю технику" in text
    assert "Совет" not in text


def test_progress_text_final_keeps_tips_without_watching():
    text = progress_text("ru", _good(fps=15.0), watching=False)
    assert "15 кадров/с" in text
    assert "Совет к следующей съёмке" in text
    assert "Смотрю" not in text


def test_progress_text_without_preflight():
    assert progress_text("en", None, watching=True).startswith("🧠")
    assert progress_text("en", None, watching=False) == ""


def test_check_video_without_ffprobe(tmp_path: Path):
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"fake")
    with patch("video_preflight.shutil.which", return_value=None):
        assert check_video(src) is None


@pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="нет ffmpeg"
)
def test_check_video_real_file(tmp_path: Path):
    src = tmp_path / "dark.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=0x101010:s=320x240:r=15:d=2",
            "-pix_fmt",
            "yuv420p",
            str(src),
        ],
        check=True,
    )
    result = check_video(src)
    assert result is not None
    assert (result.width, result.height) == (320, 240)
    assert result.fps == pytest.approx(15)
    assert result.duration_sec == pytest.approx(2, abs=0.2)
    assert result.tips() == ["pf_tip_low_fps", "pf_tip_low_res", "pf_tip_dark"]
