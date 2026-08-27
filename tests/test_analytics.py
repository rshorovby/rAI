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
    EVENT_REMINDER_SENT,
    EVENT_VIDEO_SENT,
    format_analytics_report,
    format_daly_report,
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
                EVENT_REMINDER_SENT: 4,
            },
            "recent_users": [],
            "usage": {
                "days": 30,
                "calls": 10,
                "analyses": 8,
                "input_tokens": 80000,
                "output_tokens": 20000,
                "thinking_tokens": 5000,
                "cost_usd": 0.42,
                "active_users": 5,
                "avg_cost_per_analysis": 0.0525,
                "cost_per_active_user": 0.084,
                "avg_input_tokens": 10000,
                "avg_output_tokens": 3125,
            },
        }
    )
    assert "статистика" in report.lower()
    assert "Воронка" in report
    assert "Фидбек" in report
    assert "себестоимость" in report.lower()
    assert "Оплата" in report
    assert "👍 Полезно: 3" in report
    assert "👎 Не помогло: 1" in report
    assert "✅ Понятно что делать: 2" in report
    assert "Напоминания" in report
    assert "Отправлено: 4" in report
    assert "Эталон тренера" in report


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


def test_daly_summary_counts(tmp_path):
    with _tmp_db(tmp_path):
        storage.upsert_user(1, None, "A", None, "ru")
        storage.upsert_user(2, None, "B", None, "ru")
        storage.upsert_user(3, None, "C", None, "ru")
        storage.save_session(1, "## Краткое резюме\none\n")
        storage.save_session(1, "## Краткое резюме\ntwo\n")
        storage.save_session(2, "## Краткое резюме\none\n")
        storage.log_event(1, EVENT_VIDEO_SENT)
        storage.log_event(1, EVENT_VIDEO_SENT)
        storage.log_event(2, EVENT_VIDEO_SENT)
        data = storage.get_daly_summary()

    assert data["users_with_analysis"] == 2
    assert data["users_2plus"] == 1
    assert data["new_analyzers_today"] == 2
    assert data["analyses_today"] == 3
    assert data["analyses_total"] == 3
    assert data["videos_today"] == 3
    assert data["videos_total"] == 3
    assert data["returned_7d"] == 0
    assert data["active_7d"] == 3
    assert data["active_30d"] == 3


def test_daly_returned_users(tmp_path):
    with _tmp_db(tmp_path):
        storage.upsert_user(1, None, "A", None, "ru")
        storage.save_session(1, "## Краткое резюме\nold\n")
        with storage._connect() as conn:
            storage._init_db(conn)
            conn.execute(
                "UPDATE player_sessions SET created_at = datetime('now', '-40 days')"
            )
            conn.commit()
        storage.save_session(1, "## Краткое резюме\nnew\n")
        data = storage.get_daly_summary()

    assert data["users_2plus"] == 1
    assert data["returned_7d"] == 1
    assert data["returned_30d"] == 1
    assert data["new_analyzers_today"] == 0


def test_format_daly_report():
    text = format_daly_report(
        {
            "users_with_analysis": 12,
            "new_analyzers_today": 1,
            "users_2plus": 4,
            "active_7d": 5,
            "active_30d": 8,
            "videos_today": 3,
            "videos_7d": 11,
            "videos_total": 40,
            "analyses_today": 2,
            "analyses_7d": 9,
            "analyses_total": 35,
            "returned_7d": 2,
            "returned_30d": 3,
        }
    )
    assert "daily" in text
    assert "С ≥1 разбором: 12 (+1 сегодня)" in text
    assert "5 за 7д" in text
    assert "С 2+ разборами: 4" in text
    assert "Сегодня: 3" in text
    assert "Всего: 35" in text
    assert "За неделю: 2" in text
    assert "За месяц: 3" in text
