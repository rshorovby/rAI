from pathlib import Path
from unittest.mock import patch

import billing
import storage


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "t.db")


def test_default_free_quota(tmp_path):
    with _tmp_db(tmp_path):
        plan = billing.get_plan(1)
        assert plan.plan == billing.PLAN_FREE
        assert plan.analyses_left == billing.FREE_ANALYSES_PER_MONTH
        assert billing.has_quota(1)


def test_grant_pro_and_idempotent(tmp_path):
    with _tmp_db(tmp_path):
        first = billing.grant_pro(7, months=1, payment_id="pay-1")
        assert first["plan"] == billing.PLAN_PRO
        second = billing.grant_pro(7, months=1, payment_id="pay-1")
        assert second["expires_at"] == first["expires_at"]
        assert billing.is_pro(7)
        plan = billing.get_plan(7)
        assert plan.is_pro
        assert plan.analyses_limit == billing.PRO_ANALYSES_PER_MONTH


def test_quota_decreases_with_sessions(tmp_path):
    with _tmp_db(tmp_path):
        storage.save_session(3, "## Краткое резюме\nx\n")
        storage.save_session(3, "## Краткое резюме\ny\n")
        plan = billing.get_plan(3)
        assert plan.analyses_used == 2
        assert plan.analyses_left == 0
        assert not billing.has_quota(3)


def test_parse_stars_payload():
    payload = billing.stars_payload(42)
    assert billing.parse_stars_payload(payload) == 42
    assert billing.parse_stars_payload("junk") is None
