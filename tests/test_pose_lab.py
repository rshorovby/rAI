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
