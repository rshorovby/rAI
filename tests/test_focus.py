from pathlib import Path
from unittest.mock import patch

import storage


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "t.db")


def test_focus_set_get_clear(tmp_path):
    with _tmp_db(tmp_path):
        storage.set_player_focus(1, "Повернуться до отскока", "forehand", days=7)
        focus = storage.get_player_focus(1)
        assert focus["focus"].startswith("Повернуться")
        assert focus["stroke"] == "forehand"
        storage.clear_player_focus(1)
        assert storage.get_player_focus(1) is None
