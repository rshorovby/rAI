"""Поза по кадрам, звук удара и поиск контактов. В бою вызывает pose_runtime.

Зависимости — requirements-lab.txt. Модели MediaPipe лежат в data/models.
"""

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent / "data" / "models"

NOSE = 0
SHOULDER = {"left": 11, "right": 12}
ELBOW = {"left": 13, "right": 14}
WRIST = {"left": 15, "right": 16}
HIP = {"left": 23, "right": 24}
ANKLE = {"left": 27, "right": 28}

MIN_VISIBILITY = 0.5
SMOOTH_SEC = 0.05
MEDIAN_FRAMES = 5
# Скорость запястья в длинах торса в секунду. Шаг и подготовка дают 1–4,
# замах к мячу заметно больше.
MIN_SWING_SPEED = 6.0
SWING_SHARE_OF_MAX = 0.35
WRIST_ONLY_SHARE = 0.6
MIN_GAP_SEC = 0.8
# Первые кадры трекер «нащупывает» позу, точки прыгают.
WARMUP_SEC = 0.15
AUDIO_RATE = 16000
AUDIO_HOP = 160
ONSET_MAD_K = 6.0
# log10 скачка энергии: 1.0 — щелчок в 10 раз громче фона перед ним.
ONSET_MIN_FLUX = 1.0
ONSET_MIN_GAP_SEC = 0.3
# Звук удара ищем у пика запястья: контакт чуть раньше пика скорости кисти.
AUDIO_BEFORE_PEAK_SEC = 0.2
AUDIO_AFTER_PEAK_SEC = 0.2
SERVE_PEAK_WINDOW_SEC = 0.15
SERVE_GROUP_SEC = 2.0
_LEFT_RIGHT = [(i, i + 1) for i in range(11, 33, 2)] + [(1, 4), (2, 5), (3, 6)]


@dataclass
class PoseTrack:
    times: np.ndarray
    points: np.ndarray
    width: int
    height: int

    @property
    def detected_share(self) -> float:
        if not len(self.times):
            return 0.0
        return float(np.mean(~np.isnan(self.points[:, NOSE, 0])))


def extract_pose(
    path: Path, model: str = "full", max_side: int = 720
) -> Optional[PoseTrack]:
    """Точки 33 суставов по каждому кадру в пикселях уменьшенного кадра. Нет позы — NaN."""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return None
    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path=str(MODELS_DIR / f"pose_landmarker_{model}.task")
        ),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
    )
    times = []
    frames = []
    width = height = 0
    last_ms = -1
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            t_ms = max(0.0, cap.get(cv2.CAP_PROP_POS_MSEC))
            stamp = max(last_ms + 1, int(round(t_ms)))
            last_ms = stamp
            frame = _resize(cv2, frame, max_side)
            height, width = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect_for_video(image, stamp)
            row = np.full((33, 3), np.nan)
            if result.pose_landmarks:
                for index, mark in enumerate(result.pose_landmarks[0]):
                    row[index] = (mark.x * width, mark.y * height, mark.visibility)
            times.append(stamp / 1000.0)
            frames.append(row)
    cap.release()
    if not frames:
        return None
    points = fix_side_swaps(np.stack(frames))
    return PoseTrack(np.array(times), points, width, height)


def fix_side_swaps(points: np.ndarray) -> np.ndarray:
    """MediaPipe путает лево и право, особенно со спины. Метки сторон — как ближе к прошлому кадру."""
    out = points.copy()
    left = [a for a, _ in _LEFT_RIGHT]
    right = [b for _, b in _LEFT_RIGHT]
    previous = None
    for i in range(len(out)):
        if np.isnan(out[i, 0, 0]):
            continue
        if previous is not None:
            current = out[i, :, :2]
            swapped = current.copy()
            swapped[left], swapped[right] = current[right], current[left]
            keep = np.nansum(np.linalg.norm(current - previous, axis=1))
            flip = np.nansum(np.linalg.norm(swapped - previous, axis=1))
            if flip < keep:
                out[i, left], out[i, right] = out[i, right].copy(), out[i, left].copy()
        previous = out[i, :, :2]
    return out


def save_track(track: PoseTrack, dest: Path) -> None:
    np.savez_compressed(
        dest,
        times=track.times,
        points=track.points,
        size=np.array([track.width, track.height]),
    )


def load_track(source: Path) -> Optional[PoseTrack]:
    if not source.is_file():
        return None
    data = np.load(source)
    width, height = (int(v) for v in data["size"])
    return PoseTrack(data["times"], data["points"], width, height)


def grab_frames(path: Path, times: list, max_side: int = 720) -> list:
    """Кадры, ближайшие к моментам times, одним последовательным проходом."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    wanted = sorted((t, i) for i, t in enumerate(times))
    best: dict = {}
    while wanted:
        ok, frame = cap.read()
        if not ok:
            break
        t = max(0.0, cap.get(cv2.CAP_PROP_POS_MSEC)) / 1000.0
        for target, index in wanted:
            prev = best.get(index)
            if prev is None or abs(t - target) < abs(prev[0] - target):
                best[index] = (t, _resize(cv2, frame, max_side))
        wanted = [(target, i) for target, i in wanted if t <= target + 0.5]
    cap.release()
    return [best.get(i, (None, None)) for i in range(len(times))]


def body_scale(track: PoseTrack) -> Optional[float]:
    """Медианная длина торса (середина плеч — середина таза) в пикселях."""
    shoulders = _mid(track.points, SHOULDER)
    hips = _mid(track.points, HIP)
    lengths = np.linalg.norm(shoulders - hips, axis=1)
    if np.all(np.isnan(lengths)):
        return None
    return float(np.nanmedian(lengths))


def wrist_speed(track: PoseTrack, side: str, scale: float) -> np.ndarray:
    """Скорость запястья в длинах торса в секунду, на каждый кадр."""
    xy = _interpolate(track.times, _visible(track.points[:, WRIST[side]]))
    xy = _smooth(track.times, xy, SMOOTH_SEC)
    speed = np.zeros(len(track.times))
    if len(track.times) < 2:
        return speed
    step = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    dt = np.maximum(np.diff(track.times), 1e-3)
    speed[1:] = step / dt / scale
    speed[track.times < track.times[0] + WARMUP_SEC] = 0.0
    return np.nan_to_num(speed)


def find_peaks(
    times: np.ndarray, values: np.ndarray, min_height: float, min_gap: float
) -> list:
    """Локальные максимумы не ниже min_height, сильнейшие первыми, не ближе min_gap."""
    candidates = [
        i
        for i in range(1, len(values) - 1)
        if values[i] >= min_height
        and values[i] >= values[i - 1]
        and values[i] > values[i + 1]
    ]
    candidates.sort(key=lambda i: values[i], reverse=True)
    picked: list = []
    for i in candidates:
        if all(abs(times[i] - times[j]) >= min_gap for j in picked):
            picked.append(i)
    return sorted(picked)


def swing_peaks(times: np.ndarray, speed: np.ndarray) -> list:
    if not len(speed):
        return []
    threshold = max(MIN_SWING_SPEED, SWING_SHARE_OF_MAX * float(speed.max()))
    return find_peaks(times, speed, threshold, MIN_GAP_SEC)


def load_audio(path: Path) -> Optional[np.ndarray]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    try:
        result = subprocess.run(
            [
                ffmpeg,
                "-v",
                "error",
                "-i",
                str(path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(AUDIO_RATE),
                "-f",
                "s16le",
                "-",
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    return np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def audio_onsets(samples: np.ndarray, rate: int = AUDIO_RATE) -> list:
    """Резкие щелчки: скачок энергии производной сигнала. [(t, сила 0..1)]."""
    if samples is None or len(samples) < AUDIO_HOP * 10:
        return []
    clicks = np.diff(samples)
    frames = len(clicks) // AUDIO_HOP
    energy = (clicks[: frames * AUDIO_HOP].reshape(frames, AUDIO_HOP) ** 2).sum(axis=1)
    log_energy = np.log10(energy + 1e-10)
    flux = np.zeros(frames)
    for i in range(5, frames):
        flux[i] = max(0.0, log_energy[i] - log_energy[i - 5 : i].mean())
    median = float(np.median(flux))
    mad = float(np.median(np.abs(flux - median))) or 1e-6
    times = (np.arange(frames) + 0.5) * AUDIO_HOP / rate
    threshold = max(ONSET_MIN_FLUX, median + ONSET_MAD_K * mad)
    peaks = find_peaks(times, flux, threshold, ONSET_MIN_GAP_SEC)
    if not peaks:
        return []
    top = max(flux[i] for i in peaks)
    return [(float(times[i]), float(flux[i] / top)) for i in peaks]


def fuse_contacts(peak_times: list, onsets: list) -> list:
    """Контакт = щелчок рядом с пиком кисти, иначе сам пик. [{"t", "source", "peak_t"}]."""
    contacts = []
    for peak_t in peak_times:
        near = [
            (strength, t)
            for t, strength in onsets
            if peak_t - AUDIO_BEFORE_PEAK_SEC <= t <= peak_t + AUDIO_AFTER_PEAK_SEC
        ]
        if near:
            _, t = max(near)
            contacts.append({"t": round(t, 3), "source": "audio", "peak_t": peak_t})
        else:
            contacts.append(
                {"t": round(peak_t, 3), "source": "wrist", "peak_t": peak_t}
            )
    return contacts


def estimate_view(track: PoseTrack, scale: float) -> str:
    """Ракурс по ширине плеч к торсу и по тому, какое плечо левее в кадре."""
    left = _visible(track.points[:, SHOULDER["left"]])
    right = _visible(track.points[:, SHOULDER["right"]])
    width = np.abs(left[:, 0] - right[:, 0])
    if np.all(np.isnan(width)):
        return "unknown"
    ratio = float(np.nanmedian(width)) / scale
    if ratio < 0.35:
        return "side"
    facing = float(np.nanmedian(left[:, 0] - right[:, 0]))
    return "front" if facing > 0 else "back"


def serve_details(
    track: PoseTrack, contact_t: float, dominant: str, scale: float
) -> dict:
    """Подброс — верхняя точка кисти подброса за 2,5 с до контакта. Высоты — в торсах."""
    toss_side = "left" if dominant == "right" else "right"
    window = (track.times >= contact_t - 2.5) & (track.times <= contact_t - 0.2)
    toss_y = _visible(track.points[:, WRIST[toss_side]])[:, 1]
    details: dict = {
        "toss_t": None,
        "toss_above_head": None,
        "contact_above_head": None,
    }
    if np.any(window) and not np.all(np.isnan(toss_y[window])):
        idx = np.flatnonzero(window)[int(np.nanargmin(toss_y[window]))]
        details["toss_t"] = round(float(track.times[idx]), 3)
        details["toss_above_head"] = _above_head(track, idx, toss_side, scale)
    at = int(np.argmin(np.abs(track.times - contact_t)))
    details["contact_above_head"] = _above_head(track, at, dominant, scale)
    return details


def serve_hits(track: PoseTrack, peaks: dict, speeds: dict, scale: float) -> tuple:
    """Подброс тоже даёт пик над головой, но раньше удара. В группе пиков — последний."""
    candidates = sorted(
        (float(track.times[i]), side, i)
        for side, found in peaks.items()
        for i in found
        if _peak_above_head(track, i, side, scale) > 0
    )
    picks = []
    group_start = None
    for t, side, i in candidates:
        if group_start is None or t - group_start > SERVE_GROUP_SEC:
            group_start = t
            picks.append((side, i))
        else:
            picks[-1] = (side, i)
    if not picks:
        return "right", []
    sides = [side for side, _ in picks]
    dominant = max(
        ("left", "right"),
        key=lambda s: (
            sides.count(s),
            max((speeds[s][i] for side, i in picks if side == s), default=0),
        ),
    )
    return dominant, [i for side, i in picks if side == dominant]


def analyze(
    path: Path,
    model: str = "full",
    stroke: str = "",
    track: Optional[PoseTrack] = None,
) -> dict:
    """track можно передать готовым: поза — самое долгое, её стоит кэшировать."""
    if track is None:
        track = extract_pose(path, model=model)
    report: dict = {"frames": 0, "detected_share": 0.0, "contacts": []}
    if track is None:
        return report
    report["frames"] = len(track.times)
    report["detected_share"] = round(track.detected_share, 3)
    scale = body_scale(track)
    if not scale:
        return report
    speeds = {side: wrist_speed(track, side, scale) for side in ("left", "right")}
    peaks = {side: swing_peaks(track.times, speeds[side]) for side in speeds}
    onsets = audio_onsets(load_audio(path))
    if stroke == "serve":
        dominant, chosen = serve_hits(track, peaks, speeds, scale)
        peaks = {dominant: chosen}
    by_side = {
        side: _side_contacts(track, found, speeds[side], onsets)
        for side, found in peaks.items()
    }
    dominant = max(
        by_side,
        key=lambda side: (
            sum(c["source"] == "audio" for c in by_side[side]),
            max((c["wrist_speed"] for c in by_side[side]), default=0),
        ),
    )
    speed = speeds[dominant]
    contacts = by_side[dominant]
    if stroke == "serve":
        for contact in contacts:
            contact.update(serve_details(track, contact["t"], dominant, scale))
    report.update(
        dominant=dominant,
        view=estimate_view(track, scale),
        torso_px=round(scale, 1),
        contacts=contacts,
        audio_onsets=[round(t, 3) for t, _ in onsets],
        track=track,
        speed=speed,
    )
    return report


def _side_contacts(
    track: PoseTrack, found: list, speed: np.ndarray, onsets: list
) -> list:
    """Пик без щелчка засчитываем, только если он близок к самому быстрому замаху."""
    contacts = fuse_contacts([float(track.times[i]) for i in found], onsets)
    top = float(speed.max()) if len(speed) else 0.0
    kept = []
    for contact, i in zip(contacts, found):
        contact["wrist_speed"] = round(float(speed[i]), 1)
        if contact["source"] == "audio" or speed[i] >= WRIST_ONLY_SHARE * top:
            kept.append(contact)
    return kept


def _peak_above_head(track: PoseTrack, index: int, side: str, scale: float) -> float:
    """Высшая точка кисти над носом в окне вокруг пика: на пике кисть уже идёт вниз."""
    near = np.flatnonzero(
        np.abs(track.times - track.times[index]) <= SERVE_PEAK_WINDOW_SEC
    )
    heights = [_above_head(track, i, side, scale) for i in near]
    return max((h for h in heights if h is not None), default=-1.0)


def _above_head(track: PoseTrack, index: int, side: str, scale: float):
    wrist_y = track.points[index, WRIST[side], 1]
    nose_y = track.points[index, NOSE, 1]
    if np.isnan(wrist_y) or np.isnan(nose_y):
        return None
    return round(float(nose_y - wrist_y) / scale, 2)


def _resize(cv2, frame, max_side: int):
    h, w = frame.shape[:2]
    factor = max_side / max(h, w)
    if factor >= 1:
        return frame
    return cv2.resize(frame, (int(w * factor), int(h * factor)))


def _visible(points: np.ndarray) -> np.ndarray:
    xy = points[:, :2].copy()
    xy[~(points[:, 2] >= MIN_VISIBILITY)] = np.nan
    return xy


def _mid(points: np.ndarray, pair: dict) -> np.ndarray:
    return (_visible(points[:, pair["left"]]) + _visible(points[:, pair["right"]])) / 2


def _interpolate(times: np.ndarray, xy: np.ndarray) -> np.ndarray:
    out = xy.copy()
    for axis in range(xy.shape[1]):
        column = xy[:, axis]
        known = ~np.isnan(column)
        if known.sum() >= 2:
            out[:, axis] = np.interp(times, times[known], column[known])
    return out


def _smooth(times: np.ndarray, xy: np.ndarray, window_sec: float) -> np.ndarray:
    """Медиана по MEDIAN_FRAMES убирает одиночные прыжки точки, потом среднее по окну."""
    if len(times) < MEDIAN_FRAMES:
        return xy
    step = float(np.median(np.diff(times))) or 1 / 30
    size = max(1, int(round(window_sec / step)))
    half = MEDIAN_FRAMES // 2
    out = xy.copy()
    for axis in range(xy.shape[1]):
        column = xy[:, axis]
        if np.any(np.isnan(column)):
            continue
        padded = np.pad(column, half, mode="edge")
        windows = np.lib.stride_tricks.sliding_window_view(padded, MEDIAN_FRAMES)
        column = np.median(windows, axis=1)
        if size > 1:
            left, right = size // 2, size - 1 - size // 2
            padded = np.pad(column, (left, right), mode="edge")
            column = np.convolve(padded, np.ones(size) / size, mode="valid")
        out[:, axis] = column
    return out
