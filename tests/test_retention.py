from pathlib import Path
from unittest.mock import patch

import storage
from analytics import EVENT_ANALYSIS_SUCCESS, EVENT_VIDEO_SENT


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "t.db")


def test_retention_cohorts_structure(tmp_path):
    with _tmp_db(tmp_path):
        storage.upsert_user(1, None, "A", None, "ru")
        storage.log_event(1, EVENT_VIDEO_SENT)
        storage.log_event(1, EVENT_ANALYSIS_SUCCESS)
        cohorts = storage.get_retention_cohorts(4)
        assert isinstance(cohorts, list)
        if cohorts:
            c = cohorts[-1]
            assert "d1_pct" in c
            assert "d30_pct" in c
            assert c["size"] >= 1
