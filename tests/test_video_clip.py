import shutil
import subprocess

import pytest

from video_clip import find_span_sec, find_timecode_sec, make_slowmo_clip


def test_find_timecode():
    assert find_timecode_sec("🟠 00:03.125\nНаблюдение: x") == pytest.approx(3.125)
    assert find_timecode_sec("01:05 рука") == 65
    assert find_timecode_sec("без таймкода 12") is None


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="нужен ffmpeg")
def test_make_slowmo_clip(tmp_path):
    src = tmp_path / "src.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=5:size=320x240:rate=25",
            "-pix_fmt",
            "yuv420p",
            str(src),
        ],
        capture_output=True,
        check=True,
    )
    clip = make_slowmo_clip(src, 1.5, 3.5)
    assert clip is not None
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(clip),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert float(out.stdout) == pytest.approx(4.0, abs=0.3)
    finally:
        clip.unlink()


def test_analysis_checks_accept_millis():
    from analysis_checks import TIMECODE_RE, _seconds

    assert TIMECODE_RE.match("00:03.125") and TIMECODE_RE.match("00:03")
    assert _seconds("01:02.500") == 62.5


def test_find_span():
    assert find_span_sec("00:03.000–00:05.000\nНаблюдение") == (2.75, 5.25)
    assert find_span_sec("00:03.000–00:03.500") == (2.25, 4.25)
    assert find_span_sec("00:03.000–00:20.000") == (2.75, 8.75)
    assert find_span_sec("00:00.500") == (0.0, 3.0)
    assert find_span_sec("нет") is None


def test_render_remark_span():
    from render_report import _remark

    text = _remark(
        {
            "t": "00:01.000",
            "t_end": "00:02.500",
            "observation": "x",
            "why_it_matters": "y",
        }
    )
    assert text.startswith("00:01.000–00:02.500\n")
