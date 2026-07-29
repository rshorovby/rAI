from pathlib import Path
from unittest.mock import patch

import storage


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "t.db")


def test_progress_scores_aggregation(tmp_path):
    with _tmp_db(tmp_path):
        storage.save_session(
            1,
            "## Краткое резюме\na\n",
            scores={"footwork": 5, "contact": 4},
            focus="x",
            stroke="forehand",
        )
        storage.save_session(
            1,
            "## Краткое резюме\nb\n",
            scores={"footwork": 7, "contact": 6},
            focus="y",
            stroke="forehand",
        )
        rows = storage.get_progress_scores(1, 90)
        assert len(rows) == 2
        assert rows[0]["scores"]["footwork"] == 5
        assert rows[1]["scores"]["footwork"] == 7


def test_progress_one_session(tmp_path):
    with _tmp_db(tmp_path):
        storage.save_session(
            2,
            "## Краткое резюме\na\n",
            scores={"footwork": 5},
        )
        rows = storage.get_progress_scores(2, 90)
        assert len(rows) == 1
