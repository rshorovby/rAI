"""Оверлей скелета MediaPipe Pose на видео (фаза A)."""

import logging
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).resolve().parent / "models" / "pose_landmarker_lite.task"
# Лимиты под маленький VPS (~512 MB RAM): не жрём длинные ролики целиком.
MAX_WIDTH = 480
TARGET_FPS = 12.0
MAX_SECONDS = 12.0
MAX_OUTPUT_FRAMES = 144
MAX_WALL_SEC = 25.0
MIN_POSE_FRAMES = 1


@dataclass
class PoseOverlayResult:
    overlay_path: Optional[Path] = None
    frames_processed: int = 0
    frames_with_pose: int = 0
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return (
            self.overlay_path is not None
            and self.overlay_path.exists()
            and self.frames_with_pose >= MIN_POSE_FRAMES
            and not self.error
        )


def create_pose_overlay(video_path: Path) -> PoseOverlayResult:
    """Строит mp4 со скелетом. При любой ошибке возвращает result.error, не бросает."""
    try:
        return _create_pose_overlay(video_path)
    except Exception as exc:
        logger.exception("Pose overlay failed for %s", video_path)
        return PoseOverlayResult(error=str(exc)[:300])


def _create_pose_overlay(video_path: Path) -> PoseOverlayResult:
    import cv2
    import mediapipe as mp
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.core import base_options as base_options_module
    from mediapipe.tasks.python.vision import (
        PoseLandmarker,
        PoseLandmarkerOptions,
        RunningMode,
        drawing_styles,
        drawing_utils,
    )

    if not video_path.exists():
        return PoseOverlayResult(error="video not found")
    if not MODEL_PATH.exists():
        return PoseOverlayResult(error=f"model missing: {MODEL_PATH}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return PoseOverlayResult(error="cannot open video")

    src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if src_fps < 1.0:
        src_fps = 25.0
    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if src_w <= 0 or src_h <= 0:
        cap.release()
        return PoseOverlayResult(error="invalid video size")

    scale = 1.0
    if src_w > MAX_WIDTH:
        scale = MAX_WIDTH / float(src_w)
    out_w = int(src_w * scale)
    out_h = int(src_h * scale)
    out_w -= out_w % 2
    out_h -= out_h % 2
    if out_w < 2 or out_h < 2:
        cap.release()
        return PoseOverlayResult(error="scaled size too small")

    # Берём каждый N-й кадр исходника → целевой TARGET_FPS
    sample_every = max(1, int(round(src_fps / TARGET_FPS)))
    out_fps = min(TARGET_FPS, src_fps / float(sample_every))
    max_source_frames = int(src_fps * MAX_SECONDS) + sample_every

    fd, out_name = tempfile.mkstemp(suffix=".mp4", prefix="pose_")
    out_path = Path(out_name)
    try:
        os.close(fd)
    except OSError:
        pass

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, out_fps, (out_w, out_h))
    if not writer.isOpened():
        cap.release()
        out_path.unlink(missing_ok=True)
        return PoseOverlayResult(error="cannot open video writer")

    options = PoseLandmarkerOptions(
        base_options=base_options_module.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    frames_processed = 0
    frames_with_pose = 0
    source_index = 0
    started = time.monotonic()

    try:
        with PoseLandmarker.create_from_options(options) as landmarker:
            while frames_processed < MAX_OUTPUT_FRAMES:
                if time.monotonic() - started > MAX_WALL_SEC:
                    logger.warning(
                        "Pose overlay wall timeout after %s frames", frames_processed
                    )
                    break
                if source_index > max_source_frames:
                    break

                ok, frame = cap.read()
                if not ok:
                    break

                keep = source_index % sample_every == 0
                source_index += 1
                if not keep:
                    continue

                if scale != 1.0:
                    frame = cv2.resize(
                        frame, (out_w, out_h), interpolation=cv2.INTER_AREA
                    )

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp_ms = int(frames_processed * 1000.0 / out_fps)

                detection = landmarker.detect_for_video(mp_image, timestamp_ms)
                landmarks = None
                if detection.pose_landmarks:
                    landmarks = detection.pose_landmarks[0]
                    frames_with_pose += 1

                if landmarks is not None:
                    drawing_utils.draw_landmarks(
                        frame,
                        landmarks,
                        vision.PoseLandmarksConnections.POSE_LANDMARKS,
                        drawing_styles.get_default_pose_landmarks_style(),
                    )

                writer.write(frame)
                frames_processed += 1
    finally:
        cap.release()
        writer.release()

    if frames_processed == 0:
        out_path.unlink(missing_ok=True)
        return PoseOverlayResult(error="empty video", frames_processed=0)

    if frames_with_pose < MIN_POSE_FRAMES:
        out_path.unlink(missing_ok=True)
        return PoseOverlayResult(
            frames_processed=frames_processed,
            frames_with_pose=frames_with_pose,
            error="no pose detected",
        )

    logger.info(
        "Pose overlay ready: frames=%s with_pose=%s src_sampled_every=%s path=%s",
        frames_processed,
        frames_with_pose,
        sample_every,
        out_path,
    )
    return PoseOverlayResult(
        overlay_path=out_path,
        frames_processed=frames_processed,
        frames_with_pose=frames_with_pose,
    )


def cleanup_overlay(result: Optional[PoseOverlayResult]) -> None:
    if not result or not result.overlay_path:
        return
    try:
        result.overlay_path.unlink(missing_ok=True)
    except OSError:
        logger.warning("Не удалось удалить overlay %s", result.overlay_path)
