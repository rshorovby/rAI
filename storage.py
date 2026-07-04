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

        CREATE TABLE IF NOT EXISTS player_profiles (
            user_id     INTEGER PRIMARY KEY,
            level       TEXT,
            focus       TEXT,
            hand        TEXT,
            injuries    TEXT    NOT NULL DEFAULT '',
            skipped     INTEGER NOT NULL DEFAULT 0,
            updated_at  TEXT    NOT NULL
        );
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


def has_profile_record(user_id: int) -> bool:
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            "SELECT 1 FROM player_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return row is not None


def is_profile_complete(user_id: int) -> bool:
    profile = get_player_profile(user_id)
    return bool(
        profile and not profile.get("skipped") and profile.get("level")
    )


def get_player_profile(user_id: int) -> Optional[dict]:
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            """
            SELECT level, focus, hand, injuries, skipped, updated_at
            FROM player_profiles
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "level": row["level"],
        "focus": row["focus"],
        "hand": row["hand"],
        "injuries": row["injuries"] or "",
        "skipped": bool(row["skipped"]),
        "updated_at": row["updated_at"],
    }


def save_player_profile(user_id: int, profile: dict) -> None:
    updated_at = datetime.now().strftime("%d %b %Y %H:%M")
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            INSERT INTO player_profiles
                (user_id, level, focus, hand, injuries, skipped, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                level = excluded.level,
                focus = excluded.focus,
                hand = excluded.hand,
                injuries = excluded.injuries,
                skipped = excluded.skipped,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                profile.get("level"),
                profile.get("focus"),
                profile.get("hand"),
                profile.get("injuries", ""),
                1 if profile.get("skipped") else 0,
                updated_at,
            ),
        )
        conn.commit()


def mark_profile_skipped(user_id: int) -> None:
    save_player_profile(
        user_id,
        {
            "level": None,
            "focus": None,
            "hand": None,
            "injuries": "",
            "skipped": True,
        },
    )


def format_profile_for_user(user_id: int, lang: str) -> str:
    from onboarding import profile_value_label

    ui_lang = lang if lang in ("ru", "en") else DEFAULT_LANG
    profile = get_player_profile(user_id)
    if not profile:
        return t(ui_lang, "profile_not_set")

    if profile.get("skipped"):
        return t(ui_lang, "profile_skipped")

    injuries = profile.get("injuries") or ""
    injuries_text = (
        t(ui_lang, "ob_injuries_none")
        if not injuries.strip()
        else injuries.strip()
    )
    return t(
        ui_lang,
        "profile_view",
        level=profile_value_label(ui_lang, "level", profile.get("level")),
        focus=profile_value_label(ui_lang, "focus", profile.get("focus")),
        hand=profile_value_label(ui_lang, "hand", profile.get("hand")),
        injuries=injuries_text,
        updated_at=profile.get("updated_at", "—"),
    )


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
