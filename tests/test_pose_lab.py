import pytest

np = pytest.importorskip("numpy")

import pose_lab  # noqa: E402
from eval_pose_lab import load_labels, match_contacts  # noqa: E402


def test_find_peaks_threshold_and_gap():
    times = np.arange(0, 3, 0.1)
    values = np.zeros_like(times)
    values[5] = 10
    values[7] = 8
    values[20] = 9
    values[25] = 2
    assert pose_lab.find_peaks(times, values, 5, 0.8) == [5, 20]


def test_audio_onsets_finds_clicks():
    rate = pose_lab.AUDIO_RATE
    rng = np.random.default_rng(0)
    samples = rng.normal(0, 0.001, rate * 3).astype(np.float32)
    for second in (1.0, 2.5):
        start = int(second * rate)
        samples[start : start + 80] += rng.normal(0, 0.5, 80).astype(np.float32)
    found = [t for t, _ in pose_lab.audio_onsets(samples, rate)]
    assert len(found) == 2
    assert found[0] == pytest.approx(1.0, abs=0.02)
    assert found[1] == pytest.approx(2.5, abs=0.02)


def test_fuse_contacts_prefers_audio_near_peak():
    contacts = pose_lab.fuse_contacts([1.0, 3.0], [(0.9, 0.5), (0.95, 1.0), (2.0, 1.0)])
    assert contacts[0]["t"] == 0.95
    assert contacts[0]["source"] == "audio"
    assert contacts[1] == {"t": 3.0, "source": "wrist", "peak_t": 3.0}


def test_fix_side_swaps_restores_labels():
    frames = np.zeros((3, 33, 3))
    frames[:, :, 2] = 1.0
    frames[:, 15, :2] = (100, 100)
    frames[:, 16, :2] = (300, 100)
    frames[1, 15, :2], frames[1, 16, :2] = (300, 100), (100, 100)
    fixed = pose_lab.fix_side_swaps(frames)
    assert tuple(fixed[1, 15, :2]) == (100, 100)
    assert tuple(fixed[1, 16, :2]) == (300, 100)


def test_load_labels_timeline_frames(tmp_path):
    path = tmp_path / "labels.json"
    path.write_text('{"_timeline_fps": 30, "a.mp4": [5.04, 3.0, 9.17]}')
    assert load_labels(path) == {"a.mp4": [5.133, 3.0, 9.567]}


def test_load_labels_plain_seconds(tmp_path):
    path = tmp_path / "labels.json"
    path.write_text('{"a.mp4": [5.04]}')
    assert load_labels(path) == {"a.mp4": [5.04]}


def test_match_contacts():
    result = match_contacts([1.02, 3.0, 5.5], [1.0, 3.1])
    assert result["matched"] == 2
    assert result["found"] == 3
    assert result["mean_error_sec"] == pytest.approx(0.06)


def test_joint_angle_right_and_straight():
    assert pose_lab.joint_angle((0, 1), (0, 0), (1, 0)) == pytest.approx(90.0)
    assert pose_lab.joint_angle((0, 0), (1, 0), (2, 0)) == pytest.approx(180.0)
    assert pose_lab.joint_angle((np.nan, 0), (0, 0), (1, 0)) is None


def test_measure_contacts_uses_declared_hand():
    times = np.array([0.0, 1.0, 1.5, 2.0])
    points = np.full((len(times), 33, 3), np.nan)
    for index in range(len(times)):
        _mark(points, index, pose_lab.NOSE, 150, 250)
        _arm(points, index, "right", elbow=(100, 200), wrist=(200, 200))
        _arm(points, index, "left", elbow=(0, 200), wrist=(0, 300))
        _leg(points, index, "left", knee=(40, 400), ankle=(40, 500))
        _leg(points, index, "right", knee=(200, 420), ankle=(160, 500))
    _arm(points, 2, "left", elbow=(0, 200), wrist=(0, -100))
    _leg(points, 2, "right", knee=(200, 470), ankle=(80, 500))
    _arm(points, 0, "right", elbow=(100, 200), wrist=(100, 300))
    track = pose_lab.PoseTrack(times, points, 640, 480)
    right = pose_lab.measure_contacts(track, [2.0], "right", 100.0, "serve")
    left = pose_lab.measure_contacts(track, [2.0], "left", 100.0, "serve")
    assert right["contacts"][0]["elbow"] == pytest.approx(90.0, abs=0.1)
    assert right["contacts"][0]["contact_above_head"] == pytest.approx(0.5, abs=0.01)
    assert right["contacts"][0]["toss_above_head"] == pytest.approx(3.5, abs=0.01)
    assert left["contacts"][0]["elbow"] == pytest.approx(180.0, abs=0.1)
    assert left["contacts"][0]["contact_above_head"] == pytest.approx(-0.5, abs=0.01)
    assert right["contacts"][0]["knee_load"] < right["contacts"][0]["knee_right"]
    spread = pose_lab.measure_contacts(track, [0.0, 2.0], "right", 100.0, "")
    assert spread["spread"]["elbow"] == pytest.approx(90.0)
    hidden = points.copy()
    hidden[3, pose_lab.WRIST["right"], 2] = 0.1
    quiet = pose_lab.measure_contacts(
        pose_lab.PoseTrack(times, hidden, 640, 480), [2.0], "right", 100.0, ""
    )
    assert quiet["contacts"][0]["elbow"] is None
    assert pose_lab.measure_contacts(track, [2.0], "both", 100.0)["contacts"] == []


def _mark(points, index, landmark, x, y):
    points[index, landmark] = (x, y, 1.0)


def _arm(points, index, side, elbow, wrist):
    shoulder = (100, 100) if side == "right" else (0, 100)
    _mark(points, index, pose_lab.SHOULDER[side], *shoulder)
    _mark(points, index, pose_lab.ELBOW[side], *elbow)
    _mark(points, index, pose_lab.WRIST[side], *wrist)


def _leg(points, index, side, knee, ankle):
    hip = (40, 300) if side == "left" else (200, 300)
    _mark(points, index, pose_lab.HIP[side], *hip)
    _mark(points, index, pose_lab.KNEE[side], *knee)
    _mark(points, index, pose_lab.ANKLE[side], *ankle)
