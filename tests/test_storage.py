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
"""


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
        result = storage.format_history_for_user(5)
    assert result is not None
    assert "разбор" in result.lower()


def test_different_users_isolated(tmp_path):
    with _tmp_db(tmp_path):
        storage.save_session(1, SAMPLE_REPORT)
        storage.save_session(2, SAMPLE_REPORT)
        storage.save_session(2, SAMPLE_REPORT)

        assert storage.get_session_count(1) == 1
        assert storage.get_session_count(2) == 2
