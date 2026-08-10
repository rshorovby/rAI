from pathlib import Path
from unittest.mock import patch

import review
import storage


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "t.db")


def test_compose_final_with_notes_and_fallback():
    text = review.compose_final_report(
        "DRAFT",
        coach_notes="Смотри на кисть",
        fallback=True,
        lang="ru",
    )
    assert "предварительный" in text.lower() or "AI" in text
    assert "Смотри на кисть" in text
    assert "DRAFT" in text


def test_compose_replacement_overrides_draft():
    text = review.compose_final_report("DRAFT", replacement="FINAL", lang="ru")
    assert "FINAL" in text
    assert "DRAFT" not in text


def test_review_job_lifecycle(tmp_path):
    with _tmp_db(tmp_path):
        job_id = storage.create_review_job(
            7,
            video_file_id="vid",
            draft_text="hello",
            focus_text="focus",
            drill_text="drill",
        )
        job = storage.get_review_job(job_id)
        assert job["status"] == "queued"
        storage.update_review_job(
            job_id,
            forum_chat_id=-100,
            message_thread_id=55,
            pending_coach_action="notes",
            status="in_review",
        )
        by_thread = storage.get_open_review_by_thread(-100, 55)
        assert by_thread["id"] == job_id
        storage.mark_review_sent(
            job_id, status="sent_coach", final_text="FINAL", coach_notes="n"
        )
        assert storage.get_open_review_job(7) is None
        done = storage.get_review_job(job_id)
        assert done["status"] == "sent_coach"
        assert done["final_text"] == "FINAL"


def test_new_job_cancels_previous(tmp_path):
    with _tmp_db(tmp_path):
        a = storage.create_review_job(1, video_file_id="a", draft_text="1")
        b = storage.create_review_job(1, video_file_id="b", draft_text="2")
        assert storage.get_review_job(a)["status"] == "cancelled"
        assert storage.get_open_review_job(1)["id"] == b


def test_fallback_list_includes_old_jobs(tmp_path):
    with _tmp_db(tmp_path):
        job_id = storage.create_review_job(3, video_file_id="v", draft_text="d")
        with storage._connect() as conn:
            storage._init_db(conn)
            conn.execute(
                "UPDATE review_jobs SET created_at = ? WHERE id = ?",
                ("2000-01-01 00:00:00", job_id),
            )
            conn.commit()
        due = storage.list_review_jobs_for_fallback(hours=24)
        assert any(j["id"] == job_id for j in due)


def test_ai_sent_not_in_fallback(tmp_path):
    with _tmp_db(tmp_path):
        job_id = storage.create_review_job(4, video_file_id="v", draft_text="d")
        storage.mark_review_sent(job_id, status=review.STATUS_AI_SENT, final_text="d")
        with storage._connect() as conn:
            storage._init_db(conn)
            conn.execute(
                "UPDATE review_jobs SET created_at = ? WHERE id = ?",
                ("2000-01-01 00:00:00", job_id),
            )
            conn.commit()
        due = storage.list_review_jobs_for_fallback(hours=24)
        assert not any(j["id"] == job_id for j in due)


def test_player_forum_thread_lookup(tmp_path):
    with _tmp_db(tmp_path):
        storage.save_player_forum_topic(99, -1001, 77, title="Test")
        row = storage.get_player_by_forum_thread(-1001, 77)
        assert row is not None
        assert row["user_id"] == 99
        assert storage.get_player_by_forum_thread(-1001, 1) is None
