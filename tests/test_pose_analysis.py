from unittest.mock import MagicMock, patch

import pose_analysis
from pose_analysis import PoseOverlayResult, cleanup_overlay, create_pose_overlay


def test_pose_overlay_result_ok_requires_file(tmp_path):
    missing = PoseOverlayResult(
        overlay_path=tmp_path / "none.mp4",
        frames_processed=10,
        frames_with_pose=5,
    )
    assert missing.ok is False

    path = tmp_path / "ok.mp4"
    path.write_bytes(b"x")
    ok = PoseOverlayResult(
        overlay_path=path,
        frames_processed=10,
        frames_with_pose=5,
    )
    assert ok.ok is True

    failed = PoseOverlayResult(
        overlay_path=path,
        frames_processed=10,
        frames_with_pose=5,
        error="boom",
    )
    assert failed.ok is False


def test_create_pose_overlay_missing_video(tmp_path):
    result = create_pose_overlay(tmp_path / "missing.mp4")
    assert result.ok is False
    assert result.error


def test_create_pose_overlay_missing_model(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"not-a-real-video")
    with patch.object(pose_analysis, "MODEL_PATH", tmp_path / "no.task"):
        result = create_pose_overlay(video)
    assert result.ok is False
    assert "model missing" in (result.error or "")


def test_create_pose_overlay_cannot_open_video(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    (tmp_path / "model.task").write_bytes(b"m")
    fake_cap = MagicMock()
    fake_cap.isOpened.return_value = False
    with patch.object(pose_analysis, "MODEL_PATH", tmp_path / "model.task"):
        with patch("cv2.VideoCapture", return_value=fake_cap):
            result = create_pose_overlay(video)
    assert result.ok is False
    assert result.error == "cannot open video"


def test_cleanup_overlay(tmp_path):
    path = tmp_path / "overlay.mp4"
    path.write_bytes(b"x")
    result = PoseOverlayResult(overlay_path=path, frames_with_pose=1)
    cleanup_overlay(result)
    assert not path.exists()
    cleanup_overlay(None)
    cleanup_overlay(PoseOverlayResult())
