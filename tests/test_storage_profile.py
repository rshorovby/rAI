from pathlib import Path
from unittest.mock import patch

import storage


def _tmp_db(tmp_path: Path):
    db = tmp_path / "test.db"
    return patch.object(storage, "DB_PATH", db)


def test_save_and_get_profile(tmp_path):
    with _tmp_db(tmp_path):
        storage.save_player_profile(
            1,
            {
                "level": "recreational",
                "focus": "strokes",
                "hand": "right",
                "injuries": "",
                "skipped": False,
            },
        )
        profile = storage.get_player_profile(1)

    assert profile is not None
    assert profile["level"] == "recreational"
    assert profile["focus"] == "strokes"
    assert profile["hand"] == "right"
    assert profile["skipped"] is False


def test_has_profile_record(tmp_path):
    with _tmp_db(tmp_path):
        assert storage.has_profile_record(5) is False
        storage.mark_profile_skipped(5)
        assert storage.has_profile_record(5) is True


def test_is_profile_complete(tmp_path):
    with _tmp_db(tmp_path):
        storage.mark_profile_skipped(3)
        assert storage.is_profile_complete(3) is False

        storage.save_player_profile(
            4,
            {
                "level": "advanced",
                "focus": "serve",
                "hand": "left",
                "injuries": "elbow",
                "skipped": False,
            },
        )
        assert storage.is_profile_complete(4) is True


def test_format_profile_skipped(tmp_path):
    with _tmp_db(tmp_path):
        storage.mark_profile_skipped(9)
        text = storage.format_profile_for_user(9, "ru")
    assert "пропущен" in text.lower() or "не заполнен" in text.lower()


def test_reset_player_data(tmp_path):
    with _tmp_db(tmp_path):
        storage.upsert_user(1, "alice", "Alice", None, "ru")
        storage.save_player_profile(
            1,
            {
                "level": "recreational",
                "focus": "strokes",
                "hand": "right",
                "injuries": "",
                "skipped": False,
            },
        )
        storage.save_session(
            1,
            "## Краткое резюме\nТест.\n\n## Топ-3\n1. A",
            "ru",
        )

        storage.reset_player_data(1)

        assert storage.has_profile_record(1) is False
        assert storage.get_player_history(1) == []
        profile = storage.get_player_profile(1)
        assert profile is None


def test_format_profile_complete(tmp_path):
    with _tmp_db(tmp_path):
        storage.save_player_profile(
            2,
            {
                "level": "beginner",
                "focus": "footwork",
                "hand": "right",
                "injuries": "",
                "skipped": False,
            },
        )
        text = storage.format_profile_for_user(2, "ru")
    assert "Начинающий" in text
    assert "Ноги" in text
