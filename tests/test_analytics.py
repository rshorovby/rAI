from pathlib import Path
from unittest.mock import patch

import storage
from analytics import (
    EVENT_ANALYSIS_FAILED,
    EVENT_ANALYSIS_SUCCESS,
    EVENT_FEEDBACK_CLEAR,
    EVENT_FEEDBACK_NEGATIVE,
    EVENT_FEEDBACK_POSITIVE,
    EVENT_ONBOARDING_COMPLETED,
    EVENT_ONBOARDING_SKIPPED,
    EVENT_ONBOARDING_STARTED,
    EVENT_VIDEO_SENT,
    format_analytics_report,
)


def _tmp_db(tmp_path: Path):
    db = tmp_path / "test.db"
    return patch.object(storage, "DB_PATH", db)


def test_upsert_user_and_touch(tmp_path):
    with _tmp_db(tmp_path):
        storage.upsert_user(1, "alice", "Alice", None, "ru")
        storage.upsert_user(1, "alice2", "Alice", "A", "en")

        with storage._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = 1").fetchone()

    assert row["username"] == "alice2"
    assert row["language_code"] == "en"


def test_log_event_and_summary(tmp_path):
    with _tmp_db(tmp_path):
        storage.upsert_user(10, None, "Bob", None, "en")
        storage.log_event(10, EVENT_ONBOARDING_STARTED)
        storage.log_event(10, EVENT_ONBOARDING_COMPLETED)
        storage.log_event(10, EVENT_VIDEO_SENT)
        storage.log_event(10, EVENT_ANALYSIS_SUCCESS)

        data = storage.get_analytics_summary()

    assert data["users_total"] == 1
    assert data["events"][EVENT_ONBOARDING_STARTED] == 1
    assert data["events"][EVENT_ANALYSIS_SUCCESS] == 1
    assert len(data["recent_users"]) == 1
    assert data["recent_users"][0]["user_id"] == 10


def test_format_analytics_report_contains_sections():
    report = format_analytics_report(
        {
            "users_total": 5,
            "profiles_complete": 2,
            "profiles_skipped": 1,
            "users_with_videos": 3,
            "users_active_7d": 4,
            "analyses_total": 7,
            "events": {
                EVENT_ONBOARDING_STARTED: 3,
                EVENT_ONBOARDING_COMPLETED: 2,
                EVENT_ONBOARDING_SKIPPED: 1,
                EVENT_VIDEO_SENT: 5,
                EVENT_ANALYSIS_SUCCESS: 4,
                EVENT_ANALYSIS_FAILED: 1,
                EVENT_FEEDBACK_POSITIVE: 3,
                EVENT_FEEDBACK_NEGATIVE: 1,
                EVENT_FEEDBACK_CLEAR: 2,
            },
            "recent_users": [],
        }
    )
    assert "статистика" in report.lower()
    assert "Воронка" in report
    assert "Фидбек" in report
    assert "👍 Полезно: 3" in report
    assert "👎 Не помогло: 1" in report
    assert "✅ Понятно что делать: 2" in report


def test_feedback_events_in_summary(tmp_path):
    with _tmp_db(tmp_path):
        storage.upsert_user(20, None, "Ann", None, "ru")
        storage.log_event(20, EVENT_FEEDBACK_POSITIVE)
        storage.log_event(20, EVENT_FEEDBACK_NEGATIVE)
        storage.log_event(20, EVENT_FEEDBACK_CLEAR)
        data = storage.get_analytics_summary()

    assert data["events"][EVENT_FEEDBACK_POSITIVE] == 1
    assert data["events"][EVENT_FEEDBACK_NEGATIVE] == 1
    assert data["events"][EVENT_FEEDBACK_CLEAR] == 1
