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


def test_coach_eval_keyboard_has_three_ratings():
    markup = review.coach_eval_keyboard(12)
    buttons = [btn for row in markup.inline_keyboard for btn in row]
    assert {btn.callback_data for btn in buttons} == {
        "ce:r:12:ok",
        "ce:r:12:added",
        "ce:r:12:miss",
    }


def test_coach_eval_tags_only_after_added_or_miss():
    ok_kb = review.coach_eval_keyboard(1, rating=review.RATING_OK)
    assert len(ok_kb.inline_keyboard) == 1
    added_kb = review.coach_eval_keyboard(1, rating=review.RATING_ADDED)
    tag_data = {
        btn.callback_data for row in added_kb.inline_keyboard[1:] for btn in row
    }
    assert "ce:t:1:priority" in tag_data
    assert "ce:t:1:hallucination" in tag_data


def test_coach_evaluation_triple(tmp_path):
    with _tmp_db(tmp_path):
        job_id = storage.create_review_job(
            5,
            video_file_id="vid",
            draft_text="AI сказал: поздний замах",
        )
        storage.update_review_job(job_id, forum_chat_id=-100, message_thread_id=9)
        storage.mark_review_sent(
            job_id, status=review.STATUS_AI_SENT, final_text="AI сказал: поздний замах"
        )
        latest = storage.get_latest_review_job_for_thread(-100, 9)
        assert latest["id"] == job_id
        storage.upsert_coach_evaluation(
            job_id,
            player_id=5,
            coach_user_id=42,
            rating=review.RATING_ADDED,
            tags=[review.TAG_PRIORITY],
        )
        storage.append_coach_eval_delta(
            job_id,
            "Главное — встретить мяч впереди, а не замах",
            player_id=5,
            coach_user_id=42,
        )
        row = storage.get_coach_evaluation(job_id)
        job = storage.get_review_job(job_id)
        assert job["draft_text"] == "AI сказал: поздний замах"
        assert row["rating"] == "added"
        assert "priority" in row["tags"]
        assert "встретить мяч" in row["delta_text"]
        stats = storage.get_coach_eval_stats()
        assert stats["added"] == 1
        assert stats["with_delta"] == 1
