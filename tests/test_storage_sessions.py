from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import storage


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "t.db")


def test_active_session_roundtrip(tmp_path):
    with _tmp_db(tmp_path):
        payload = {"analysis": "report", "history": [{"user": "a", "assistant": "b"}]}
        storage.save_active_session(5, payload)
        loaded = storage.load_active_session(5)
        assert loaded["analysis"] == "report"
        assert loaded["history"][0]["user"] == "a"
        storage.clear_active_session(5)
        assert storage.load_active_session(5) is None


def test_active_session_ttl(tmp_path):
    with _tmp_db(tmp_path):
        storage.save_active_session(6, {"analysis": "x", "history": []})
        old = (
            datetime.now() - timedelta(days=storage.ACTIVE_SESSION_TTL_DAYS + 1)
        ).strftime("%Y-%m-%d %H:%M:%S")
        with storage._connect() as conn:
            storage._init_db(conn)
            conn.execute(
                "UPDATE active_sessions SET updated_at = ? WHERE user_id = 6",
                (old,),
            )
            conn.commit()
        assert storage.load_active_session(6) is None


def test_usage_log_and_summary(tmp_path):
    with _tmp_db(tmp_path):
        storage.log_usage(1, "analyze", "gemini-3.5-flash", 100, 50, 10, 12.0, 0.01)
        storage.log_usage(1, "chat", "gemini-3.5-flash", 20, 30, 0, None, 0.002)
        summary = storage.get_usage_summary(30)
        assert summary["analyses"] == 1
        assert summary["calls"] == 2
        assert summary["cost_usd"] > 0
