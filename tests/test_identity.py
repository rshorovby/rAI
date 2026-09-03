from pathlib import Path
from unittest.mock import patch

import identity
import storage


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "t.db")


def test_upsert_creates_telegram_identity(tmp_path):
    with _tmp_db(tmp_path):
        player_id = storage.upsert_user(42, "ann", "Ann", None, "ru")
        assert player_id == 42
        assert identity.telegram_id_for(42) == 42
        assert identity.player_id_for_telegram(42) == 42
        assert identity.get_or_create_telegram_player(42) == 42


def test_backfill_from_existing_users_table(tmp_path):
    with _tmp_db(tmp_path):
        with storage._connect() as conn:
            storage._init_db(conn)
            conn.execute(
                """
                INSERT INTO users
                    (user_id, username, first_name, last_name, language_code,
                     first_seen_at, last_seen_at)
                VALUES (7, NULL, 'A', NULL, 'ru', '2020-01-01 00:00:00',
                        '2020-01-01 00:00:00')
                """
            )
            conn.commit()
        with storage._connect() as conn:
            storage._init_db(conn)
        assert identity.telegram_id_for(7) == 7
        assert identity.player_id_for_telegram(7) == 7


def test_wal_enabled(tmp_path):
    with _tmp_db(tmp_path):
        storage.upsert_user(1, None, "A", None, "ru")
        with storage._connect() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert str(mode).lower() == "wal"
