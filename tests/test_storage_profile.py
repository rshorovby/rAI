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
                "hand": "right",
                "frequency": "2",
                "experience": "y3_7",
                "coaching": "both",
                "focus": "stability",
                "injuries": "",
                "skipped": False,
            },
        )
        profile = storage.get_player_profile(1)

    assert profile is not None
    assert profile["level"] == "recreational"
    assert profile["hand"] == "right"
    assert profile["frequency"] == "2"
    assert profile["experience"] == "y3_7"
    assert profile["coaching"] == "both"
    assert profile["focus"] == "stability"
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
                "hand": "left",
                "frequency": "5_plus",
                "experience": "y15_plus",
                "coaching": "none",
                "focus": "serve",
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
                "hand": "right",
                "frequency": "1",
                "experience": "under_1",
                "coaching": "group",
                "focus": "power",
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


def test_preferred_language_overrides_device(tmp_path):
    with _tmp_db(tmp_path):
        storage.upsert_user(1, "alice", "Alice", None, "en")
        storage.set_preferred_language(1, "ru")
        storage.upsert_user(1, "alice", "Alice", None, "de")

        assert storage.get_preferred_language(1) == "ru"
        assert storage.get_user_language_code(1) == "ru"
        text = storage.format_profile_for_user(1, "ru")

    assert "Русский" in text


def test_legacy_profile_focus_becomes_full_eval(tmp_path):
    import sqlite3

    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE player_profiles (
            user_id     INTEGER PRIMARY KEY,
            level       TEXT,
            hand        TEXT,
            frequency   TEXT,
            experience  TEXT,
            coaching    TEXT,
            focus       TEXT,
            injuries    TEXT    NOT NULL DEFAULT '',
            skipped     INTEGER NOT NULL DEFAULT 0,
            updated_at  TEXT    NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO player_profiles
            (user_id, level, hand, focus, injuries, skipped, updated_at)
        VALUES (1, 'beginner', 'left', 'power', '', 0, 'now')
        """
    )
    conn.commit()
    conn.close()

    with patch.object(storage, "DB_PATH", db):
        profile = storage.get_player_profile(1)

    assert profile["focus"] == "all"
    assert profile["backhand"] is None
    assert profile["hand"] == "left"


def test_trainer_age_roundtrip_and_preserve(tmp_path):
    with _tmp_db(tmp_path):
        storage.save_player_profile(
            3,
            {
                "level": "beginner",
                "hand": "right",
                "backhand": "two_handed",
                "frequency": "2",
                "experience": "under_1",
                "coaching": "individual",
                "focus": "all",
                "age_band": "y10_11",
                "age_recorded_on": "2026-10-09",
                "injuries": "",
                "skipped": False,
            },
        )
        storage.save_player_profile(
            3,
            {
                "level": "beginner",
                "hand": "left",
                "frequency": "2",
                "experience": "under_1",
                "coaching": "individual",
                "focus": "all",
                "injuries": "",
                "skipped": False,
            },
        )
        profile = storage.get_player_profile(3)
        text = storage.format_profile_for_user(3, "ru")
        storage.mark_profile_skipped(3)
        skipped = storage.get_player_profile(3)

    assert profile["hand"] == "left"
    assert profile["age_band"] == "y10_11"
    assert profile["age_recorded_on"] == "2026-10-09"
    assert "10–11" in text
    assert "2026-10-09" in text
    assert skipped["age_band"] is None
    assert skipped["skipped"] is True


def test_format_profile_complete(tmp_path):
    with _tmp_db(tmp_path):
        storage.save_player_profile(
            2,
            {
                "level": "beginner",
                "hand": "right",
                "backhand": "one_handed",
                "frequency": "3_4",
                "experience": "y1_3",
                "coaching": "individual",
                "focus": "all",
                "injuries": "",
                "skipped": False,
            },
        )
        text = storage.format_profile_for_user(2, "ru")
    assert "Начинающий" in text
    assert "Одноручный" in text
    assert "Возраст" not in text
    assert "Главная цель" not in text
    assert "3–4 раза в неделю" in text
    assert "Индивидуально" in text
