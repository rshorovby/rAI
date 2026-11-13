"""Проверка ролика до разбора: факты о файле и советы к следующей съёмке."""

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from i18n import t

logger = logging.getLogger(__name__)

TIMEOUT_SEC = 30
MIN_FPS = 24.0
MIN_SHORT_SIDE = 480
MIN_BRIGHTNESS = 45.0
BRIGHTNESS_SAMPLE_FPS = 2

_YAVG_RE = re.compile(r"lavfi\.signalstats\.YAVG=([\d.]+)")


@dataclass(frozen=True)
class Preflight:
    width: int
    height: int
    fps: Optional[float]
    duration_sec: Optional[float]
    brightness: Optional[float] = None

    @property
    def short_side(self) -> int:
        return min(self.width, self.height)

    def tips(self) -> list:
        """Ключи i18n советов. Порядок — от самого заметного для разбора."""
        keys = []
        if self.fps is not None and self.fps < MIN_FPS:
            keys.append("pf_tip_low_fps")
        if 0 < self.short_side < MIN_SHORT_SIDE:
            keys.append("pf_tip_low_res")
        if self.brightness is not None and self.brightness < MIN_BRIGHTNESS:
            keys.append("pf_tip_dark")
        return keys


def check_video(path: Path) -> Optional[Preflight]:
    """None, если ffprobe нет или файл не читается: разбор идёт без проверки."""
    stream = _probe(Path(path))
    if stream is None:
        return None
    width = int(stream.get("width") or 0)
    height = int(stream.get("height") or 0)
    if not width or not height:
        return None
    return Preflight(
        width=width,
        height=height,
        fps=_parse_rate(stream.get("avg_frame_rate"))
        or _parse_rate(stream.get("r_frame_rate")),
        duration_sec=_parse_float(stream.get("duration")),
        brightness=_mean_brightness(Path(path)),
    )


def progress_text(lang: str, preflight: Optional[Preflight], watching: bool) -> str:
    """Статус для игрока: факты о ролике, советы к съёмке и, пока идёт разбор, «смотрю»."""
    lines = []
    if preflight is not None:
        facts = []
        if preflight.duration_sec:
            facts.append(t(lang, "pf_unit_sec", n=round(preflight.duration_sec)))
        facts.append(f"{preflight.short_side}p")
        if preflight.fps:
            facts.append(t(lang, "pf_unit_fps", n=round(preflight.fps)))
        lines.append(t(lang, "pf_video", facts=" · ".join(facts)))
        tips = preflight.tips()
        if tips:
            lines.append("")
            lines.append(t(lang, "pf_tips_header"))
            lines.extend(
                t(
                    lang,
                    key,
                    fps=round(preflight.fps or 0),
                    resolution=f"{preflight.short_side}p",
                )
                for key in tips
            )
    if watching:
        if lines:
            lines.append("")
        lines.append(t(lang, "pf_watching"))
    return "\n".join(lines)


def _run(cmd: list) -> Optional[subprocess.CompletedProcess]:
    nice = shutil.which("nice")
    if nice:
        cmd = [nice, "-n", "10", *cmd]
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_SEC, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("preflight: %s не отработал: %s", cmd[0], exc)
        return None


def _probe(path: Path) -> Optional[dict]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not path.is_file():
        return None
    result = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,avg_frame_rate,r_frame_rate,duration"
            ":format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    if result is None or result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None
    streams = data.get("streams") or []
    if not streams:
        return None
    stream = dict(streams[0])
    if not stream.get("duration"):
        stream["duration"] = (data.get("format") or {}).get("duration")
    return stream


def _mean_brightness(path: Path) -> Optional[float]:
    """Средняя яркость 0–255 по двум кадрам в секунду. format=gray — и для 10-бит HDR."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    result = _run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(path),
            "-an",
            "-vf",
            f"fps={BRIGHTNESS_SAMPLE_FPS},scale=160:-2,format=gray,signalstats,"
            "metadata=print:key=lavfi.signalstats.YAVG:file=-",
            "-f",
            "null",
            "-",
        ]
    )
    if result is None or result.returncode != 0:
        return None
    values = [float(v) for v in _YAVG_RE.findall(result.stdout or "")]
    if not values:
        return None
    return sum(values) / len(values)


def _parse_rate(raw) -> Optional[float]:
    text = str(raw or "")
    if "/" in text:
        num, den = text.split("/", 1)
        try:
            den_value = float(den)
            return float(num) / den_value if den_value else None
        except ValueError:
            return None
    value = _parse_float(text)
    return value or None


def _parse_float(raw) -> Optional[float]:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
