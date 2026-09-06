from pathlib import Path
from unittest.mock import patch

import services
import storage
from analyzer import AnalysisResult
from pricing import Usage


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "coverage.db")


def _prepared(stroke, scores):
    result = AnalysisResult(text="## Краткое резюме\nok\n", usage=Usage(), model="m")
    prepared = services.prepare_report(result, {"stroke": stroke})
    prepared.scores = scores
    return prepared


def test_apply_coverage_accent_only_and_thresholds(tmp_path):
    with _tmp_db(tmp_path):
        prepared = _prepared(
            "forehand",
            {
                "preparation": 5,
                "contact": 8,
                "follow_through": 6,
                "footwork": 9,
            },
        )
        job_id = services.enqueue_review(
            1,
            prepared,
            language_code="ru",
            video_file_id="a",
            video_mime="video/mp4",
            look="technique",
        )
        rows = storage.list_coverage_for_job(job_id)
        slots = {r["slot"] for r in rows}
        assert slots == {"preparation", "contact", "footwork"}
        assert all(r["segment"] == "forehand" for r in rows)
        assert all(r["status"] == "pending" for r in rows)


def test_dossier_weights_and_goals_locked(tmp_path):
    with _tmp_db(tmp_path):
        prepared = _prepared(
            "forehand",
            {
                "preparation": 8,
                "contact": 8,
                "follow_through": 8,
                "footwork": 8,
            },
        )
        services.enqueue_review(
            2,
            prepared,
            language_code="ru",
            video_file_id="b",
            video_mime="video/mp4",
        )
        dossier = services.dossier_payload(2)
        fh = next(s for s in dossier["segments"] if s["id"] == "forehand")
        assert fh["coverage_pending"] == 100.0
        assert fh["coverage_committed"] == 0.0
        assert dossier["player"]["coverage_pending"] == 25.0
        assert dossier["player"]["coverage_committed"] == 0.0
        assert dossier["player"]["goals_unlocked"] is False
        serve = next(s for s in dossier["segments"] if s["id"] == "serve")
        assert serve["next_to_film"] == list(services.COVERAGE_SLOTS)


def test_empty_stroke_writes_nothing(tmp_path):
    with _tmp_db(tmp_path):
        prepared = _prepared("", {"contact": 9})
        job_id = services.enqueue_review(
            3,
            prepared,
            language_code="ru",
            video_file_id="c",
            video_mime="video/mp4",
        )
        assert storage.list_coverage_for_job(job_id) == []
