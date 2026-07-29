from pathlib import Path
from unittest.mock import patch

import storage


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "t.db")


def test_digest_users_and_streak(tmp_path):
    with _tmp_db(tmp_path):
        storage.upsert_user(1, None, "A", None, "ru")
        storage.save_session(1, "## Краткое резюме\nx\n")
        users = storage.get_users_for_digest()
        assert any(u["user_id"] == 1 for u in users)
        storage.mark_digest_sent(1, had_analysis=True)
        with storage._connect() as conn:
            storage._init_db(conn)
            row = conn.execute(
                "SELECT streak_weeks, digest_sent_at FROM users WHERE user_id = 1"
            ).fetchone()
        assert row["streak_weeks"] == 1
        assert row["digest_sent_at"]
        # повторно сразу не должен попасть
        users2 = storage.get_users_for_digest()
        assert not any(u["user_id"] == 1 for u in users2)


def test_digest_skips_inactive(tmp_path):
    with _tmp_db(tmp_path):
        storage.upsert_user(2, None, "B", None, "en")
        with storage._connect() as conn:
            storage._init_db(conn)
            conn.execute(
                "UPDATE users SET last_seen_at = datetime('now', '-30 days') WHERE user_id = 2"
            )
            conn.commit()
        users = storage.get_users_for_digest()
        assert not any(u["user_id"] == 2 for u in users)
