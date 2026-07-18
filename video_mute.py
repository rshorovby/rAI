"""Strip audio from video before Gemini upload to avoid ~32 tok/s audio billing."""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

FFMPEG_TIMEOUT_SEC = 60


def strip_audio_for_upload(video_path: Path) -> Tuple[Path, Optional[Path]]:
    """Return (path_to_upload, temp_file_to_delete_or_None).

    On success, path_to_upload is a mute copy and the caller must delete the temp.
    If ffmpeg is missing or fails, returns the original path and None (no cleanup).
    """
    video_path = Path(video_path)
    if not video_path.is_file():
        return video_path, None

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        logger.info("ffmpeg не найден — загружаем видео с аудио как есть")
        return video_path, None

    suffix = video_path.suffix or ".mp4"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-an",
        "-c:v",
        "copy",
        "-movflags",
        "+faststart",
        str(tmp_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=FFMPEG_TIMEOUT_SEC,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Не удалось снять аудио (ffmpeg): %s — upload как есть", exc)
        _safe_unlink(tmp_path)
        return video_path, None

    if result.returncode != 0 or not tmp_path.is_file() or tmp_path.stat().st_size == 0:
        err = (result.stderr or b"")[-400:].decode("utf-8", errors="replace")
        logger.warning(
            "ffmpeg -an завершился с ошибкой (code=%s): %s — upload как есть",
            result.returncode,
            err,
        )
        _safe_unlink(tmp_path)
        return video_path, None

    logger.info("Аудиодорожка снята перед upload в Gemini (%s)", tmp_path.name)
    return tmp_path, tmp_path


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Не удалось удалить временный mute-файл: %s", path)
