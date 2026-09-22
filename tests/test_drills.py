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
        assert "Счёт для большего времени" in msg
        assert "Count for more time" not in msg
        en = drills.format_drill_message(picked[0], "en")
        assert "Count for more time" in en


def test_cards_keep_https_url_only(tmp_path):
    with _tmp_db(tmp_path):
        drills.sync_drills_from_wiki()
        storage.upsert_drill(
            "count-for-more-time",
            title="Счёт",
            description="Описание",
            url="https://example.com/drill",
        )
        storage.upsert_drill(
            "late-prep-fix",
            title="Ранняя",
            description="Описание",
            url="http://example.com/plain",
        )
        cards = drills.cards_for_ids(
            [
                "missing",
                "count-for-more-time",
                "late-prep-fix",
                "count-for-more-time",
                "balance-hold",
            ],
            "ru",
        )
        assert [card["id"] for card in cards] == [
            "count-for-more-time",
            "late-prep-fix",
            "balance-hold",
        ]
        assert cards[0]["url"] == "https://example.com/drill"
        assert cards[0]["title"] == "Счёт для большего времени"
        assert cards[1]["url"] == ""
        storage.upsert_drill(
            "count-for-more-time",
            title="Счёт",
            description="Описание",
            url="",
        )
        kept = drills.cards_for_ids(["count-for-more-time"], "en")
        assert kept[0]["url"] == "https://example.com/drill"
        assert kept[0]["title"] == "Count for more time"


def test_all_drills_have_ru_strings():
    missing = sorted(
        set(p.stem for p in drills.DRILLS_DIR.glob("*.md")) - set(drills.DRILL_RU)
    )
    assert missing == [], f"Нет RU-перевода для: {missing}"
