from pathlib import Path
from unittest.mock import patch

import storage


# Подменяем DB_PATH на временный файл во всех тестах
def _tmp_db(tmp_path: Path):
    db = tmp_path / "test.db"
    return patch.object(storage, "DB_PATH", db)


SAMPLE_REPORT = """\
## Краткое резюме
Игрок любительского уровня. Сильная сторона — стабильность бэкхенда. Зона роста — перенос веса на форхенде.

## Что происходит на видео
- 20 секунд, съёмка сбоку

## Разбор по категориям

### Техника удара
- **Наблюдение:** локоть высоко

## Топ-3 приоритета для тренировки
1. Перенос веса на форхенде
2. Сплит-степ
3. Follow-through

## Ограничения анализа
Качество видео ограниченное.

## Следующее видео
Сними форхенд сбоку, 15 секунд. Следи за переносом веса.
"""


def test_strip_next_video_section():
    stripped = storage.strip_next_video_section(SAMPLE_REPORT, "ru")
    assert "## Следующее видео" not in stripped
    assert "форхенд" not in stripped or "Ограничения" in stripped
    assert "форхенд" in storage.extract_next_video(SAMPLE_REPORT, "ru")


def test_extract_and_save_next_video(tmp_path):
    with _tmp_db(tmp_path):
        storage.upsert_user(42, None, "A", None, "ru")
        storage.save_session(42, SAMPLE_REPORT)
        with storage._connect() as conn:
            row = conn.execute(
                "SELECT next_video FROM player_sessions WHERE user_id = 42"
            ).fetchone()
        assert "форхенд" in row["next_video"]
        assert storage.extract_next_video(SAMPLE_REPORT, "ru") == row["next_video"]


def test_get_users_for_reminder(tmp_path):
    with _tmp_db(tmp_path):
        storage.upsert_user(1, None, "Ann", None, "ru")
        storage.save_session(1, SAMPLE_REPORT)
        with storage._connect() as conn:
            conn.execute(
                """
                UPDATE users SET last_seen_at = datetime('now', '-7 days')
                WHERE user_id = 1
                """
            )
            conn.commit()
        users = storage.get_users_for_reminder(days=7)
    assert len(users) == 1
    assert users[0]["user_id"] == 1
    assert "форхенд" in users[0]["next_video"]


def test_reminder_not_sent_twice(tmp_path):
    with _tmp_db(tmp_path):
        storage.upsert_user(2, None, "Bob", None, "en")
        storage.save_session(2, SAMPLE_REPORT)
        with storage._connect() as conn:
            conn.execute(
                """
                UPDATE users SET last_seen_at = datetime('now', '-7 days')
                WHERE user_id = 2
                """
            )
            conn.commit()
        assert len(storage.get_users_for_reminder(days=7)) == 1
        storage.mark_reminder_sent(2)
        assert len(storage.get_users_for_reminder(days=7)) == 0


def test_get_users_for_no_video_survey(tmp_path):
    with _tmp_db(tmp_path):
        storage.upsert_user(10, None, "Ann", None, "ru")
        storage.save_player_profile(
            10,
            {
                "level": "amateur",
                "focus": "fh",
                "hand": "right",
                "injuries": "",
            },
        )
        storage.log_event(10, "onboarding_completed")
        with storage._connect() as conn:
            conn.execute(
                """
                UPDATE events
                SET created_at = datetime('now', '-25 hours')
                WHERE user_id = 10 AND event_type = 'onboarding_completed'
                """
            )
            conn.commit()

        users = storage.get_users_for_no_video_survey(hours=24)
        assert len(users) == 1
        assert users[0]["user_id"] == 10

        storage.mark_no_video_survey_sent(10)
        assert len(storage.get_users_for_no_video_survey(hours=24)) == 0

        storage.log_event(10, "video_sent")
        storage.upsert_user(11, None, "Bob", None, "en")
        storage.save_player_profile(
            11,
            {
                "level": "amateur",
                "focus": "fh",
                "hand": "right",
                "injuries": "",
            },
        )
        storage.log_event(11, "onboarding_completed")
        with storage._connect() as conn:
            conn.execute(
                """
                UPDATE events
                SET created_at = datetime('now', '-25 hours')
                WHERE user_id = 11 AND event_type = 'onboarding_completed'
                """
            )
            conn.commit()
        users = storage.get_users_for_no_video_survey(hours=24)
        assert len(users) == 1
        assert users[0]["user_id"] == 11


def test_get_users_for_no_onboarding_survey(tmp_path):
    with _tmp_db(tmp_path):
        storage.upsert_user(20, None, "Ann", None, "ru")
        storage.log_event(20, "onboarding_started")
        with storage._connect() as conn:
            conn.execute(
                """
                UPDATE events
                SET created_at = datetime('now', '-25 hours')
                WHERE user_id = 20 AND event_type = 'onboarding_started'
                """
            )
            conn.commit()

        users = storage.get_users_for_no_onboarding_survey(hours=24)
        assert len(users) == 1
        assert users[0]["user_id"] == 20

        storage.mark_no_onboarding_survey_sent(20)
        assert len(storage.get_users_for_no_onboarding_survey(hours=24)) == 0

        storage.save_player_profile(
            21,
            {
                "level": "amateur",
                "focus": "fh",
                "hand": "right",
                "injuries": "",
            },
        )
        storage.upsert_user(21, None, "Bob", None, "en")
        storage.log_event(21, "onboarding_started")
        with storage._connect() as conn:
            conn.execute(
                """
                UPDATE events
                SET created_at = datetime('now', '-25 hours')
                WHERE user_id = 21 AND event_type = 'onboarding_started'
                """
            )
            conn.commit()
        assert len(storage.get_users_for_no_onboarding_survey(hours=24)) == 0


def test_save_and_retrieve(tmp_path):
    with _tmp_db(tmp_path):
        storage.save_session(42, SAMPLE_REPORT)
        history = storage.get_player_history(42)

    assert len(history) == 1
    assert "любительского уровня" in history[0]["summary"]
    assert "Перенос веса" in history[0]["top3"]


def test_count(tmp_path):
    with _tmp_db(tmp_path):
        storage.save_session(1, SAMPLE_REPORT)
        storage.save_session(1, SAMPLE_REPORT)
        assert storage.get_session_count(1) == 2
        assert storage.get_session_count(99) == 0


def test_history_keeps_same_stroke_and_two_others(tmp_path):
    with _tmp_db(tmp_path):
        for i in range(4):
            storage.save_session(7, f"## Краткое резюме\nfh-{i}\n", stroke="forehand")
        for i in range(3):
            storage.save_session(7, f"## Краткое резюме\nsv-{i}\n", stroke="serve")
        history = storage.get_player_history(7, "forehand")
    summaries = [item["summary"] for item in history]
    assert summaries.count("fh-0") == 0
    assert {"fh-1", "fh-2", "fh-3"} <= set(summaries)
    assert "sv-2" in summaries and "sv-1" in summaries
    assert summaries.index("fh-1") < summaries.index("sv-2")


def test_note_is_clipped_and_practice_answer_is_listed(tmp_path):
    with _tmp_db(tmp_path):
        storage.add_player_note(4, "я" * 600)
        notes = storage.recent_player_notes(4)
        plan_id = storage.create_practice_plan(
            4, "разворот", "тень", "unit-turn-shadow"
        )
        storage.set_practice_post_answer(plan_id, "hard")
        answers = storage.recent_practice_answers(4)
    assert len(notes) == 1
    assert len(notes[0]["text"]) == storage.NOTE_MAX_CHARS
    assert notes[0]["text"].endswith("…")
    assert answers[0]["post_answer"] == "hard"
    assert answers[0]["drill_id"] == "unit-turn-shadow"


def test_chronic_tag_needs_two_hits(tmp_path):
    with _tmp_db(tmp_path):
        storage.save_session(
            5, "## Краткое резюме\na\n", stroke="forehand", issue_tags=["unit-turn"]
        )
        once = storage.player_memory(5)
        storage.save_session(
            5, "## Краткое резюме\nb\n", stroke="forehand", issue_tags=["unit-turn"]
        )
        storage.save_session(
            5,
            "## Краткое резюме\nc\n",
            stroke="forehand",
            focus_checks=[{"stroke": "forehand", "status": "improved"}],
        )
        memory = storage.player_memory(5)
    assert once["chronic"] == []
    assert memory["chronic"][0]["tag"] == "unit-turn"
    assert memory["chronic"][0]["count"] == 2
    assert memory["closed_focuses"] == 1
    assert memory["stroke_counts"]["forehand"] == 3


def test_max_history_limit(tmp_path):
    with _tmp_db(tmp_path):
        for _ in range(8):
            storage.save_session(7, SAMPLE_REPORT)
        history = storage.get_player_history(7)

    assert len(history) <= storage.MAX_HISTORY_SESSIONS


def test_no_history_returns_none(tmp_path):
    with _tmp_db(tmp_path):
        result = storage.format_history_for_user(999)
    assert result is None


def test_format_history_for_user(tmp_path):
    with _tmp_db(tmp_path):
        storage.save_session(5, SAMPLE_REPORT)
        result = storage.format_history_for_user(5, "ru")
    assert result is not None
    assert "разбор" in result.lower()


def test_acquisition_source_keeps_first_code(tmp_path):
    with _tmp_db(tmp_path):
        player_id = storage.get_or_create_telegram_player(77)
        assert storage.get_acquisition_source(player_id) is None
        assert storage.set_acquisition_source_if_empty(player_id, "minsk_mir") == (
            "minsk_mir"
        )
        assert (
            storage.set_acquisition_source_if_empty(player_id, "instagram")
            == "minsk_mir"
        )
        assert storage.get_acquisition_source(player_id) == "minsk_mir"


def test_different_users_isolated(tmp_path):
    with _tmp_db(tmp_path):
        storage.save_session(1, SAMPLE_REPORT)
        storage.save_session(2, SAMPLE_REPORT)
        storage.save_session(2, SAMPLE_REPORT)

        assert storage.get_session_count(1) == 1
        assert storage.get_session_count(2) == 2
