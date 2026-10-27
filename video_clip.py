"""Замедленный отрезок видео вокруг таймкода наблюдения."""

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

FFMPEG_TIMEOUT_SEC = 90
CLIP_PAD_SEC = 0.25
DEFAULT_BEFORE_SEC = 1.0
DEFAULT_AFTER_SEC = 2.5
MIN_CLIP_SEC = 2.0
MAX_CLIP_SEC = 6.0
SLOWDOWN = 2.0
MAX_CLIP_SIDE = 720

_TS = r"(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?"
_TIMECODE = re.compile(rf"(?<![\d:]){_TS}(?![\d:])")
_SPAN = re.compile(rf"(?<![\d:]){_TS}\s*[–—-]\s*{_TS}(?![\d:])")


def _to_sec(minutes: str, seconds: str, frac: Optional[str]) -> float:
    millis = float(f"0.{frac}") if frac else 0.0
    return int(minutes) * 60 + int(seconds) + millis


def find_timecode_sec(text: str) -> Optional[float]:
    """Первый таймкод вида MM:SS или MM:SS.mmm в секундах."""
    match = _TIMECODE.search(text or "")
    if not match:
        return None
    return _to_sec(*match.groups())


def find_span_sec(text: str) -> Optional[tuple]:
    """Окно показа (start, end) в секундах из «MM:SS.mmm–MM:SS.mmm» или одного таймкода."""
    span = _SPAN.search(text or "")
    if span:
        g = span.groups()
        start, end = _to_sec(*g[:3]), _to_sec(*g[3:])
        if end > start:
            return clip_window(start, end)
    point = find_timecode_sec(text)
    if point is None:
        return None
    return max(0.0, point - DEFAULT_BEFORE_SEC), point + DEFAULT_AFTER_SEC


def clip_window(start: float, end: float) -> tuple:
    """Отрезок модели с небольшим запасом; длина от 2 до 6 секунд."""
    lo = max(0.0, start - CLIP_PAD_SEC)
    hi = end + CLIP_PAD_SEC
    if hi - lo < MIN_CLIP_SEC:
        extra = (MIN_CLIP_SEC - (hi - lo)) / 2
        lo = max(0.0, lo - extra)
        hi = lo + MIN_CLIP_SEC
    if hi - lo > MAX_CLIP_SEC:
        hi = lo + MAX_CLIP_SEC
    return lo, hi


def make_slowmo_clip(src: Path, start_sec: float, end_sec: float) -> Optional[Path]:
    """mp4 без звука: отрезок [start; end] замедлен в 2 раза. Вызывающий удаляет файл."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not Path(src).is_file():
        return None

    start = max(0.0, start_sec)
    duration = max(0.5, end_sec - start)
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    out = Path(tmp.name)
    tmp.close()

    scale = (
        f"scale='if(gt(iw,ih),min({MAX_CLIP_SIDE},iw),-2)':"
        f"'if(gt(iw,ih),-2,min({MAX_CLIP_SIDE},ih))'"
    )
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        f"{start:.3f}",
        "-i",
        str(src),
        "-t",
        f"{duration:.3f}",
        "-an",
        "-vf",
        f"{scale},setpts={SLOWDOWN}*PTS",
        "-c:v",
        "libx264",
        "-threads",
        "1",
        "-preset",
        "veryfast",
        "-crf",
        "28",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(out),
    ]
    nice = shutil.which("nice")
    if nice:
        cmd = [nice, "-n", "10", *cmd]
    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=FFMPEG_TIMEOUT_SEC, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("slowmo clip: ffmpeg не отработал: %s", exc)
        out.unlink(missing_ok=True)
        return None

    if result.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
        err = (result.stderr or b"")[-300:].decode("utf-8", errors="replace")
        logger.warning("slowmo clip: ffmpeg code=%s %s", result.returncode, err)
        out.unlink(missing_ok=True)
        return None
    return out
