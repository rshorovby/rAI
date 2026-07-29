from pathlib import Path
from unittest.mock import patch

import drills
import storage


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "t.db")


def test_sync_and_pick(tmp_path):
    with _tmp_db(tmp_path):
        n = drills.sync_drills_from_wiki()
        assert n >= 5
        catalog = drills.catalog_for_prompt()
        assert "id=" in catalog
        picked = drills.pick_drills(["count-for-more-time"], ["footwork"], limit=2)
        assert picked
        assert picked[0]["id"]
        msg = drills.format_drill_message(picked[0], "ru")
        assert "Упражнение" in msg
