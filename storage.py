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
            top3        TEXT    NOT NULL DEFAULT '',
            next_video  TEXT    NOT NULL DEFAULT ''
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

        CREATE TABLE IF NOT EXISTS users (
            user_id         INTEGER PRIMARY KEY,
            username        TEXT,
            first_name      TEXT,
            last_name       TEXT,
            language_code   TEXT,
            first_seen_at   TEXT    NOT NULL,
            last_seen_at    TEXT    NOT NULL,
            last_analysis_at TEXT,
            reminder_sent_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_users_last_seen
            ON users (last_seen_at DESC);

        CREATE TABLE IF NOT EXISTS events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            event_type  TEXT    NOT NULL,
            created_at  TEXT    NOT NULL,
            payload     TEXT    NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_events_type
            ON events (event_type, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_events_user
            ON events (user_id, created_at DESC);
    """
    )
    _migrate_schema(conn)
    conn.commit()


def _migrate_schema(conn: sqlite3.Connection) -> None:
    migrations = (
        ("player_sessions", "next_video", "TEXT NOT NULL DEFAULT ''"),
        ("users", "last_analysis_at", "TEXT"),
        ("users", "reminder_sent_at", "TEXT"),
    )
    for table, column, typedef in migrations:
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {typedef}")


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


def _extract_report_sections(report: str, language_code: str) -> tuple[str, str, str]:
    headers = report_section_headers(language_code)
    summary = _extract_section(report, headers["summary"])
    top3 = _extract_section(report, headers["top3"])
    next_video = extract_next_video(report, language_code)
    if summary:
        return summary, top3, next_video

    for alt in ("ru", "en"):
        alt_headers = report_section_headers(alt)
        summary = _extract_section(report, alt_headers["summary"])
        if summary:
            top3 = _extract_section(report, alt_headers["top3"])
            next_video = extract_next_video(report, language_code)
            return summary, top3, next_video

    return report[:400], top3, next_video


def extract_next_video(report: str, language_code: str) -> str:
    headers = report_section_headers(language_code)
    text = _extract_section(report, headers["next_video"])
    if text:
        return text

    for alt in ("ru", "en"):
        alt_headers = report_section_headers(alt)
        text = _extract_section(report, alt_headers["next_video"])
        if text:
            return text
    return ""


def strip_next_video_section(report: str, language_code: str) -> str:
    """Убирает секцию «Следующее видео» из текста для отправки в Telegram."""
    result = report
    checked: set[str] = set()
    for lang in (language_code, "ru", "en"):
        base = lang if lang in ("ru", "en") else "en"
        if base in checked:
            continue
        checked.add(base)
        header = report_section_headers(base)["next_video"]
        pattern = rf"\n?##\s*{re.escape(header)}\s*\n.*?(?=\n##\s|\Z)"
        result = re.sub(pattern, "", result, flags=re.DOTALL)
    return result.strip()


def save_session(
    user_id: int,
    report: str,
    language_code: str = DEFAULT_LANG,
) -> None:
    """Сохраняет краткое резюме, топ-3 и задание на следующее видео."""
    summary, top3, next_video = _extract_report_sections(report, language_code)
    created_at = datetime.now().strftime("%d %b %Y")

    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            INSERT INTO player_sessions (user_id, created_at, summary, top3, next_video)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, created_at, summary, top3, next_video),
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
    return bool(profile and not profile.get("skipped") and profile.get("level"))


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


def upsert_user(
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
    language_code: Optional[str],
) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        existing = conn.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE users SET
                    username = ?,
                    first_name = ?,
                    last_name = ?,
                    language_code = ?,
                    last_seen_at = ?,
                    reminder_sent_at = NULL
                WHERE user_id = ?
                """,
                (username, first_name, last_name, language_code, now, user_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO users
                    (user_id, username, first_name, last_name, language_code,
                     first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    username,
                    first_name,
                    last_name,
                    language_code,
                    now,
                    now,
                ),
            )
        conn.commit()


def log_event(user_id: int, event_type: str, payload: str = "") -> None:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            "INSERT INTO events (user_id, event_type, created_at, payload)"
            " VALUES (?, ?, ?, ?)",
            (user_id, event_type, created_at, payload[:500]),
        )
        conn.commit()


def get_analytics_summary(recent_limit: int = 10) -> dict:
    from analytics import ALL_EVENT_TYPES

    with _connect() as conn:
        _init_db(conn)
        users_total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        profiles_complete = conn.execute(
            """
            SELECT COUNT(*) FROM player_profiles
            WHERE skipped = 0 AND level IS NOT NULL
            """
        ).fetchone()[0]
        profiles_skipped = conn.execute(
            "SELECT COUNT(*) FROM player_profiles WHERE skipped = 1"
        ).fetchone()[0]
        users_with_videos = conn.execute(
            "SELECT COUNT(DISTINCT user_id) FROM player_sessions"
        ).fetchone()[0]
        analyses_total = conn.execute(
            "SELECT COUNT(*) FROM player_sessions"
        ).fetchone()[0]
        users_active_7d = conn.execute(
            """
            SELECT COUNT(*) FROM users
            WHERE datetime(last_seen_at) >= datetime('now', '-7 days')
            """
        ).fetchone()[0]

        events: dict[str, int] = {}
        for event_type in ALL_EVENT_TYPES:
            events[event_type] = conn.execute(
                "SELECT COUNT(*) FROM events WHERE event_type = ?",
                (event_type,),
            ).fetchone()[0]

        rows = conn.execute(
            """
            SELECT
                u.user_id,
                u.username,
                u.first_name,
                u.last_name,
                u.language_code,
                u.first_seen_at,
                u.last_seen_at,
                COALESCE(s.videos, 0) AS videos,
                p.level,
                p.skipped AS profile_skipped
            FROM users u
            LEFT JOIN (
                SELECT user_id, COUNT(*) AS videos
                FROM player_sessions
                GROUP BY user_id
            ) s ON s.user_id = u.user_id
            LEFT JOIN player_profiles p ON p.user_id = u.user_id
            ORDER BY u.last_seen_at DESC
            LIMIT ?
            """,
            (recent_limit,),
        ).fetchall()

    recent_users = []
    for row in rows:
        profile_status = "—"
        if row["profile_skipped"]:
            profile_status = "пропущен"
        elif row["level"]:
            profile_status = row["level"]
        parts = [row["first_name"] or "", row["last_name"] or ""]
        display_name = " ".join(p for p in parts if p).strip()
        recent_users.append(
            {
                "user_id": row["user_id"],
                "username": row["username"],
                "display_name": display_name,
                "language_code": row["language_code"],
                "first_seen_at": row["first_seen_at"],
                "last_seen_at": row["last_seen_at"],
                "videos": row["videos"],
                "profile_status": profile_status,
            }
        )

    return {
        "users_total": users_total,
        "profiles_complete": profiles_complete,
        "profiles_skipped": profiles_skipped,
        "users_with_videos": users_with_videos,
        "users_active_7d": users_active_7d,
        "analyses_total": analyses_total,
        "events": events,
        "recent_users": recent_users,
    }


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
        t(ui_lang, "ob_injuries_none") if not injuries.strip() else injuries.strip()
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


def get_users_for_reminder(days: int = 7) -> list[dict]:
    """Пользователи для напоминания: N дней без взаимодействия с ботом."""
    with _connect() as conn:
        _init_db(conn)
        rows = conn.execute(
            """
            SELECT
                u.user_id,
                u.language_code,
                (
                    SELECT ps.next_video
                    FROM player_sessions ps
                    WHERE ps.user_id = u.user_id
                    ORDER BY ps.id DESC
                    LIMIT 1
                ) AS next_video
            FROM users u
            WHERE u.last_seen_at IS NOT NULL
              AND date(u.last_seen_at) = date('now', ?)
              AND (
                  u.reminder_sent_at IS NULL
                  OR datetime(u.reminder_sent_at) < datetime(u.last_seen_at)
              )
            """,
            (f"-{days} days",),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_reminder_sent(user_id: int) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            "UPDATE users SET reminder_sent_at = ? WHERE user_id = ?",
            (now, user_id),
        )
        conn.commit()
