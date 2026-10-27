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
CLIP_BEFORE_SEC = 1.0
CLIP_AFTER_SEC = 1.0
SLOWDOWN = 2.0
MAX_CLIP_SIDE = 720

_TIMECODE = re.compile(r"(?<![\d:])(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?(?![\d:])")


def find_timecode_sec(text: str) -> Optional[float]:
    """Первый таймкод вида MM:SS или MM:SS.mmm в секундах."""
    match = _TIMECODE.search(text or "")
    if not match:
        return None
    minutes, seconds, frac = match.groups()
    millis = float(f"0.{frac}") if frac else 0.0
    return int(minutes) * 60 + int(seconds) + millis


def make_slowmo_clip(src: Path, center_sec: float) -> Optional[Path]:
    """mp4 без звука: [t-1с; t+1с] замедлено в 2 раза. Вызывающий удаляет файл."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not Path(src).is_file():
        return None

    start = max(0.0, center_sec - CLIP_BEFORE_SEC)
    duration = CLIP_BEFORE_SEC + CLIP_AFTER_SEC
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
