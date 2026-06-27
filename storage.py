"""Постоянное хранилище истории сессий игрока (SQLite)."""

import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from i18n import DEFAULT_LANG, report_section_headers, t

DB_PATH = Path(__file__).parent / "data" / "rally.db"
MAX_HISTORY_SESSIONS = 5  # столько последних сессий попадает в контекст тренера


# ---------------------------------------------------------------------------
# Подключение / инициализация
# ---------------------------------------------------------------------------


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS player_sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            created_at  TEXT    NOT NULL,
            summary     TEXT    NOT NULL,
            top3        TEXT    NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_user
            ON player_sessions (user_id, created_at DESC);
    """
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Извлечение секций из отчёта
# ---------------------------------------------------------------------------


def _extract_section(report: str, header: str) -> str:
    pattern = rf"##\s*{re.escape(header)}\s*\n(.*?)(?=\n##\s|\Z)"
    m = re.search(pattern, report, re.DOTALL)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------------------
# Публичный API
# ---------------------------------------------------------------------------


def _extract_report_sections(report: str, language_code: str) -> tuple[str, str]:
    headers = report_section_headers(language_code)
    summary = _extract_section(report, headers["summary"])
    top3 = _extract_section(report, headers["top3"])
    if summary:
        return summary, top3

    for alt in ("ru", "en"):
        alt_headers = report_section_headers(alt)
        summary = _extract_section(report, alt_headers["summary"])
        if summary:
            top3 = _extract_section(report, alt_headers["top3"])
            return summary, top3

    return report[:400], top3


def save_session(
    user_id: int,
    report: str,
    language_code: str = DEFAULT_LANG,
) -> None:
    """Сохраняет краткое резюме и топ-3 из отчёта в историю игрока."""
    summary, top3 = _extract_report_sections(report, language_code)
    created_at = datetime.now().strftime("%d %b %Y")

    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            "INSERT INTO player_sessions (user_id, created_at, summary, top3)"
            " VALUES (?, ?, ?, ?)",
            (user_id, created_at, summary, top3),
        )
        conn.commit()


def get_player_history(user_id: int) -> list[dict]:
    """Возвращает последние MAX_HISTORY_SESSIONS сессий (от старой к новой)."""
    with _connect() as conn:
        _init_db(conn)
        rows = conn.execute(
            """
            SELECT created_at, summary, top3
            FROM player_sessions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, MAX_HISTORY_SESSIONS),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_session_count(user_id: int) -> int:
    """Общее число сессий игрока."""
    with _connect() as conn:
        _init_db(conn)
        return conn.execute(
            "SELECT COUNT(*) FROM player_sessions WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]


def format_history_for_user(
    user_id: int,
    lang: str = DEFAULT_LANG,
) -> Optional[str]:
    """Возвращает историю в удобочитаемом виде для команды /history.
    Возвращает None, если сессий нет."""
    sessions = get_player_history(user_id)
    count = get_session_count(user_id)
    if not sessions:
        return None

    ui_lang = lang if lang in ("ru", "en") else DEFAULT_LANG
    lines = [t(ui_lang, "history_header", count=count)]
    shown = sessions[-MAX_HISTORY_SESSIONS:]
    for i, s in enumerate(shown, max(1, count - len(shown) + 1)):
        lines.append(f"*{i}. {s['created_at']}*")
        lines.append(s["summary"])
        if s["top3"]:
            lines.append(t(ui_lang, "history_priorities", top3=s["top3"]))
        lines.append("")
    return "\n".join(lines).strip()
