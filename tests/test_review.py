from pathlib import Path
from unittest.mock import patch

import review
import storage


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "t.db")


def test_reply_keyboards_split_coach_and_bot():
    reply = review.keyboard_reply_to_coach("ru", player_id=5, via_trainer=False)
    assert [btn.callback_data for btn in reply.inline_keyboard[0]] == ["rvp:reply"]
    owned = review.keyboard_reply_to_coach("ru", player_id=5, via_trainer=True)
    assert owned.inline_keyboard[0][0].callback_data == "rvp:reply:5"
    cont = review.keyboard_continue_with_bot("ru")
    assert cont.inline_keyboard[0][0].callback_data == "rvp:bot"
    assert "ботом" in cont.inline_keyboard[0][0].text


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


def test_coach_action_keyboard_has_reply_fix_and_ok():
    markup = review.coach_action_keyboard(12)
    buttons = [btn for row in markup.inline_keyboard for btn in row]
    assert {btn.callback_data for btn in buttons} == {
        "ce:a:12:reply",
        "ce:a:12:fix",
        "ce:a:12:ok",
    }
    assert any(btn.text == "✅ ОК" for btn in buttons)


def test_coach_action_keyboard_marks_active_fix():
    markup = review.coach_action_keyboard(1, action=review.ACTION_FIX_AI_CONT)
    labels = [btn.text for row in markup.inline_keyboard for btn in row]
    assert any(text.startswith("· ") and "Поправить" in text for text in labels)


def test_coach_action_keyboard_marks_ok():
    markup = review.coach_action_keyboard(1, action=review.ACTION_APPROVE)
    labels = [btn.text for row in markup.inline_keyboard for btn in row]
    assert any(text.startswith("· ") and "ОК" in text for text in labels)


def test_strip_cabinet_draft_drops_summary_and_metadata():
    report = (
        "## Краткое резюме\n"
        "Любитель. Главное — точка контакта.\n\n"
        "## Что происходит на видео\n"
        "Форхенд сбоку, 12 секунд.\n\n"
        "## Топ-3 приоритета для тренировки\n"
        "1. Встретить мяч впереди.\n\n"
        "## Следующее видео\n"
        "Снять форхенд сбоку.\n\n"
        "## Метаданные (служебно)\n"
        "```json\n"
        '{"scores":{"footwork":6}}\n'
        "```"
    )
    body = review.strip_cabinet_draft(report)
    assert "Краткое резюме" not in body
    assert "Любитель. Главное" not in body
    assert "Метаданные" not in body
    assert "footwork" not in body
    assert "Что происходит на видео" in body
    assert "Встретить мяч впереди" in body
    assert "Следующее видео" not in body
    assert "Снять форхенд сбоку" not in body


def test_strip_cabinet_draft_fallback_drops_first_and_last_paragraphs():
    text = "первый абзац\n\nсередина разбора\n\nпоследний абзац"
    assert review.strip_cabinet_draft(text) == "середина разбора"


def test_cabinet_draft_parts_splits_observations_and_drops_extra():
    report = (Path(__file__).parent / "fixtures/structured/rally.md").read_text(
        encoding="utf-8"
    )
    parts = review.cabinet_draft_parts(report, "ru")
    texts = [part["text"] for part in parts]
    joined = "\n".join(texts)
    assert "Краткое резюме" not in joined
    assert "Метаданные" not in joined
    assert "Следующее видео" not in joined
    assert "footwork" not in joined
    assert texts[0].startswith("## Что происходит на видео")
    assert "форхенд" in texts[0].lower()
    assert texts[1].startswith("## Разбор по категориям\n### Техника удара")
    assert "**Рекомендация:**" in texts[1]
    assert parts[1]["window"] is not None
    assert any(part["text"].startswith("### Передвижение") for part in parts)
    footwork = next(part for part in parts if "Передвижение" in part["text"])
    assert footwork["window"] is None
    assert "недостаточно данных" in footwork["text"].lower()
    balance = next(part for part in parts if "Позиционирование" in part["text"])
    assert balance["window"] is None
    assert "не в приоритете" in balance["text"].lower()
    assert texts[-1].startswith("## Топ-3 приоритета для тренировки")
    assert all(part["window"] is None for part in parts if part is not parts[1])


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


def test_save_coach_correction_replaces_then_appends(tmp_path):
    with _tmp_db(tmp_path):
        job_id = storage.create_review_job(8, video_file_id="v", draft_text="черновик")
        storage.save_coach_correction(
            job_id,
            "первая версия",
            player_id=8,
            coach_user_id=1,
        )
        storage.save_coach_correction(
            job_id,
            "вторая версия",
            player_id=8,
            coach_user_id=1,
        )
        row = storage.get_coach_evaluation(job_id)
        assert row["delta_text"] == "вторая версия"
        storage.save_coach_correction(
            job_id,
            "дописка",
            player_id=8,
            coach_user_id=1,
            append=True,
        )
        row = storage.get_coach_evaluation(job_id)
        assert "вторая версия" in row["delta_text"]
        assert "дописка" in row["delta_text"]


def test_get_coach_corrections_for_player(tmp_path):
    with _tmp_db(tmp_path):
        a = storage.create_review_job(3, video_file_id="a", draft_text="AI A")
        b = storage.create_review_job(3, video_file_id="b", draft_text="AI B")
        other = storage.create_review_job(9, video_file_id="c", draft_text="AI C")
        storage.save_coach_correction(a, "тренер A", player_id=3, coach_user_id=1)
        storage.save_coach_correction(b, "тренер B", player_id=3, coach_user_id=1)
        storage.save_coach_correction(other, "чужой", player_id=9, coach_user_id=1)
        items = storage.get_coach_corrections_for_player(3)
        assert [row["delta_text"] for row in items] == ["тренер B", "тренер A"]
        assert items[0]["draft_text"] == "AI B"


def test_get_coach_corrections_global_excludes_player_jobs(tmp_path):
    with _tmp_db(tmp_path):
        a = storage.create_review_job(3, video_file_id="a", draft_text="AI A")
        b = storage.create_review_job(3, video_file_id="b", draft_text="AI B")
        other = storage.create_review_job(9, video_file_id="c", draft_text="AI C")
        storage.save_coach_correction(a, "тренер A", player_id=3, coach_user_id=1)
        storage.save_coach_correction(b, "тренер B", player_id=3, coach_user_id=1)
        storage.save_coach_correction(other, "чужой", player_id=9, coach_user_id=1)
        global_items = storage.get_coach_corrections_global(
            limit=4, exclude_job_ids={a, b}
        )
        assert [row["delta_text"] for row in global_items] == ["чужой"]
        merged = storage.get_coach_corrections_for_prompt(3)
        scopes = [(row["scope"], row["delta_text"]) for row in merged]
        assert ("global", "чужой") in scopes
        assert ("player", "тренер B") in scopes
        assert ("player", "тренер A") in scopes


def test_get_coach_corrections_for_prompt_without_player(tmp_path):
    with _tmp_db(tmp_path):
        job_id = storage.create_review_job(4, video_file_id="v", draft_text="AI")
        storage.save_coach_correction(job_id, "эталон", player_id=4, coach_user_id=1)
        items = storage.get_coach_corrections_for_prompt(None)
        assert len(items) == 1
        assert items[0]["scope"] == "global"
        assert items[0]["delta_text"] == "эталон"


def test_get_coach_approved_drafts_for_prompt(tmp_path):
    with _tmp_db(tmp_path):
        ok_job = storage.create_review_job(
            4, video_file_id="ok", draft_text="компетентный черновик"
        )
        fixed = storage.create_review_job(5, video_file_id="fx", draft_text="черновик")
        skipped = storage.create_review_job(
            6, video_file_id="sk", draft_text="тоже ок, но с правкой"
        )
        storage.upsert_coach_evaluation(
            ok_job, player_id=4, coach_user_id=1, rating=review.RATING_OK
        )
        storage.save_coach_correction(
            fixed, "эталон правки", player_id=5, coach_user_id=1
        )
        storage.upsert_coach_evaluation(
            skipped,
            player_id=6,
            coach_user_id=1,
            rating=review.RATING_OK,
            delta_text="правка поверх",
        )
        items = storage.get_coach_corrections_for_prompt(None)
        scopes = [
            (row["scope"], row.get("draft_text"), row.get("delta_text"))
            for row in items
        ]
        assert ("approved", "компетентный черновик", "") in scopes
        assert ("global", "черновик", "эталон правки") in scopes
        assert all(
            row["job_id"] != skipped for row in items if row["scope"] == "approved"
        )


def test_set_pending_coach_action_clears_other_jobs(tmp_path):
    with _tmp_db(tmp_path):
        a = storage.create_review_job(1, video_file_id="a", draft_text="1")
        b = storage.create_review_job(1, video_file_id="b", draft_text="2")
        storage.update_review_job(a, forum_chat_id=-1, message_thread_id=5)
        storage.update_review_job(b, forum_chat_id=-1, message_thread_id=5)
        storage.set_pending_coach_action(a, review.ACTION_FIX_AI)
        storage.set_pending_coach_action(b, review.ACTION_REPLY_PLAYER)
        assert storage.get_review_job(a)["pending_coach_action"] is None
        assert storage.get_review_job(b)["pending_coach_action"] == "reply"
        pending = storage.get_pending_review_job_for_thread(-1, 5)
        assert pending["id"] == b
