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


def _publish(job_id, status="ai_sent"):
    storage.mark_review_sent(job_id, status=status, final_text="ok")


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
        job_id = services.enqueue_review(
            2,
            prepared,
            language_code="ru",
            video_file_id="b",
            video_mime="video/mp4",
        )
        _publish(job_id)
        dossier = services.dossier_payload(2)
        fh = next(s for s in dossier["segments"] if s["id"] == "forehand")
        assert fh["job_count_pending"] == 1
        assert fh["familiarity_pending"] == 20.0
        assert fh["coverage_pending"] == 20.0
        assert fh["progress_mean_pending"] == 8.0
        assert fh["progress_pending"] == 80.0
        assert fh["coverage_committed"] == 0.0
        assert dossier["player"]["familiarity_pending"] == 5.0
        assert dossier["player"]["coverage_pending"] == 5.0
        assert dossier["player"]["progress_mean_pending"] == 2.0
        assert dossier["player"]["progress_pending"] == 20.0
        assert dossier["player"]["coverage_committed"] == 0.0
        assert dossier["player"]["goals_unlocked"] is False
        serve = next(s for s in dossier["segments"] if s["id"] == "serve")
        assert serve["next_to_film"] == list(services.COVERAGE_SLOTS)
        assert serve["job_count_pending"] == 0


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


def _detect_prepared(intake, scores, primary, detected):
    import json

    payload = {
        "scores": scores,
        "primary_segment": primary,
        "detected_segments": detected,
        "focus": "x",
    }
    text = "## Краткое резюме\nok\n\n```json\n" + json.dumps(payload) + "\n```\n"
    result = AnalysisResult(text=text, usage=Usage(), model="m")
    ctx = {
        "stroke": services.compatibility_stroke(intake),
        "strokes": list(intake),
    }
    return services.prepare_report(result, ctx)


def test_general_intake_writes_primary_and_one_secondary(tmp_path):
    with _tmp_db(tmp_path):
        prepared = _detect_prepared(
            [],
            {
                "preparation": 8,
                "contact": 8,
                "follow_through": 8,
                "footwork": 8,
            },
            "forehand",
            ["forehand", "backhand"],
        )
        assert prepared.stroke == "forehand"
        job_id = services.enqueue_review(
            4,
            prepared,
            language_code="ru",
            video_file_id="d",
            video_mime="video/mp4",
        )
        rows = storage.list_coverage_for_job(job_id)
        by_seg = {}
        for row in rows:
            by_seg.setdefault(row["segment"], set()).add(row["slot"])
        assert by_seg["forehand"] == set(services.COVERAGE_SLOTS)
        assert len(by_seg["backhand"]) == 1
        payload = services.job_coverage_payload(job_id)
        assert payload["accent_mismatch"] is False
        assert "forehand" in payload["detected_segments"]


def test_mismatch_writes_ai_primary_not_selected(tmp_path):
    with _tmp_db(tmp_path):
        prepared = _detect_prepared(
            ["forehand"],
            {"contact": 9, "preparation": 8},
            "backhand",
            ["backhand"],
        )
        assert prepared.accent_mismatch is True
        assert prepared.stroke == "backhand"
        job_id = services.enqueue_review(
            5,
            prepared,
            language_code="ru",
            video_file_id="e",
            video_mime="video/mp4",
        )
        rows = storage.list_coverage_for_job(job_id)
        assert {r["segment"] for r in rows} == {"backhand"}
        assert services.job_coverage_payload(job_id)["accent_mismatch"] is True


def test_multi_intake_counts_first_selected(tmp_path):
    with _tmp_db(tmp_path):
        prepared = _detect_prepared(
            ["backhand", "forehand"],
            {
                "preparation": 8,
                "contact": 8,
                "follow_through": 8,
                "footwork": 8,
            },
            "forehand",
            ["forehand", "backhand"],
        )
        assert prepared.stroke == "backhand"
        job_id = services.enqueue_review(
            6,
            prepared,
            language_code="ru",
            video_file_id="f",
            video_mime="video/mp4",
        )
        rows = storage.list_coverage_for_job(job_id)
        by_seg = {}
        for row in rows:
            by_seg.setdefault(row["segment"], set()).add(row["slot"])
        assert by_seg["backhand"] == set(services.COVERAGE_SLOTS)
        assert len(by_seg.get("forehand", ())) == 1


def test_queued_job_does_not_count_until_published(tmp_path):
    with _tmp_db(tmp_path):
        prepared = _prepared("forehand", {"contact": 8, "footwork": 8})
        services.enqueue_review(
            8,
            prepared,
            language_code="ru",
            video_file_id="q",
            video_mime="video/mp4",
        )
        dossier = services.dossier_payload(8)
        fh = next(s for s in dossier["segments"] if s["id"] == "forehand")
        assert fh["job_count_pending"] == 0
        assert fh["familiarity_pending"] == 0.0


def test_voided_job_excluded_from_scales(tmp_path):
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
        job_id = services.enqueue_review(
            9,
            prepared,
            language_code="ru",
            video_file_id="v",
            video_mime="video/mp4",
        )
        _publish(job_id)
        for row in storage.list_coverage_for_job(job_id):
            with storage._connect() as conn:
                storage._init_db(conn)
                conn.execute(
                    "UPDATE coverage_contributions SET status = 'voided' WHERE id = ?",
                    (row["id"],),
                )
                conn.commit()
        dossier = services.dossier_payload(9)
        fh = next(s for s in dossier["segments"] if s["id"] == "forehand")
        assert fh["job_count_pending"] == 0
        assert dossier["player"]["familiarity_pending"] == 0.0


def test_ntrp_seed_then_formula_after_core_gate(tmp_path):
    with _tmp_db(tmp_path):
        storage.save_player_profile(
            10,
            {
                "level": "recreational",
                "hand": "right",
                "frequency": "2",
                "experience": "y1_3",
                "coaching": "none",
                "focus": "technique",
                "injuries": "",
                "skipped": False,
            },
        )
        services.ensure_ntrp_seed(10)
        assert services.player_ntrp(10) == 3.0
        scores = {
            "preparation": 10,
            "contact": 10,
            "follow_through": 10,
            "footwork": 10,
        }
        fh = services.enqueue_review(
            10,
            _prepared("forehand", scores),
            language_code="ru",
            video_file_id="n1",
            video_mime="video/mp4",
        )
        _publish(fh)
        assert services.player_ntrp(10) == 3.0
        serve = services.enqueue_review(
            10,
            _prepared("serve", scores),
            language_code="ru",
            video_file_id="n2",
            video_mime="video/mp4",
        )
        _publish(serve)
        dossier = services.dossier_payload(10)
        assert dossier["player"]["progress_mean_pending"] == 5.0
        assert dossier["player"]["ntrp"] == 3.5


def test_focus_in_dossier_and_restore(tmp_path):
    with _tmp_db(tmp_path):
        prepared = _prepared("forehand", {"contact": 9, "footwork": 8})
        prepared.focus = "кисть вперёд"
        job_id = services.enqueue_review(
            11,
            prepared,
            language_code="ru",
            video_file_id="f1",
            video_mime="video/mp4",
        )
        _publish(job_id)
        fh = next(s for s in services.dossier_payload(11)["segments"] if s["id"] == "forehand")
        assert fh["focus"] == "кисть вперёд"
        assert fh["focus_status"] == "supervision"
        prepared2 = _prepared("forehand", {"contact": 8, "footwork": 8})
        prepared2.focus = "выше точка контакта"
        job2 = services.enqueue_review(
            11,
            prepared2,
            language_code="ru",
            video_file_id="f2",
            video_mime="video/mp4",
        )
        _publish(job2, status="sent_coach")
        fh = next(s for s in services.dossier_payload(11)["segments"] if s["id"] == "forehand")
        assert fh["focus"] == "выше точка контакта"
        assert fh["focus_status"] == "agreed"
        storage.restore_player_focus(11, "forehand")
        fh = next(s for s in services.dossier_payload(11)["segments"] if s["id"] == "forehand")
        assert fh["focus"] == "кисть вперёд"
