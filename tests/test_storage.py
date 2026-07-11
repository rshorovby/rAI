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


def test_different_users_isolated(tmp_path):
    with _tmp_db(tmp_path):
        storage.save_session(1, SAMPLE_REPORT)
        storage.save_session(2, SAMPLE_REPORT)
        storage.save_session(2, SAMPLE_REPORT)

        assert storage.get_session_count(1) == 1
        assert storage.get_session_count(2) == 2
