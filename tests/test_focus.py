from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import remind
import services
import storage
from analyzer import AnalysisResult
from pricing import Usage
from prompts import build_system_prompt


def _tmp_db(tmp_path: Path):
    return patch.object(storage, "DB_PATH", tmp_path / "t.db")


def test_focus_set_get_clear(tmp_path):
    with _tmp_db(tmp_path):
        storage.set_player_focus(1, "Повернуться до отскока", "forehand", days=7)
        focus = storage.get_player_focus(1, "forehand")
        assert focus["focus"].startswith("Повернуться")
        assert focus["stroke"] == "forehand"
        storage.clear_player_focus(1, "forehand")
        assert storage.get_player_focus(1, "forehand") is None


def test_focus_is_per_segment(tmp_path):
    with _tmp_db(tmp_path):
        storage.set_player_focus(1, "Повернуться до отскока", "forehand", days=7)
        storage.set_player_focus(1, "Выше подброс", "serve", days=7)
        assert storage.get_player_focus(1, "forehand")["focus"].startswith(
            "Повернуться"
        )
        assert storage.get_player_focus(1, "serve")["focus"].startswith("Выше")
        assert storage.get_player_focus(1, "backhand") is None
        storage.clear_player_focus(1, "forehand")
        assert storage.get_player_focus(1, "forehand") is None
        assert storage.get_player_focus(1, "serve")["focus"].startswith("Выше")


def test_focus_without_stroke_is_ignored(tmp_path):
    with _tmp_db(tmp_path):
        storage.set_player_focus(1, "Глобальный фокус", "", days=7)
        storage.set_player_focus(1, "Глобальный фокус", None, days=7)
        assert storage.get_player_focus(1) is None
        assert storage.list_player_foci(1) == []


def test_expired_segment_does_not_clear_other(tmp_path):
    with _tmp_db(tmp_path):
        storage.set_player_focus(1, "форхенд", "forehand", days=7)
        storage.set_player_focus(1, "подача", "serve", days=7)
        past = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        with storage._connect() as conn:
            storage._init_db(conn)
            conn.execute(
                "UPDATE player_focus SET expires_at = ? WHERE stroke = ?",
                (past, "forehand"),
            )
            conn.commit()
        assert storage.get_player_focus(1, "forehand") is None
        assert storage.get_player_focus(1, "serve")["focus"] == "подача"


def test_analysis_context_uses_matching_segment_only(tmp_path):
    with _tmp_db(tmp_path):
        storage.set_player_focus(2, "кисть вперёд", "forehand", days=7)
        ctx_fh = services.load_analysis_context(2, "forehand")
        ctx_serve = services.load_analysis_context(2, "serve")
        ctx_none = services.load_analysis_context(2)
        assert ctx_fh["focus"] == "кисть вперёд"
        assert ctx_serve["focus"] is None
        assert ctx_none["focus"] is None


def test_save_session_updates_only_that_segment(tmp_path):
    with _tmp_db(tmp_path):
        storage.set_player_focus(3, "старый форхенд", "forehand", days=7)
        result = AnalysisResult(
            text="## Краткое резюме\nok\n", usage=Usage(), model="m"
        )
        prepared = services.prepare_report(result, {"stroke": "serve"})
        prepared.focus = "новый подброс"
        services.save_analysis_session(3, prepared, "ru")
        assert storage.get_player_focus(3, "forehand")["focus"] == "старый форхенд"
        assert storage.get_player_focus(3, "serve")["focus"] == "новый подброс"


def test_save_session_skips_unknown_stroke(tmp_path):
    with _tmp_db(tmp_path):
        result = AnalysisResult(
            text="## Краткое резюме\nok\n", usage=Usage(), model="m"
        )
        prepared = services.prepare_report(result, {"stroke": ""})
        prepared.focus = "некуда сохранить"
        services.save_analysis_session(4, prepared, "ru")
        assert storage.list_player_foci(4) == []


def test_migrate_legacy_one_row_per_user(tmp_path):
    with _tmp_db(tmp_path):
        with storage._connect() as conn:
            storage._init_db(conn)
            conn.execute("DROP TABLE player_focus")
            conn.execute(
                """
                CREATE TABLE player_focus (
                    user_id     INTEGER PRIMARY KEY,
                    focus       TEXT    NOT NULL,
                    stroke      TEXT,
                    set_at      TEXT    NOT NULL,
                    expires_at  TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO player_focus (user_id, focus, stroke, set_at, expires_at)
                VALUES (5, 'Повернуться до отскока', 'forehand',
                        '2026-09-01 12:00:00', '2026-12-01 12:00:00')
                """
            )
            conn.execute(
                """
                INSERT INTO player_focus (user_id, focus, stroke, set_at, expires_at)
                VALUES (6, 'без сегмента', NULL,
                        '2026-09-01 12:00:00', '2026-12-01 12:00:00')
                """
            )
            conn.commit()
        with storage._connect() as conn:
            storage._init_db(conn)
        assert storage.get_player_focus(5, "forehand")["focus"].startswith(
            "Повернуться"
        )
        assert storage.get_player_focus(5, "serve") is None
        assert storage.list_player_foci(6) == []


def test_prompt_does_not_reuse_other_stroke_focus():
    text = build_system_prompt("ru")
    assert "per stroke" in text
    assert "do not reuse a focus from another stroke" in text
    with_focus = build_system_prompt("ru", active_focus="Повернуться до отскока")
    assert "Повернуться до отскока" in with_focus
    assert "for this stroke" in with_focus


def test_digest_lists_each_segment(tmp_path):
    with _tmp_db(tmp_path):
        storage.set_player_focus(7, "кисть", "forehand", days=7)
        storage.set_player_focus(7, "подброс", "serve", days=7)
        text = remind._digest_focus_text(7, "ru")
        assert "форхенд" in text
        assert "кисть" in text
        assert "подача" in text
        assert "подброс" in text
