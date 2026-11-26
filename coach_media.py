"""Хранение и конвертация голосовых сообщений тренера для iOS."""

from __future__ import annotations

import logging
import math
import shutil
import struct
import subprocess
from pathlib import Path
from typing import Optional

import storage

logger = logging.getLogger(__name__)

WAVEFORM_BARS = 36
_FFMPEG_TIMEOUT = 60


def media_root() -> Path:
    return storage.DB_PATH.parent / "coach_media"


def resolve_media_path(rel_path: str) -> Optional[Path]:
    raw = (rel_path or "").strip()
    if not raw:
        return None
    root = media_root().resolve()
    candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def delete_player_media(player_id: int) -> None:
    folder = media_root() / str(int(player_id))
    if folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)


def _compute_waveform(pcm: bytes, bars: int = WAVEFORM_BARS) -> list[float]:
    sample_count = len(pcm) // 2
    if sample_count == 0 or bars <= 0:
        return []
    samples = struct.unpack(f"<{sample_count}h", pcm[: sample_count * 2])
    bucket_size = max(1, sample_count // bars)
    peaks: list[float] = []
    for i in range(bars):
        start = i * bucket_size
        if start >= sample_count:
            break
        end = sample_count if i == bars - 1 else min(sample_count, start + bucket_size)
        chunk = samples[start:end]
        if not chunk:
            peaks.append(0.0)
            continue
        rms = math.sqrt(sum(s * s for s in chunk) / len(chunk)) / 32768.0
        peaks.append(rms)
    if not peaks:
        return []
    max_peak = max(peaks)
    if max_peak <= 1e-6:
        return [0.15 for _ in peaks]
    return [round(max(0.1, min(1.0, p / max_peak)), 3) for p in peaks]


def _extract_pcm_metrics(
    ffmpeg: str, audio_path: Path
) -> tuple[int, list[float]]:
    cmd = [
        ffmpeg,
        "-v",
        "error",
        "-i",
        str(audio_path),
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        "8000",
        "pipe:1",
    ]
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            timeout=_FFMPEG_TIMEOUT,
            check=False,
        )
    except Exception:
        logger.warning("coach_media: waveform ffmpeg failed", exc_info=True)
        return 0, []
    if res.returncode != 0 or not res.stdout:
        return 0, []
    pcm = res.stdout
    duration = int(round((len(pcm) // 2) / 8000.0))
    return duration, _compute_waveform(pcm)


def transcode_voice_to_m4a(
    src: Path,
    *,
    player_id: int,
    job_id: int,
    message_key: str,
    duration_hint: int = 0,
) -> dict:
    """Конвертирует аудио (обычно Telegram OGG/Opus) в .m4a (AAC) для iOS."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")
    if not Path(src).is_file():
        raise FileNotFoundError(str(src))

    safe_key = "".join(ch for ch in str(message_key) if ch.isalnum() or ch in ("_", "-"))
    if not safe_key:
        safe_key = "voice"
    rel_path = f"{int(player_id)}/{int(job_id)}_{safe_key}.m4a"
    dst = media_root() / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp_dst = dst.with_suffix(".tmp.m4a")

    cmd = [
        ffmpeg,
        "-y",
        "-v",
        "error",
        "-i",
        str(src),
        "-vn",
        "-ac",
        "1",
        "-c:a",
        "aac",
        "-b:a",
        "64k",
        "-movflags",
        "+faststart",
        str(tmp_dst),
    ]
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            timeout=_FFMPEG_TIMEOUT,
            check=False,
        )
        if res.returncode != 0 or not tmp_dst.is_file() or tmp_dst.stat().st_size == 0:
            err = (res.stderr or b"").decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"ffmpeg transcode failed (code={res.returncode}): {err}")
        tmp_dst.replace(dst)
    except Exception:
        tmp_dst.unlink(missing_ok=True)
        raise

    pcm_duration, waveform = _extract_pcm_metrics(ffmpeg, dst)
    duration = int(duration_hint) if int(duration_hint or 0) > 0 else pcm_duration
    if duration <= 0:
        duration = 1

    return {
        "media_path": rel_path,
        "media_mime": "audio/mp4",
        "duration_sec": duration,
        "waveform": waveform,
    }
