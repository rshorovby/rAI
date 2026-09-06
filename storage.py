"""Постоянное хранилище истории сессий игрока (SQLite)."""

import json
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from i18n import DEFAULT_LANG, report_section_headers, t

DB_PATH = Path(__file__).parent / "data" / "rally.db"
MAX_HISTORY_SESSIONS = 5  # столько последних сессий попадает в контекст тренера
ACTIVE_SESSION_TTL_DAYS = 7

PROVIDER_TELEGRAM = "telegram"
PROVIDER_APPLE = "apple"
CHANNEL_TELEGRAM = "telegram"
CHANNEL_IOS = "ios"
LINK_TG_TO_IOS = "tg_to_ios"
LINK_IOS_TO_TG = "ios_to_tg"

_PLAYER_ID_COLUMNS = (
    ("users", "user_id"),
    ("player_sessions", "user_id"),
    ("player_profiles", "user_id"),
    ("events", "user_id"),
    ("usage_log", "user_id"),
    ("active_sessions", "user_id"),
    ("subscriptions", "user_id"),
    ("payments", "user_id"),
    ("player_focus", "user_id"),
    ("practice_plans", "user_id"),
    ("player_forum_topics", "user_id"),
    ("review_jobs", "user_id"),
    ("survey_responses", "user_id"),
    ("coach_evaluations", "player_id"),
)


# ---------------------------------------------------------------------------
# Подключение / инициализация
# ---------------------------------------------------------------------------


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS players (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS identities (
            player_id   INTEGER NOT NULL,
            provider    TEXT    NOT NULL,
            subject     TEXT    NOT NULL,
            created_at  TEXT    NOT NULL,
            PRIMARY KEY (provider, subject),
            UNIQUE (player_id, provider)
        );
        CREATE INDEX IF NOT EXISTS idx_identities_player
            ON identities (player_id);

        CREATE TABLE IF NOT EXISTS api_sessions (
            token       TEXT PRIMARY KEY,
            player_id   INTEGER NOT NULL,
            created_at  TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_api_sessions_player
            ON api_sessions (player_id);

        CREATE TABLE IF NOT EXISTS link_codes (
            code        TEXT PRIMARY KEY,
            player_id   INTEGER NOT NULL,
            direction   TEXT    NOT NULL,
            expires_at  TEXT    NOT NULL,
            created_at  TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS device_tokens (
            token       TEXT PRIMARY KEY,
            player_id   INTEGER NOT NULL,
            created_at  TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_device_tokens_player
            ON device_tokens (player_id);

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
            hand        TEXT,
            frequency   TEXT,
            experience  TEXT,
            coaching    TEXT,
            focus       TEXT,
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

        CREATE TABLE IF NOT EXISTS usage_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            kind            TEXT    NOT NULL,
            model           TEXT    NOT NULL,
            input_tokens    INTEGER NOT NULL DEFAULT 0,
            output_tokens   INTEGER NOT NULL DEFAULT 0,
            thinking_tokens INTEGER NOT NULL DEFAULT 0,
            video_seconds   REAL,
            cost_usd        REAL    NOT NULL DEFAULT 0,
            created_at      TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_usage_created
            ON usage_log (created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_usage_user
            ON usage_log (user_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS active_sessions (
            user_id    INTEGER PRIMARY KEY,
            payload    TEXT    NOT NULL,
            updated_at TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id         INTEGER PRIMARY KEY,
            plan            TEXT    NOT NULL DEFAULT 'free',
            status          TEXT    NOT NULL DEFAULT 'active',
            started_at      TEXT    NOT NULL,
            expires_at      TEXT,
            provider        TEXT,
            last_payment_id TEXT,
            reminder_sent_at TEXT
        );

        CREATE TABLE IF NOT EXISTS payments (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id             INTEGER NOT NULL,
            provider            TEXT    NOT NULL,
            provider_payment_id TEXT    UNIQUE,
            amount              INTEGER NOT NULL,
            currency            TEXT    NOT NULL,
            status              TEXT    NOT NULL,
            created_at          TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_payments_user
            ON payments (user_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS drills (
            id                TEXT PRIMARY KEY,
            title             TEXT NOT NULL,
            description       TEXT NOT NULL DEFAULT '',
            tags              TEXT NOT NULL DEFAULT '[]',
            telegram_file_id  TEXT,
            language          TEXT NOT NULL DEFAULT 'ru'
        );

        CREATE TABLE IF NOT EXISTS player_focus (
            user_id     INTEGER PRIMARY KEY,
            focus       TEXT    NOT NULL,
            stroke      TEXT,
            set_at      TEXT    NOT NULL,
            expires_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS practice_plans (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id           INTEGER NOT NULL,
            created_at        TEXT    NOT NULL,
            focus_text        TEXT    NOT NULL DEFAULT '',
            drill_text        TEXT    NOT NULL DEFAULT '',
            drill_id          TEXT,
            next_practice_on  TEXT,
            pre_sent_at       TEXT,
            post_sent_at      TEXT,
            post_answer       TEXT,
            status            TEXT    NOT NULL DEFAULT 'awaiting_date',
            mute_until        TEXT,
            skip_pre          INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_practice_user_status
            ON practice_plans (user_id, status);
        CREATE INDEX IF NOT EXISTS idx_practice_due
            ON practice_plans (status, next_practice_on);

        CREATE TABLE IF NOT EXISTS player_forum_topics (
            user_id            INTEGER PRIMARY KEY,
            forum_chat_id      INTEGER NOT NULL,
            message_thread_id  INTEGER NOT NULL,
            title              TEXT    NOT NULL DEFAULT '',
            created_at         TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS review_jobs (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id              INTEGER NOT NULL,
            reviewer_id          INTEGER,
            created_at           TEXT    NOT NULL,
            status               TEXT    NOT NULL DEFAULT 'queued',
            video_file_id        TEXT    NOT NULL,
            video_mime           TEXT    NOT NULL DEFAULT 'video/mp4',
            language_code        TEXT    NOT NULL DEFAULT 'ru',
            draft_text           TEXT    NOT NULL DEFAULT '',
            final_text           TEXT    NOT NULL DEFAULT '',
            coach_notes          TEXT    NOT NULL DEFAULT '',
            focus_text           TEXT    NOT NULL DEFAULT '',
            drill_text           TEXT    NOT NULL DEFAULT '',
            drill_id             TEXT,
            scores_json          TEXT    NOT NULL DEFAULT '',
            stroke               TEXT    NOT NULL DEFAULT '',
            forum_chat_id        INTEGER,
            message_thread_id    INTEGER,
            pending_coach_action TEXT,
            sent_at              TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_review_user_status
            ON review_jobs (user_id, status);
        CREATE INDEX IF NOT EXISTS idx_review_status_created
            ON review_jobs (status, created_at);

        CREATE TABLE IF NOT EXISTS survey_responses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            survey_type TEXT    NOT NULL,
            selected    TEXT    NOT NULL,
            other_text  TEXT    NOT NULL DEFAULT '',
            source      TEXT    NOT NULL DEFAULT 'auto',
            created_at  TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_survey_user
            ON survey_responses (user_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS coach_evaluations (
            job_id         INTEGER PRIMARY KEY,
            player_id      INTEGER NOT NULL,
            coach_user_id  INTEGER NOT NULL,
            rating         TEXT    NOT NULL DEFAULT '',
            tags_json      TEXT    NOT NULL DEFAULT '[]',
            delta_text     TEXT    NOT NULL DEFAULT '',
            created_at     TEXT    NOT NULL,
            updated_at     TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_coach_eval_rating
            ON coach_evaluations (rating, updated_at DESC);
    """
    )
    _migrate_schema(conn)
    conn.commit()


def _migrate_schema(conn: sqlite3.Connection) -> None:
    migrations = (
        ("player_sessions", "next_video", "TEXT NOT NULL DEFAULT ''"),
        ("player_sessions", "scores", "TEXT NOT NULL DEFAULT ''"),
        ("player_sessions", "focus", "TEXT NOT NULL DEFAULT ''"),
        ("player_sessions", "stroke", "TEXT NOT NULL DEFAULT ''"),
        ("users", "last_analysis_at", "TEXT"),
        ("users", "reminder_sent_at", "TEXT"),
        ("users", "digest_sent_at", "TEXT"),
        ("users", "streak_weeks", "INTEGER NOT NULL DEFAULT 0"),
        ("subscriptions", "reminder_sent_at", "TEXT"),
        ("users", "no_video_survey_sent_at", "TEXT"),
        ("users", "no_onboarding_survey_sent_at", "TEXT"),
        ("player_profiles", "frequency", "TEXT"),
        ("player_profiles", "experience", "TEXT"),
        ("player_profiles", "coaching", "TEXT"),
        ("review_jobs", "source_channel", "TEXT NOT NULL DEFAULT 'telegram'"),
    )
    for table, column, typedef in migrations:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if table not in tables:
            continue
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {typedef}")
    _backfill_telegram_identities(conn)


def _table_names(conn: sqlite3.Connection) -> set:
    return {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _backfill_telegram_identities(conn: sqlite3.Connection) -> None:
    """Каждый существующий user_id игрока → player + identity telegram."""
    tables = _table_names(conn)
    ids = set()
    for table, column in _PLAYER_ID_COLUMNS:
        if table not in tables:
            continue
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            continue
        for row in conn.execute(
            f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL"
        ):
            ids.add(int(row[0]))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for uid in ids:
        conn.execute(
            "INSERT OR IGNORE INTO players (id, created_at) VALUES (?, ?)",
            (uid, now),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO identities
                (player_id, provider, subject, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (uid, PROVIDER_TELEGRAM, str(uid), now),
        )


def get_or_create_telegram_player(telegram_user_id: int) -> int:
    """Telegram-origin: player_id совпадает с telegram id (см. PRODUCT_IOS.md)."""
    telegram_user_id = int(telegram_user_id)
    subject = str(telegram_user_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            """
            SELECT player_id FROM identities
            WHERE provider = ? AND subject = ?
            """,
            (PROVIDER_TELEGRAM, subject),
        ).fetchone()
        if row:
            return int(row["player_id"])
        conn.execute(
            "INSERT OR IGNORE INTO players (id, created_at) VALUES (?, ?)",
            (telegram_user_id, now),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO identities
                (player_id, provider, subject, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (telegram_user_id, PROVIDER_TELEGRAM, subject, now),
        )
        row = conn.execute(
            """
            SELECT player_id FROM identities
            WHERE provider = ? AND subject = ?
            """,
            (PROVIDER_TELEGRAM, subject),
        ).fetchone()
        conn.commit()
    if not row:
        raise RuntimeError(f"не удалось создать identity telegram={telegram_user_id}")
    return int(row["player_id"])


def player_id_for_telegram(telegram_user_id: int) -> Optional[int]:
    subject = str(int(telegram_user_id))
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            """
            SELECT player_id FROM identities
            WHERE provider = ? AND subject = ?
            """,
            (PROVIDER_TELEGRAM, subject),
        ).fetchone()
    if not row:
        return None
    return int(row["player_id"])


def telegram_id_for(player_id: int) -> Optional[int]:
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            """
            SELECT subject FROM identities
            WHERE player_id = ? AND provider = ?
            """,
            (int(player_id), PROVIDER_TELEGRAM),
        ).fetchone()
    if not row:
        return None
    try:
        return int(row["subject"])
    except (TypeError, ValueError):
        return None


def _now_sql() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_or_create_apple_player(apple_sub: str) -> int:
    subject = (apple_sub or "").strip()
    if not subject:
        raise ValueError("empty apple subject")
    now = _now_sql()
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            """
            SELECT player_id FROM identities
            WHERE provider = ? AND subject = ?
            """,
            (PROVIDER_APPLE, subject),
        ).fetchone()
        if row:
            return int(row["player_id"])
        cur = conn.execute(
            "INSERT INTO players (created_at) VALUES (?)",
            (now,),
        )
        player_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO identities (player_id, provider, subject, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (player_id, PROVIDER_APPLE, subject, now),
        )
        conn.commit()
    return player_id


def player_has_telegram(player_id: int) -> bool:
    return telegram_id_for(player_id) is not None


def player_language_code(player_id: int) -> str:
    code = get_user_language_code(player_id)
    return code or ""


def has_player_history(player_id: int) -> bool:
    with _connect() as conn:
        _init_db(conn)
        jobs = conn.execute(
            "SELECT 1 FROM review_jobs WHERE user_id = ? LIMIT 1",
            (int(player_id),),
        ).fetchone()
        if jobs:
            return True
        sessions = conn.execute(
            "SELECT 1 FROM player_sessions WHERE user_id = ? LIMIT 1",
            (int(player_id),),
        ).fetchone()
    return bool(sessions)


def create_api_session(player_id: int) -> str:
    import secrets

    token = secrets.token_urlsafe(32)
    now = _now_sql()
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            "INSERT INTO api_sessions (token, player_id, created_at) VALUES (?, ?, ?)",
            (token, int(player_id), now),
        )
        conn.commit()
    return token


def player_id_for_session(token: str) -> Optional[int]:
    if not token:
        return None
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            "SELECT player_id FROM api_sessions WHERE token = ?",
            (token,),
        ).fetchone()
    if not row:
        return None
    return int(row["player_id"])


def delete_api_session(token: str) -> None:
    with _connect() as conn:
        _init_db(conn)
        conn.execute("DELETE FROM api_sessions WHERE token = ?", (token,))
        conn.commit()


def delete_player_account(player_id: int) -> None:
    pid = int(player_id)
    with _connect() as conn:
        _init_db(conn)
        conn.execute("DELETE FROM api_sessions WHERE player_id = ?", (pid,))
        conn.execute("DELETE FROM link_codes WHERE player_id = ?", (pid,))
        conn.execute("DELETE FROM device_tokens WHERE player_id = ?", (pid,))
        conn.execute("DELETE FROM identities WHERE player_id = ?", (pid,))
        conn.execute("DELETE FROM players WHERE id = ?", (pid,))
        conn.commit()


def create_link_code(player_id: int, direction: str, ttl_seconds: int = 600) -> str:
    import secrets
    import string

    alphabet = string.ascii_uppercase + string.digits
    code = "".join(secrets.choice(alphabet) for _ in range(8))
    now = datetime.now()
    expires = (now + timedelta(seconds=ttl_seconds)).strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            INSERT INTO link_codes (code, player_id, direction, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                code,
                int(player_id),
                direction,
                expires,
                now.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()
    return code


def consume_link_code(code: str, direction: str) -> Optional[int]:
    raw = (code or "").strip().upper()
    if not raw:
        return None
    now = _now_sql()
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            """
            SELECT player_id, expires_at FROM link_codes
            WHERE code = ? AND direction = ?
            """,
            (raw, direction),
        ).fetchone()
        if not row:
            return None
        if str(row["expires_at"]) < now:
            conn.execute("DELETE FROM link_codes WHERE code = ?", (raw,))
            conn.commit()
            return None
        player_id = int(row["player_id"])
        conn.execute("DELETE FROM link_codes WHERE code = ?", (raw,))
        conn.commit()
    return player_id


def save_device_token(player_id: int, token: str) -> None:
    value = (token or "").strip()
    if not value:
        return
    now = _now_sql()
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            INSERT INTO device_tokens (token, player_id, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(token) DO UPDATE SET player_id = excluded.player_id
            """,
            (value, int(player_id), now),
        )
        conn.commit()


def attach_apple_identity(player_id: int, apple_sub: str) -> None:
    subject = (apple_sub or "").strip()
    now = _now_sql()
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            INSERT INTO identities (player_id, provider, subject, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(provider, subject) DO UPDATE SET player_id = excluded.player_id
            """,
            (int(player_id), PROVIDER_APPLE, subject, now),
        )
        conn.commit()


def apple_subject_for(player_id: int) -> Optional[str]:
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            """
            SELECT subject FROM identities
            WHERE player_id = ? AND provider = ?
            """,
            (int(player_id), PROVIDER_APPLE),
        ).fetchone()
    if not row:
        return None
    return str(row["subject"])


def move_apple_identity(from_player_id: int, to_player_id: int) -> None:
    """Пустой iOS (Apple) принимает историю Telegram: apple identity едет на telegram player_id."""
    sub = apple_subject_for(from_player_id)
    if not sub:
        raise ValueError("no apple identity")
    now = _now_sql()
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            "DELETE FROM identities WHERE player_id = ? AND provider = ?",
            (int(from_player_id), PROVIDER_APPLE),
        )
        conn.execute(
            """
            INSERT INTO identities (player_id, provider, subject, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (int(to_player_id), PROVIDER_APPLE, sub, now),
        )
        conn.execute(
            "DELETE FROM api_sessions WHERE player_id = ?", (int(from_player_id),)
        )
        conn.execute("DELETE FROM players WHERE id = ?", (int(from_player_id),))
        conn.commit()


def attach_telegram_identity(player_id: int, telegram_user_id: int) -> None:
    subject = str(int(telegram_user_id))
    now = _now_sql()
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            INSERT INTO identities (player_id, provider, subject, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(provider, subject) DO UPDATE SET player_id = excluded.player_id
            """,
            (int(player_id), PROVIDER_TELEGRAM, subject, now),
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


def get_latest_next_video(user_id: int) -> str:
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            """
            SELECT next_video FROM player_sessions
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return ((row["next_video"] if row else "") or "").strip()


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
    scores: Optional[dict] = None,
    focus: str = "",
    stroke: str = "",
) -> None:
    """Сохраняет краткое резюме, топ-3 и задание на следующее видео."""
    summary, top3, next_video = _extract_report_sections(report, language_code)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scores_json = json.dumps(scores or {}, ensure_ascii=False)

    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            INSERT INTO player_sessions
                (user_id, created_at, summary, top3, next_video, scores, focus, stroke)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                created_at,
                summary,
                top3,
                next_video,
                scores_json,
                focus or "",
                stroke or "",
            ),
        )
        conn.commit()


def get_player_history(user_id: int) -> list[dict]:
    """Возвращает последние MAX_HISTORY_SESSIONS сессий (от старой к новой)."""
    with _connect() as conn:
        _init_db(conn)
        rows = conn.execute(
            """
            SELECT created_at, summary, top3, scores, focus, stroke
            FROM player_sessions
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, MAX_HISTORY_SESSIONS),
        ).fetchall()
    result = []
    for row in reversed(rows):
        item = dict(row)
        raw = item.get("scores") or ""
        try:
            item["scores"] = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            item["scores"] = {}
        result.append(item)
    return result


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
            SELECT level, hand, frequency, experience, coaching, focus,
                   injuries, skipped, updated_at
            FROM player_profiles
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "level": row["level"],
        "hand": row["hand"],
        "frequency": row["frequency"],
        "experience": row["experience"],
        "coaching": row["coaching"],
        "focus": row["focus"],
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
                (user_id, level, hand, frequency, experience, coaching,
                 focus, injuries, skipped, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                level = excluded.level,
                hand = excluded.hand,
                frequency = excluded.frequency,
                experience = excluded.experience,
                coaching = excluded.coaching,
                focus = excluded.focus,
                injuries = excluded.injuries,
                skipped = excluded.skipped,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                profile.get("level"),
                profile.get("hand"),
                profile.get("frequency"),
                profile.get("experience"),
                profile.get("coaching"),
                profile.get("focus"),
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
            "hand": None,
            "frequency": None,
            "experience": None,
            "coaching": None,
            "focus": None,
            "injuries": "",
            "skipped": True,
        },
    )


def reset_player_data(user_id: int) -> None:
    """Удаляет профиль и историю разборов — как для нового пользователя."""
    cancel_active_practice_plans(user_id)
    with _connect() as conn:
        _init_db(conn)
        conn.execute("DELETE FROM player_profiles WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM player_sessions WHERE user_id = ?", (user_id,))
        conn.execute(
            """
            UPDATE users SET
                reminder_sent_at = NULL,
                last_analysis_at = NULL
            WHERE user_id = ?
            """,
            (user_id,),
        )
        conn.commit()


def upsert_user(
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
    language_code: Optional[str],
) -> int:
    """user_id здесь — Telegram id. Возвращает player_id."""
    player_id = get_or_create_telegram_player(user_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        existing = conn.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (player_id,),
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
                (username, first_name, last_name, language_code, now, player_id),
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
                    player_id,
                    username,
                    first_name,
                    last_name,
                    language_code,
                    now,
                    now,
                ),
            )
        conn.commit()
    return player_id


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
        "usage": get_usage_summary(30),
        "retention": get_retention_cohorts(8),
        "coach_evals": get_coach_eval_stats(),
    }


def get_daly_summary() -> dict:
    """Короткая ежедневная сводка: разборы, активность, возвраты."""
    from analytics import EVENT_VIDEO_SENT

    def _count(conn, sql, params=()):
        return int(conn.execute(sql, params).fetchone()[0])

    with _connect() as conn:
        _init_db(conn)
        users_with_analysis = _count(
            conn, "SELECT COUNT(DISTINCT user_id) FROM player_sessions"
        )
        users_2plus = _count(
            conn,
            """
            SELECT COUNT(*) FROM (
                SELECT user_id FROM player_sessions
                GROUP BY user_id
                HAVING COUNT(*) >= 2
            )
            """,
        )
        new_analyzers_today = _count(
            conn,
            """
            SELECT COUNT(*) FROM (
                SELECT user_id, MIN(created_at) AS first_at
                FROM player_sessions
                GROUP BY user_id
                HAVING date(first_at) = date('now')
            )
            """,
        )
        active_7d = _count(
            conn,
            """
            SELECT COUNT(*) FROM users
            WHERE datetime(last_seen_at) >= datetime('now', '-7 days')
            """,
        )
        active_30d = _count(
            conn,
            """
            SELECT COUNT(*) FROM users
            WHERE datetime(last_seen_at) >= datetime('now', '-30 days')
            """,
        )

        def _events(window_sql: str, params=()) -> int:
            return _count(
                conn,
                f"""
                SELECT COUNT(*) FROM events
                WHERE event_type = ?
                  AND {window_sql}
                """,
                (EVENT_VIDEO_SENT, *params),
            )

        def _sessions(window_sql: str, params=()) -> int:
            return _count(
                conn,
                f"SELECT COUNT(*) FROM player_sessions WHERE {window_sql}",
                params,
            )

        def _returned(days: int) -> int:
            bound = f"-{days} days"
            return _count(
                conn,
                """
                SELECT COUNT(DISTINCT s.user_id)
                FROM player_sessions s
                WHERE datetime(s.created_at) >= datetime('now', ?)
                  AND EXISTS (
                    SELECT 1 FROM player_sessions prev
                    WHERE prev.user_id = s.user_id
                      AND datetime(prev.created_at) < datetime('now', ?)
                  )
                """,
                (bound, bound),
            )

        videos_today = _events("date(created_at) = date('now')")
        videos_7d = _events("datetime(created_at) >= datetime('now', '-7 days')")
        videos_total = _events("1=1")
        analyses_today = _sessions("date(created_at) = date('now')")
        analyses_7d = _sessions("datetime(created_at) >= datetime('now', '-7 days')")
        analyses_total = _sessions("1=1")
        returned_7d = _returned(7)
        returned_30d = _returned(30)

    return {
        "users_with_analysis": users_with_analysis,
        "new_analyzers_today": new_analyzers_today,
        "users_2plus": users_2plus,
        "active_7d": active_7d,
        "active_30d": active_30d,
        "videos_today": videos_today,
        "videos_7d": videos_7d,
        "videos_total": videos_total,
        "analyses_today": analyses_today,
        "analyses_7d": analyses_7d,
        "analyses_total": analyses_total,
        "returned_7d": returned_7d,
        "returned_30d": returned_30d,
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
        hand=profile_value_label(ui_lang, "hand", profile.get("hand")),
        frequency=profile_value_label(ui_lang, "frequency", profile.get("frequency")),
        experience=profile_value_label(
            ui_lang, "experience", profile.get("experience")
        ),
        coaching=profile_value_label(ui_lang, "coaching", profile.get("coaching")),
        focus=profile_value_label(ui_lang, "focus", profile.get("focus")),
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
    """Пользователи для напоминания: N дней без взаимодействия с ботом.

    Пропускает тех, у кого активна цепочка practice_plans или недавно
    ответили на post check-in (чтобы не дублировать 7-дневный remind).
    """
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
              AND NOT EXISTS (
                  SELECT 1 FROM practice_plans pp
                  WHERE pp.user_id = u.user_id
                    AND (
                        pp.status IN (
                            'awaiting_date', 'scheduled', 'pre_done', 'snoozed'
                        )
                        OR (
                            pp.status = 'checked_in'
                            AND datetime(pp.post_sent_at) >= datetime('now', '-7 days')
                        )
                    )
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


def get_users_for_no_video_survey(hours: int = 24) -> list[dict]:
    """Онбординг завершён ≥N часов назад, видео не отправляли, опрос ещё не слали."""
    with _connect() as conn:
        _init_db(conn)
        rows = conn.execute(
            """
            SELECT u.user_id, u.language_code
            FROM users u
            INNER JOIN player_profiles pp ON pp.user_id = u.user_id
            WHERE u.no_video_survey_sent_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM events ev
                  WHERE ev.user_id = u.user_id
                    AND ev.event_type = 'video_sent'
              )
              AND (
                  SELECT MAX(datetime(e.created_at))
                  FROM events e
                  WHERE e.user_id = u.user_id
                    AND e.event_type IN (
                        'onboarding_completed', 'onboarding_skipped'
                    )
              ) <= datetime('now', ?)
            """,
            (f"-{hours} hours",),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_no_video_survey_sent(user_id: int) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            "UPDATE users SET no_video_survey_sent_at = ? WHERE user_id = ?",
            (now, user_id),
        )
        conn.commit()


def get_users_for_no_onboarding_survey(hours: int = 24) -> list[dict]:
    """/start и onboarding_started ≥N часов назад, онбординг не завершён."""
    with _connect() as conn:
        _init_db(conn)
        rows = conn.execute(
            """
            SELECT u.user_id, u.language_code
            FROM users u
            WHERE u.no_onboarding_survey_sent_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM player_profiles pp
                  WHERE pp.user_id = u.user_id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM events e
                  WHERE e.user_id = u.user_id
                    AND e.event_type IN (
                        'onboarding_completed', 'onboarding_skipped'
                    )
              )
              AND (
                  SELECT MAX(datetime(e.created_at))
                  FROM events e
                  WHERE e.user_id = u.user_id
                    AND e.event_type = 'onboarding_started'
              ) <= datetime('now', ?)
            """,
            (f"-{hours} hours",),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_no_onboarding_survey_sent(user_id: int) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            "UPDATE users SET no_onboarding_survey_sent_at = ? WHERE user_id = ?",
            (now, user_id),
        )
        conn.commit()


def save_survey_response(
    user_id: int,
    survey_type: str,
    selected: list[str],
    *,
    other_text: str = "",
    source: str = "auto",
) -> None:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            INSERT INTO survey_responses
                (user_id, survey_type, selected, other_text, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                survey_type,
                json.dumps(selected, ensure_ascii=False),
                other_text or "",
                source,
                created_at,
            ),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Usage / cost telemetry
# ---------------------------------------------------------------------------


def log_usage(
    user_id: int,
    kind: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    thinking_tokens: int = 0,
    video_seconds: Optional[float] = None,
    cost_usd: float = 0.0,
) -> None:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            INSERT INTO usage_log
                (user_id, kind, model, input_tokens, output_tokens,
                 thinking_tokens, video_seconds, cost_usd, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                kind,
                model,
                int(input_tokens or 0),
                int(output_tokens or 0),
                int(thinking_tokens or 0),
                video_seconds,
                float(cost_usd or 0.0),
                created_at,
            ),
        )
        conn.commit()


def get_usage_summary(days: int = 30) -> dict:
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS calls,
                COALESCE(SUM(CASE WHEN kind = 'analyze' THEN 1 ELSE 0 END), 0)
                    AS analyses,
                COALESCE(SUM(input_tokens), 0) AS input_tokens,
                COALESCE(SUM(output_tokens), 0) AS output_tokens,
                COALESCE(SUM(thinking_tokens), 0) AS thinking_tokens,
                COALESCE(SUM(cost_usd), 0) AS cost_usd,
                COUNT(DISTINCT user_id) AS active_users
            FROM usage_log
            WHERE datetime(created_at) >= datetime('now', ?)
            """,
            (f"-{days} days",),
        ).fetchone()
    analyses = int(row["analyses"] or 0)
    cost = float(row["cost_usd"] or 0.0)
    users = int(row["active_users"] or 0)
    return {
        "days": days,
        "calls": int(row["calls"] or 0),
        "analyses": analyses,
        "input_tokens": int(row["input_tokens"] or 0),
        "output_tokens": int(row["output_tokens"] or 0),
        "thinking_tokens": int(row["thinking_tokens"] or 0),
        "cost_usd": cost,
        "active_users": users,
        "avg_cost_per_analysis": (cost / analyses) if analyses else 0.0,
        "cost_per_active_user": (cost / users) if users else 0.0,
        "avg_input_tokens": (
            int(row["input_tokens"] or 0) / analyses if analyses else 0
        ),
        "avg_output_tokens": (
            (int(row["output_tokens"] or 0) + int(row["thinking_tokens"] or 0))
            / analyses
            if analyses
            else 0
        ),
    }


# ---------------------------------------------------------------------------
# Active dialog sessions (survives process restart)
# ---------------------------------------------------------------------------


def save_active_session(user_id: int, payload: dict) -> None:
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            INSERT INTO active_sessions (user_id, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (user_id, json.dumps(payload, ensure_ascii=False), updated_at),
        )
        conn.commit()


def load_active_session(user_id: int) -> Optional[dict]:
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            """
            SELECT payload, updated_at FROM active_sessions WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return None
    try:
        updated = datetime.strptime(row["updated_at"], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        updated = datetime.now()
    if datetime.now() - updated > timedelta(days=ACTIVE_SESSION_TTL_DAYS):
        clear_active_session(user_id)
        return None
    try:
        return json.loads(row["payload"])
    except json.JSONDecodeError:
        return None


def clear_active_session(user_id: int) -> None:
    with _connect() as conn:
        _init_db(conn)
        conn.execute("DELETE FROM active_sessions WHERE user_id = ?", (user_id,))
        conn.commit()


# ---------------------------------------------------------------------------
# Focus of the week
# ---------------------------------------------------------------------------


def set_player_focus(
    user_id: int,
    focus: str,
    stroke: Optional[str] = None,
    days: int = 7,
) -> None:
    set_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    expires_at = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            INSERT INTO player_focus (user_id, focus, stroke, set_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                focus = excluded.focus,
                stroke = excluded.stroke,
                set_at = excluded.set_at,
                expires_at = excluded.expires_at
            """,
            (user_id, focus, stroke, set_at, expires_at),
        )
        conn.commit()


def get_player_focus(user_id: int) -> Optional[dict]:
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            "SELECT focus, stroke, set_at, expires_at FROM player_focus WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return None
    if row["expires_at"]:
        try:
            if (
                datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
                < datetime.now()
            ):
                clear_player_focus(user_id)
                return None
        except ValueError:
            pass
    return dict(row)


def clear_player_focus(user_id: int) -> None:
    with _connect() as conn:
        _init_db(conn)
        conn.execute("DELETE FROM player_focus WHERE user_id = ?", (user_id,))
        conn.commit()


def get_progress_scores(user_id: int, days: int = 90) -> list[dict]:
    with _connect() as conn:
        _init_db(conn)
        rows = conn.execute(
            """
            SELECT created_at, scores, focus, stroke
            FROM player_sessions
            WHERE user_id = ?
              AND datetime(created_at) >= datetime('now', ?)
              AND scores != ''
            ORDER BY id ASC
            """,
            (user_id, f"-{days} days"),
        ).fetchall()
    result = []
    for row in rows:
        try:
            scores = json.loads(row["scores"] or "{}")
        except json.JSONDecodeError:
            scores = {}
        if not scores:
            continue
        result.append(
            {
                "created_at": row["created_at"],
                "scores": scores,
                "focus": row["focus"] or "",
                "stroke": row["stroke"] or "",
            }
        )
    return result


# ---------------------------------------------------------------------------
# Drills catalog
# ---------------------------------------------------------------------------


def upsert_drill(
    drill_id: str,
    title: str,
    description: str = "",
    tags: Optional[list] = None,
    telegram_file_id: Optional[str] = None,
    language: str = "ru",
) -> None:
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            INSERT INTO drills (id, title, description, tags, telegram_file_id, language)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                tags = excluded.tags,
                telegram_file_id = COALESCE(excluded.telegram_file_id, drills.telegram_file_id),
                language = excluded.language
            """,
            (
                drill_id,
                title,
                description,
                json.dumps(tags or [], ensure_ascii=False),
                telegram_file_id,
                language,
            ),
        )
        conn.commit()


def list_drills(language: Optional[str] = None) -> list[dict]:
    with _connect() as conn:
        _init_db(conn)
        if language:
            rows = conn.execute(
                "SELECT * FROM drills WHERE language = ? ORDER BY id",
                (language,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM drills ORDER BY id").fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["tags"] = json.loads(item.get("tags") or "[]")
        except json.JSONDecodeError:
            item["tags"] = []
        result.append(item)
    return result


def get_drill(drill_id: str) -> Optional[dict]:
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute("SELECT * FROM drills WHERE id = ?", (drill_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    try:
        item["tags"] = json.loads(item.get("tags") or "[]")
    except json.JSONDecodeError:
        item["tags"] = []
    return item


def count_analyses_in_period(user_id: int, since: datetime) -> int:
    since_s = since.strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        return conn.execute(
            """
            SELECT COUNT(*) FROM player_sessions
            WHERE user_id = ? AND datetime(created_at) >= datetime(?)
            """,
            (user_id, since_s),
        ).fetchone()[0]


def get_retention_cohorts(max_cohorts: int = 8) -> list[dict]:
    """D1/D7/D30 по когортам first_seen (неделя)."""
    with _connect() as conn:
        _init_db(conn)
        cohorts = conn.execute(
            """
            SELECT strftime('%Y-%W', first_seen_at) AS cohort,
                   COUNT(*) AS size
            FROM users
            WHERE first_seen_at IS NOT NULL
            GROUP BY cohort
            ORDER BY cohort DESC
            LIMIT ?
            """,
            (max_cohorts,),
        ).fetchall()
        result = []
        for c in cohorts:
            cohort = c["cohort"]
            size = int(c["size"])
            if size == 0:
                continue

            def _retained(days: int, cohort_key: str = cohort) -> int:
                return conn.execute(
                    """
                    SELECT COUNT(DISTINCT u.user_id)
                    FROM users u
                    JOIN events e ON e.user_id = u.user_id
                    WHERE strftime('%Y-%W', u.first_seen_at) = ?
                      AND e.event_type IN ('video_sent', 'analysis_success')
                      AND julianday(e.created_at) - julianday(u.first_seen_at)
                          BETWEEN ? AND ?
                    """,
                    (cohort_key, days - 0.5, days + 1.5),
                ).fetchone()[0]

            d1 = _retained(1)
            d7 = _retained(7)
            d30 = _retained(30)
            result.append(
                {
                    "cohort": cohort,
                    "size": size,
                    "d1": d1,
                    "d7": d7,
                    "d30": d30,
                    "d1_pct": round(100 * d1 / size) if size else 0,
                    "d7_pct": round(100 * d7 / size) if size else 0,
                    "d30_pct": round(100 * d30 / size) if size else 0,
                }
            )
    return list(reversed(result))


def get_users_for_digest() -> list[dict]:
    """Пользователи с активностью за 14 дней, без дайджеста за последние 6 дней."""
    with _connect() as conn:
        _init_db(conn)
        rows = conn.execute(
            """
            SELECT
                u.user_id,
                u.language_code,
                COALESCE(u.streak_weeks, 0) AS streak_weeks,
                (
                    SELECT COUNT(*) FROM player_sessions s
                    WHERE s.user_id = u.user_id
                      AND datetime(s.created_at) >= datetime('now', '-7 days')
                ) AS analyses_week
            FROM users u
            WHERE datetime(u.last_seen_at) >= datetime('now', '-14 days')
              AND (
                  u.digest_sent_at IS NULL
                  OR datetime(u.digest_sent_at) < datetime('now', '-6 days')
              )
            """
        ).fetchall()
    return [dict(r) for r in rows]


def mark_digest_sent(user_id: int, had_analysis: bool) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        if had_analysis:
            conn.execute(
                """
                UPDATE users
                SET digest_sent_at = ?,
                    streak_weeks = COALESCE(streak_weeks, 0) + 1
                WHERE user_id = ?
                """,
                (now, user_id),
            )
        else:
            conn.execute(
                """
                UPDATE users
                SET digest_sent_at = ?, streak_weeks = 0
                WHERE user_id = ?
                """,
                (now, user_id),
            )
        conn.commit()


# ---------------------------------------------------------------------------
# Practice plans (возврат вокруг следующей тренировки)
# ---------------------------------------------------------------------------

_ACTIVE_PRACTICE_STATUSES = (
    "awaiting_date",
    "scheduled",
    "pre_done",
    "snoozed",
)


def cancel_active_practice_plans(user_id: int) -> None:
    with _connect() as conn:
        _init_db(conn)
        placeholders = ",".join("?" * len(_ACTIVE_PRACTICE_STATUSES))
        conn.execute(
            f"""
            UPDATE practice_plans
            SET status = 'cancelled'
            WHERE user_id = ? AND status IN ({placeholders})
            """,
            (user_id, *_ACTIVE_PRACTICE_STATUSES),
        )
        conn.commit()


def create_practice_plan(
    user_id: int,
    focus_text: str = "",
    drill_text: str = "",
    drill_id: Optional[str] = None,
) -> int:
    """Создаёт новую цепочку; предыдущие активные закрывает."""
    cancel_active_practice_plans(user_id)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        cur = conn.execute(
            """
            INSERT INTO practice_plans
                (user_id, created_at, focus_text, drill_text, drill_id, status)
            VALUES (?, ?, ?, ?, ?, 'awaiting_date')
            """,
            (
                user_id,
                created_at,
                (focus_text or "").strip(),
                (drill_text or "").strip(),
                drill_id,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_active_practice_plan(user_id: int) -> Optional[dict]:
    with _connect() as conn:
        _init_db(conn)
        placeholders = ",".join("?" * len(_ACTIVE_PRACTICE_STATUSES))
        row = conn.execute(
            f"""
            SELECT * FROM practice_plans
            WHERE user_id = ? AND status IN ({placeholders})
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id, *_ACTIVE_PRACTICE_STATUSES),
        ).fetchone()
    return dict(row) if row else None


def get_practice_plan(plan_id: int) -> Optional[dict]:
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            "SELECT * FROM practice_plans WHERE id = ?", (plan_id,)
        ).fetchone()
    return dict(row) if row else None


def set_practice_date(
    plan_id: int,
    practice_on: Optional[str],
    *,
    skip_pre: bool = False,
) -> None:
    """practice_on — YYYY-MM-DD или None (не должно вызываться для unknown без даты)."""
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            UPDATE practice_plans
            SET next_practice_on = ?,
                status = 'scheduled',
                skip_pre = ?,
                pre_sent_at = NULL,
                post_sent_at = NULL,
                post_answer = NULL
            WHERE id = ?
            """,
            (practice_on, 1 if skip_pre else 0, plan_id),
        )
        conn.commit()


def mark_practice_pre_sent(plan_id: int) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            UPDATE practice_plans
            SET pre_sent_at = ?, status = 'pre_done'
            WHERE id = ?
            """,
            (now, plan_id),
        )
        conn.commit()


def mark_practice_post_sent(plan_id: int) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            UPDATE practice_plans
            SET post_sent_at = ?
            WHERE id = ?
            """,
            (now, plan_id),
        )
        conn.commit()


def set_practice_post_answer(plan_id: int, answer: str) -> None:
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            UPDATE practice_plans
            SET post_answer = ?, status = 'checked_in'
            WHERE id = ?
            """,
            (answer, plan_id),
        )
        conn.commit()


def snooze_practice_plan(user_id: int, days: int = 7) -> None:
    mute_until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    plan = get_active_practice_plan(user_id)
    if not plan:
        return
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            UPDATE practice_plans
            SET status = 'snoozed', mute_until = ?
            WHERE id = ?
            """,
            (mute_until, plan["id"]),
        )
        conn.commit()


def auto_schedule_stale_practice_plans(today: str) -> int:
    """Если юзер не ответил на «когда тренировка?» >1 дня — fallback на сегодня, без pre."""
    with _connect() as conn:
        _init_db(conn)
        cur = conn.execute(
            """
            UPDATE practice_plans
            SET next_practice_on = ?,
                status = 'scheduled',
                skip_pre = 1
            WHERE status = 'awaiting_date'
              AND date(created_at) < date(?)
            """,
            (today, today),
        )
        conn.commit()
        return int(cur.rowcount or 0)


def list_due_practice_pre(practice_on: str) -> list[dict]:
    """Планы, которым пора отправить pre-nudge (дата тренировки = practice_on)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        rows = conn.execute(
            """
            SELECT pp.*, u.language_code
            FROM practice_plans pp
            LEFT JOIN users u ON u.user_id = pp.user_id
            WHERE pp.status = 'scheduled'
              AND pp.skip_pre = 0
              AND pp.next_practice_on = ?
              AND pp.pre_sent_at IS NULL
              AND (pp.mute_until IS NULL OR datetime(pp.mute_until) <= datetime(?))
            """,
            (practice_on, now),
        ).fetchall()
    return [dict(r) for r in rows]


def list_due_practice_post(practice_on: str) -> list[dict]:
    """Планы, которым пора отправить post check-in."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        rows = conn.execute(
            """
            SELECT pp.*, u.language_code
            FROM practice_plans pp
            LEFT JOIN users u ON u.user_id = pp.user_id
            WHERE pp.status IN ('scheduled', 'pre_done')
              AND pp.next_practice_on = ?
              AND pp.post_sent_at IS NULL
              AND (pp.mute_until IS NULL OR datetime(pp.mute_until) <= datetime(?))
            """,
            (practice_on, now),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Coach review jobs (Product V2)
# ---------------------------------------------------------------------------

_OPEN_REVIEW_STATUSES = ("queued", "in_review")
# Списки канала игрока. Не для cancel: новый клип в боте не должен
# снимать уже отданный игроку AI-разбор.
_PLAYER_OPEN_STATUSES = ("queued", "in_review", "ai_sent")
_PLAYER_HISTORY_STATUSES = ("ai_sent", "sent_coach", "sent_fallback")


def get_player_forum_topic(user_id: int, forum_chat_id: int) -> Optional[dict]:
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            """
            SELECT * FROM player_forum_topics
            WHERE user_id = ? AND forum_chat_id = ?
            """,
            (user_id, forum_chat_id),
        ).fetchone()
    return dict(row) if row else None


def get_player_by_forum_thread(
    forum_chat_id: int, message_thread_id: int
) -> Optional[dict]:
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            """
            SELECT * FROM player_forum_topics
            WHERE forum_chat_id = ? AND message_thread_id = ?
            """,
            (forum_chat_id, message_thread_id),
        ).fetchone()
    return dict(row) if row else None


def get_user_language_code(user_id: int) -> str:
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            "SELECT language_code FROM users WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    return (row["language_code"] if row else "") or ""


def save_player_forum_topic(
    user_id: int,
    forum_chat_id: int,
    message_thread_id: int,
    title: str = "",
) -> None:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            INSERT INTO player_forum_topics
                (user_id, forum_chat_id, message_thread_id, title, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                forum_chat_id = excluded.forum_chat_id,
                message_thread_id = excluded.message_thread_id,
                title = excluded.title
            """,
            (user_id, forum_chat_id, message_thread_id, title, created_at),
        )
        conn.commit()


def cancel_open_review_jobs(
    user_id: int, source_channel: str = CHANNEL_TELEGRAM
) -> None:
    with _connect() as conn:
        _init_db(conn)
        placeholders = ",".join("?" * len(_OPEN_REVIEW_STATUSES))
        conn.execute(
            f"""
            UPDATE review_jobs
            SET status = 'cancelled'
            WHERE user_id = ?
              AND status IN ({placeholders})
              AND COALESCE(source_channel, ?) = ?
            """,
            (
                user_id,
                *_OPEN_REVIEW_STATUSES,
                CHANNEL_TELEGRAM,
                source_channel,
            ),
        )
        conn.commit()


def create_review_job(
    user_id: int,
    *,
    video_file_id: str,
    video_mime: str = "video/mp4",
    language_code: str = "ru",
    draft_text: str = "",
    focus_text: str = "",
    drill_text: str = "",
    drill_id: Optional[str] = None,
    scores: Optional[dict] = None,
    stroke: str = "",
    reviewer_id: Optional[int] = None,
    source_channel: str = CHANNEL_TELEGRAM,
) -> int:
    if source_channel == CHANNEL_TELEGRAM:
        cancel_open_review_jobs(user_id, CHANNEL_TELEGRAM)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scores_json = json.dumps(scores or {}, ensure_ascii=False)
    with _connect() as conn:
        _init_db(conn)
        cur = conn.execute(
            """
            INSERT INTO review_jobs (
                user_id, reviewer_id, created_at, status,
                video_file_id, video_mime, language_code, draft_text,
                focus_text, drill_text, drill_id, scores_json, stroke,
                source_channel
            ) VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                reviewer_id,
                created_at,
                video_file_id,
                video_mime,
                language_code,
                draft_text,
                (focus_text or "").strip(),
                (drill_text or "").strip(),
                drill_id,
                scores_json,
                stroke or "",
                source_channel,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_review_job(job_id: int) -> Optional[dict]:
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            "SELECT * FROM review_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    return dict(row) if row else None


def list_player_jobs(player_id: int, *, open_only: bool = False) -> list:
    pid = int(player_id)
    with _connect() as conn:
        _init_db(conn)
        if open_only:
            statuses = _PLAYER_OPEN_STATUSES
        else:
            statuses = _PLAYER_HISTORY_STATUSES
        placeholders = ",".join("?" * len(statuses))
        rows = conn.execute(
            f"""
            SELECT * FROM review_jobs
            WHERE user_id = ? AND status IN ({placeholders})
            ORDER BY id DESC
            """,
            (pid, *statuses),
        ).fetchall()
    return [dict(r) for r in rows]


def get_open_review_job(user_id: int) -> Optional[dict]:
    with _connect() as conn:
        _init_db(conn)
        placeholders = ",".join("?" * len(_OPEN_REVIEW_STATUSES))
        row = conn.execute(
            f"""
            SELECT * FROM review_jobs
            WHERE user_id = ? AND status IN ({placeholders})
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id, *_OPEN_REVIEW_STATUSES),
        ).fetchone()
    return dict(row) if row else None


def get_open_review_by_thread(
    forum_chat_id: int, message_thread_id: int
) -> Optional[dict]:
    with _connect() as conn:
        _init_db(conn)
        placeholders = ",".join("?" * len(_OPEN_REVIEW_STATUSES))
        row = conn.execute(
            f"""
            SELECT * FROM review_jobs
            WHERE forum_chat_id = ?
              AND message_thread_id = ?
              AND status IN ({placeholders})
            ORDER BY id DESC
            LIMIT 1
            """,
            (forum_chat_id, message_thread_id, *_OPEN_REVIEW_STATUSES),
        ).fetchone()
    return dict(row) if row else None


def update_review_job(job_id: int, **fields) -> None:
    if not fields:
        return
    allowed = {
        "status",
        "reviewer_id",
        "final_text",
        "coach_notes",
        "forum_chat_id",
        "message_thread_id",
        "pending_coach_action",
        "sent_at",
        "draft_text",
    }
    cols = []
    values = []
    for key, value in fields.items():
        if key not in allowed:
            raise ValueError(f"unsupported review_jobs field: {key}")
        cols.append(f"{key} = ?")
        values.append(value)
    values.append(job_id)
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            f"UPDATE review_jobs SET {', '.join(cols)} WHERE id = ?",
            values,
        )
        conn.commit()


def list_review_jobs_for_fallback(hours: int = 24) -> list[dict]:
    with _connect() as conn:
        _init_db(conn)
        rows = conn.execute(
            """
            SELECT * FROM review_jobs
            WHERE status IN ('queued', 'in_review')
              AND datetime(created_at) <= datetime('now', ?)
            ORDER BY id ASC
            """,
            (f"-{hours} hours",),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_review_sent(
    job_id: int,
    *,
    status: str,
    final_text: str,
    coach_notes: str = "",
) -> None:
    sent_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    update_review_job(
        job_id,
        status=status,
        final_text=final_text,
        coach_notes=coach_notes or "",
        pending_coach_action=None,
        sent_at=sent_at,
    )


_MAX_COACH_DELTA_CHARS = 8000


def _parse_eval_tags(raw: str) -> list:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data if item]


def _eval_from_row(row) -> dict:
    item = dict(row)
    item["tags"] = _parse_eval_tags(item.get("tags_json") or "[]")
    return item


def get_latest_review_job_for_thread(
    forum_chat_id: int, message_thread_id: int
) -> Optional[dict]:
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            """
            SELECT * FROM review_jobs
            WHERE forum_chat_id = ?
              AND message_thread_id = ?
              AND status != 'cancelled'
            ORDER BY id DESC
            LIMIT 1
            """,
            (forum_chat_id, message_thread_id),
        ).fetchone()
    return dict(row) if row else None


def get_pending_review_job_for_thread(
    forum_chat_id: int, message_thread_id: int
) -> Optional[dict]:
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            """
            SELECT * FROM review_jobs
            WHERE forum_chat_id = ?
              AND message_thread_id = ?
              AND status != 'cancelled'
              AND pending_coach_action IS NOT NULL
              AND TRIM(pending_coach_action) != ''
            ORDER BY id DESC
            LIMIT 1
            """,
            (forum_chat_id, message_thread_id),
        ).fetchone()
    return dict(row) if row else None


def set_pending_coach_action(job_id: int, action: Optional[str]) -> None:
    job = get_review_job(job_id)
    if not job:
        return
    forum_chat_id = job.get("forum_chat_id")
    thread_id = job.get("message_thread_id")
    with _connect() as conn:
        _init_db(conn)
        if forum_chat_id and thread_id:
            conn.execute(
                """
                UPDATE review_jobs
                SET pending_coach_action = NULL
                WHERE forum_chat_id = ? AND message_thread_id = ?
                """,
                (forum_chat_id, thread_id),
            )
        conn.execute(
            "UPDATE review_jobs SET pending_coach_action = ? WHERE id = ?",
            (action, job_id),
        )
        conn.commit()


def get_coach_evaluation(job_id: int) -> Optional[dict]:
    with _connect() as conn:
        _init_db(conn)
        row = conn.execute(
            "SELECT * FROM coach_evaluations WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    return _eval_from_row(row) if row else None


def upsert_coach_evaluation(
    job_id: int,
    *,
    player_id: int,
    coach_user_id: int,
    rating: Optional[str] = None,
    tags: Optional[list] = None,
    delta_text: Optional[str] = None,
) -> dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    existing = get_coach_evaluation(job_id)
    next_rating = (
        rating if rating is not None else (existing["rating"] if existing else "")
    )
    next_tags = tags if tags is not None else (existing["tags"] if existing else [])
    next_delta = (
        delta_text
        if delta_text is not None
        else (existing["delta_text"] if existing else "")
    )
    tags_json = json.dumps(next_tags, ensure_ascii=False)
    with _connect() as conn:
        _init_db(conn)
        conn.execute(
            """
            INSERT INTO coach_evaluations (
                job_id, player_id, coach_user_id, rating, tags_json,
                delta_text, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                player_id = excluded.player_id,
                coach_user_id = excluded.coach_user_id,
                rating = excluded.rating,
                tags_json = excluded.tags_json,
                delta_text = excluded.delta_text,
                updated_at = excluded.updated_at
            """,
            (
                job_id,
                player_id,
                coach_user_id,
                next_rating or "",
                tags_json,
                next_delta or "",
                existing["created_at"] if existing else now,
                now,
            ),
        )
        conn.commit()
    saved = get_coach_evaluation(job_id)
    assert saved is not None
    return saved


def append_coach_eval_delta(
    job_id: int,
    text: str,
    *,
    player_id: int,
    coach_user_id: int,
) -> Optional[dict]:
    chunk = (text or "").strip()
    if not chunk:
        return get_coach_evaluation(job_id)
    existing = get_coach_evaluation(job_id)
    previous = (existing["delta_text"] if existing else "") or ""
    merged = f"{previous}\n\n{chunk}".strip() if previous else chunk
    if len(merged) > _MAX_COACH_DELTA_CHARS:
        merged = merged[-_MAX_COACH_DELTA_CHARS:]
    return upsert_coach_evaluation(
        job_id,
        player_id=player_id,
        coach_user_id=coach_user_id,
        delta_text=merged,
    )


def save_coach_correction(
    job_id: int,
    text: str,
    *,
    player_id: int,
    coach_user_id: int,
    append: bool = False,
) -> Optional[dict]:
    chunk = (text or "").strip()
    if not chunk:
        return get_coach_evaluation(job_id)
    if append:
        return append_coach_eval_delta(
            job_id,
            chunk,
            player_id=player_id,
            coach_user_id=coach_user_id,
        )
    if len(chunk) > _MAX_COACH_DELTA_CHARS:
        chunk = chunk[-_MAX_COACH_DELTA_CHARS:]
    return upsert_coach_evaluation(
        job_id,
        player_id=player_id,
        coach_user_id=coach_user_id,
        delta_text=chunk,
    )


def get_coach_corrections_for_player(player_id: int, limit: int = 2) -> list[dict]:
    """Последние эталоны тренера для игрока: черновик ИИ + исправленный текст."""
    n = max(1, min(int(limit), 5))
    with _connect() as conn:
        _init_db(conn)
        rows = conn.execute(
            """
            SELECT
                e.job_id,
                e.delta_text,
                e.updated_at,
                j.draft_text
            FROM coach_evaluations e
            JOIN review_jobs j ON j.id = e.job_id
            WHERE e.player_id = ?
              AND TRIM(e.delta_text) != ''
            ORDER BY e.updated_at DESC, e.job_id DESC
            LIMIT ?
            """,
            (player_id, n),
        ).fetchall()
    return [dict(row) for row in rows]


def get_coach_corrections_global(
    limit: int = 4, exclude_job_ids: Optional[set] = None
) -> list[dict]:
    """Последние эталоны тренера по всем игрокам — дом.стиль штатного тренера."""
    n = max(1, min(int(limit), 8))
    excluded = [int(x) for x in (exclude_job_ids or []) if x is not None]
    with _connect() as conn:
        _init_db(conn)
        if excluded:
            placeholders = ",".join("?" * len(excluded))
            rows = conn.execute(
                f"""
                SELECT
                    e.job_id,
                    e.delta_text,
                    e.updated_at,
                    j.draft_text
                FROM coach_evaluations e
                JOIN review_jobs j ON j.id = e.job_id
                WHERE TRIM(e.delta_text) != ''
                  AND e.job_id NOT IN ({placeholders})
                ORDER BY e.updated_at DESC, e.job_id DESC
                LIMIT ?
                """,
                (*excluded, n),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT
                    e.job_id,
                    e.delta_text,
                    e.updated_at,
                    j.draft_text
                FROM coach_evaluations e
                JOIN review_jobs j ON j.id = e.job_id
                WHERE TRIM(e.delta_text) != ''
                ORDER BY e.updated_at DESC, e.job_id DESC
                LIMIT ?
                """,
                (n,),
            ).fetchall()
    return [dict(row) for row in rows]


def get_coach_approved_drafts(
    limit: int = 3, exclude_job_ids: Optional[set] = None
) -> list[dict]:
    """Черновики AI, которые тренер закрепил кнопкой ОК."""
    n = max(1, min(int(limit), 8))
    excluded = [int(x) for x in (exclude_job_ids or []) if x is not None]
    with _connect() as conn:
        _init_db(conn)
        extra = ""
        params = []
        if excluded:
            extra = f" AND e.job_id NOT IN ({','.join('?' * len(excluded))})"
            params.extend(excluded)
        rows = conn.execute(
            f"""
            SELECT
                e.job_id,
                e.delta_text,
                e.updated_at,
                j.draft_text
            FROM coach_evaluations e
            JOIN review_jobs j ON j.id = e.job_id
            WHERE e.rating = 'ok'
              AND TRIM(COALESCE(e.delta_text, '')) = ''
              AND TRIM(j.draft_text) != ''
              {extra}
            ORDER BY e.updated_at DESC, e.job_id DESC
            LIMIT ?
            """,
            (*params, n),
        ).fetchall()
    return [dict(row) for row in rows]


def get_coach_corrections_for_prompt(
    player_id: Optional[int] = None,
    *,
    player_limit: int = 2,
    global_limit: int = 4,
    approved_limit: int = 3,
) -> list[dict]:
    """Глобальный стиль тренера + персональные правки игрока для system prompt."""
    player_rows = []
    if player_id:
        for row in get_coach_corrections_for_player(int(player_id), limit=player_limit):
            item = dict(row)
            item["scope"] = "player"
            player_rows.append(item)
    seen = {int(row["job_id"]) for row in player_rows if row.get("job_id") is not None}
    global_rows = []
    for row in get_coach_corrections_global(limit=global_limit, exclude_job_ids=seen):
        item = dict(row)
        item["scope"] = "global"
        global_rows.append(item)
        if item.get("job_id") is not None:
            seen.add(int(item["job_id"]))
    approved_rows = []
    for row in get_coach_approved_drafts(limit=approved_limit, exclude_job_ids=seen):
        item = dict(row)
        item["scope"] = "approved"
        approved_rows.append(item)
    return approved_rows + global_rows + player_rows


def get_coach_eval_stats() -> dict:
    with _connect() as conn:
        _init_db(conn)
        rows = conn.execute(
            """
            SELECT rating, COUNT(*) AS n
            FROM coach_evaluations
            WHERE rating != ''
            GROUP BY rating
            """
        ).fetchall()
        rated = {row["rating"]: int(row["n"]) for row in rows}
        with_delta = conn.execute(
            """
            SELECT COUNT(*) FROM coach_evaluations
            WHERE TRIM(delta_text) != ''
            """
        ).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM coach_evaluations").fetchone()[0]
    return {
        "total": int(total),
        "ok": int(rated.get("ok", 0)),
        "added": int(rated.get("added", 0)),
        "miss": int(rated.get("miss", 0)),
        "with_delta": int(with_delta),
    }
