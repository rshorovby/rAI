from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import billing
import storage


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "t.db")


def test_expire_after_grace(tmp_path):
    with _tmp_db(tmp_path):
        billing.grant_pro(9, months=1, payment_id="p9")
        past = (datetime.now() - timedelta(days=billing.GRACE_DAYS + 2)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        with storage._connect() as conn:
            storage._init_db(conn)
            conn.execute(
                "UPDATE subscriptions SET expires_at = ? WHERE user_id = 9",
                (past,),
            )
            conn.commit()
        expired = billing.expire_subscriptions()
        assert 9 in expired
        assert not billing.is_pro(9)


def test_still_pro_during_grace(tmp_path):
    with _tmp_db(tmp_path):
        billing.grant_pro(11, months=1, payment_id="p11")
        past = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        with storage._connect() as conn:
            storage._init_db(conn)
            conn.execute(
                "UPDATE subscriptions SET expires_at = ? WHERE user_id = 11",
                (past,),
            )
            conn.commit()
        assert billing.is_pro(11)
