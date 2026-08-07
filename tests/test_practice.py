from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import practice
import storage

MSK = ZoneInfo("Europe/Moscow")


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "t.db")


def test_resolve_practice_date_choices():
    today = date(2026, 7, 31)  # Friday
    assert practice.resolve_practice_date("today", today=today) == today
    assert practice.resolve_practice_date("tomorrow", today=today) == date(2026, 8, 1)
    assert practice.resolve_practice_date("plus2", today=today) == date(2026, 8, 2)
    assert practice.resolve_practice_date("weekend", today=today) == date(2026, 8, 1)
    assert practice.resolve_practice_date("unknown", today=today) is None


def test_resolve_weekend_on_saturday_goes_sunday():
    saturday = date(2026, 8, 1)
    assert practice.resolve_practice_date("weekend", today=saturday) == date(2026, 8, 2)


def test_should_send_windows():
    morning = datetime(2026, 7, 31, 9, 0, tzinfo=MSK)
    evening = datetime(2026, 7, 31, 20, 0, tzinfo=MSK)
    early = datetime(2026, 7, 31, 8, 59, tzinfo=MSK)
    assert practice.should_send_pre_now(now=morning)
    assert not practice.should_send_pre_now(now=early)
    assert practice.should_send_post_now(now=evening)
    assert not practice.should_send_post_now(now=morning)


def test_practice_plan_lifecycle(tmp_path):
    with _tmp_db(tmp_path):
        plan_id = storage.create_practice_plan(1, "Фокус", "Drill A", "drill-a")
        active = storage.get_active_practice_plan(1)
        assert active["id"] == plan_id
        assert active["status"] == "awaiting_date"

        storage.set_practice_date(plan_id, "2026-07-31", skip_pre=False)
        active = storage.get_active_practice_plan(1)
        assert active["status"] == "scheduled"
        assert active["next_practice_on"] == "2026-07-31"

        due_pre = storage.list_due_practice_pre("2026-07-31")
        assert len(due_pre) == 1
        storage.mark_practice_pre_sent(plan_id)
        assert storage.list_due_practice_pre("2026-07-31") == []

        due_post = storage.list_due_practice_post("2026-07-31")
        assert len(due_post) == 1
        storage.mark_practice_post_sent(plan_id)
        storage.set_practice_post_answer(plan_id, "yes")
        assert storage.get_active_practice_plan(1) is None


def test_new_plan_cancels_previous(tmp_path):
    with _tmp_db(tmp_path):
        first = storage.create_practice_plan(5, "a", "b")
        second = storage.create_practice_plan(5, "c", "d")
        assert second != first
        active = storage.get_active_practice_plan(5)
        assert active["id"] == second
        old = storage.get_practice_plan(first)
        assert old["status"] == "cancelled"


def test_auto_schedule_stale_awaiting(tmp_path):
    with _tmp_db(tmp_path):
        plan_id = storage.create_practice_plan(9, "f", "d")
        with storage._connect() as conn:
            storage._init_db(conn)
            conn.execute(
                "UPDATE practice_plans SET created_at = ? WHERE id = ?",
                ("2026-07-29 12:00:00", plan_id),
            )
            conn.commit()
        n = storage.auto_schedule_stale_practice_plans("2026-07-31")
        assert n == 1
        plan = storage.get_practice_plan(plan_id)
        assert plan["status"] == "scheduled"
        assert plan["next_practice_on"] == "2026-07-31"
        assert plan["skip_pre"] == 1


def test_reminder_skips_active_practice(tmp_path):
    with _tmp_db(tmp_path):
        storage.upsert_user(
            11,
            username=None,
            first_name="T",
            last_name=None,
            language_code="ru",
        )
        with storage._connect() as conn:
            storage._init_db(conn)
            conn.execute(
                """
                UPDATE users
                SET last_seen_at = datetime('now', '-7 days'),
                    last_analysis_at = datetime('now', '-7 days')
                WHERE user_id = 11
                """
            )
            conn.execute(
                """
                INSERT INTO player_sessions
                    (user_id, created_at, summary, top3, next_video)
                VALUES (11, datetime('now', '-7 days'), 's', '', 'film fh')
                """
            )
            conn.commit()
        users = storage.get_users_for_reminder(days=7)
        assert any(u["user_id"] == 11 for u in users)

        storage.create_practice_plan(11, "f", "d")
        users = storage.get_users_for_reminder(days=7)
        assert not any(u["user_id"] == 11 for u in users)
