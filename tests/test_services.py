from pathlib import Path
from unittest.mock import patch

import services
import storage
from analyzer import AnalysisResult
from pricing import Usage


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "t.db")


def test_progress_scores_via_services(tmp_path):
    with _tmp_db(tmp_path):
        storage.save_session(
            1,
            "## Краткое резюме\na\n",
            scores={"footwork": 5, "contact": 4},
            focus="x",
            stroke="forehand",
        )
        rows = services.progress_scores(1, 90)
        assert len(rows) == 1
        assert rows[0]["scores"]["footwork"] == 5


def test_report_payload_parses_scores():
    text = (
        "## Краткое резюме\nok\n\n"
        "## Следующее видео\nfilm\n\n"
        '```json\n{"scores": {"footwork": 6, "contact": 7}, "findings": [{"problem": "P", "recommendation": "R"}]}\n```\n'
    )
    payload = services.report_payload(text)
    assert payload["scores"]["footwork"] == 6
    assert payload["markdown"]
    assert payload["summary"] == "ok"
    assert payload["next_video"] == "film"
    assert payload["findings"][0]["recommendation"] == "R"


def test_prepare_and_enqueue_review(tmp_path):
    with _tmp_db(tmp_path):
        result = AnalysisResult(
            text="## Краткое резюме\nhello\n",
            usage=Usage(),
            model="m",
        )
        prepared = services.prepare_report(result, {"stroke": "serve"})
        assert prepared.stroke == "serve"
        services.save_analysis_session(3, prepared, "ru")
        job_id = services.enqueue_review(
            3,
            prepared,
            language_code="ru",
            video_file_id="fid",
            video_mime="video/mp4",
        )
        job = storage.get_review_job(job_id)
        assert job["user_id"] == 3
        assert job["stroke"] == "serve"
        assert job["video_file_id"] == "fid"


def test_get_plan_delegates(tmp_path):
    with _tmp_db(tmp_path):
        plan = services.get_plan(1)
        assert plan.analyses_left >= 0
