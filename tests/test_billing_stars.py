from pathlib import Path
from unittest.mock import patch

import billing
import storage


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "t.db")


def test_precheckout_payload_matches_user():
    payload = billing.stars_payload(55)
    assert billing.parse_stars_payload(payload) == 55


def test_successful_payment_grants_once(tmp_path):
    with _tmp_db(tmp_path):
        billing.grant_pro(55, payment_id="charge-abc")
        billing.grant_pro(55, payment_id="charge-abc")
        with storage._connect() as conn:
            storage._init_db(conn)
            n = conn.execute(
                "SELECT COUNT(*) FROM payments WHERE provider_payment_id = ?",
                ("charge-abc",),
            ).fetchone()[0]
        assert n == 1
        assert billing.is_pro(55)
