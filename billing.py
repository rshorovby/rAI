"""Тарифы, квоты и подписки (Telegram Stars)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import storage

PLAN_FREE = "free"
PLAN_PRO = "pro"
STATUS_ACTIVE = "active"
STATUS_EXPIRED = "expired"
STATUS_CANCELED = "canceled"

PROVIDER_STARS = "stars"
PROVIDER_WEB = "web"

# Лимиты P0 (подтверждены планом)
FREE_ANALYSES_PER_MONTH = 2
PRO_ANALYSES_PER_MONTH = 30
FREE_MAX_VIDEO_SECONDS = 30
PRO_MAX_VIDEO_SECONDS = 60
GRACE_DAYS = 3
PRO_MONTHS_DEFAULT = 1

# Telegram Stars: ориентир ~$15/мес. 1 Star ≈ $0.013 — около 1150 XTR.
# Ставим округлённо 1000 Stars (~$13) как стартовую цену; правится в .env.
DEFAULT_STARS_PRICE = 1000
STARS_CURRENCY = "XTR"
STARS_PAYLOAD_PREFIX = "rally_pro_month:"


@dataclass(frozen=True)
class PlanInfo:
    plan: str
    status: str
    is_pro: bool
    analyses_limit: int
    analyses_used: int
    analyses_left: int
    max_video_seconds: int
    expires_at: Optional[str]
    period_start: datetime
    reset_at: datetime


def _now() -> datetime:
    return datetime.now()


def _month_start(dt: Optional[datetime] = None) -> datetime:
    d = dt or _now()
    return d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _next_month(dt: datetime) -> datetime:
    if dt.month == 12:
        return dt.replace(year=dt.year + 1, month=1)
    return dt.replace(month=dt.month + 1)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def get_subscription(user_id: int) -> dict:
    with storage._connect() as conn:
        storage._init_db(conn)
        row = conn.execute(
            "SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)
        ).fetchone()
    if not row:
        return {
            "user_id": user_id,
            "plan": PLAN_FREE,
            "status": STATUS_ACTIVE,
            "started_at": None,
            "expires_at": None,
            "provider": None,
            "last_payment_id": None,
        }
    return dict(row)


def is_pro(user_id: int) -> bool:
    sub = get_subscription(user_id)
    if sub.get("plan") != PLAN_PRO or sub.get("status") != STATUS_ACTIVE:
        return False
    expires = _parse_dt(sub.get("expires_at"))
    if expires is None:
        return True
    # grace period
    return _now() <= expires + timedelta(days=GRACE_DAYS)


def get_plan(user_id: int) -> PlanInfo:
    pro = is_pro(user_id)
    sub = get_subscription(user_id)
    period_start = _month_start()
    used = storage.count_analyses_in_period(user_id, period_start)
    limit = PRO_ANALYSES_PER_MONTH if pro else FREE_ANALYSES_PER_MONTH
    left = max(0, limit - used)
    return PlanInfo(
        plan=PLAN_PRO if pro else PLAN_FREE,
        status=sub.get("status") or STATUS_ACTIVE,
        is_pro=pro,
        analyses_limit=limit,
        analyses_used=used,
        analyses_left=left,
        max_video_seconds=PRO_MAX_VIDEO_SECONDS if pro else FREE_MAX_VIDEO_SECONDS,
        expires_at=sub.get("expires_at"),
        period_start=period_start,
        reset_at=_next_month(period_start),
    )


def has_quota(user_id: int) -> bool:
    return get_plan(user_id).analyses_left > 0


def grant_pro(
    user_id: int,
    months: int = PRO_MONTHS_DEFAULT,
    provider: str = PROVIDER_STARS,
    payment_id: Optional[str] = None,
) -> dict:
    """Выдаёт / продлевает Pro. Идемпотентно по payment_id."""
    months = max(1, int(months))
    now = _now()
    with storage._connect() as conn:
        storage._init_db(conn)
        if payment_id:
            existing = conn.execute(
                "SELECT id FROM payments WHERE provider_payment_id = ?",
                (payment_id,),
            ).fetchone()
            if existing:
                row = conn.execute(
                    "SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)
                ).fetchone()
                return dict(row) if row else get_subscription(user_id)

        current = conn.execute(
            "SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)
        ).fetchone()
        base = now
        if current and current["plan"] == PLAN_PRO and current["expires_at"]:
            cur_exp = _parse_dt(current["expires_at"])
            if cur_exp and cur_exp > now:
                base = cur_exp
        expires = base + timedelta(days=30 * months)
        started = (
            current["started_at"]
            if current and current["plan"] == PLAN_PRO
            else now.strftime("%Y-%m-%d %H:%M:%S")
        )
        conn.execute(
            """
            INSERT INTO subscriptions
                (user_id, plan, status, started_at, expires_at, provider, last_payment_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                plan = excluded.plan,
                status = excluded.status,
                started_at = COALESCE(subscriptions.started_at, excluded.started_at),
                expires_at = excluded.expires_at,
                provider = excluded.provider,
                last_payment_id = excluded.last_payment_id,
                reminder_sent_at = NULL
            """,
            (
                user_id,
                PLAN_PRO,
                STATUS_ACTIVE,
                started,
                expires.strftime("%Y-%m-%d %H:%M:%S"),
                provider,
                payment_id,
            ),
        )
        if payment_id:
            conn.execute(
                """
                INSERT INTO payments
                    (user_id, provider, provider_payment_id, amount, currency, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    provider,
                    payment_id,
                    DEFAULT_STARS_PRICE,
                    STARS_CURRENCY,
                    "paid",
                    now.strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)
        ).fetchone()
    return dict(row)


def expire_subscriptions() -> list[int]:
    """Помечает просроченные (после grace) как expired. Возвращает user_id."""
    now = _now()
    expired_ids: list[int] = []
    with storage._connect() as conn:
        storage._init_db(conn)
        rows = conn.execute(
            """
            SELECT user_id, expires_at FROM subscriptions
            WHERE plan = ? AND status = ? AND expires_at IS NOT NULL
            """,
            (PLAN_PRO, STATUS_ACTIVE),
        ).fetchall()
        for row in rows:
            exp = _parse_dt(row["expires_at"])
            if exp and now > exp + timedelta(days=GRACE_DAYS):
                conn.execute(
                    """
                    UPDATE subscriptions
                    SET plan = ?, status = ?
                    WHERE user_id = ?
                    """,
                    (PLAN_FREE, STATUS_EXPIRED, row["user_id"]),
                )
                expired_ids.append(int(row["user_id"]))
        conn.commit()
    return expired_ids


def subscriptions_needing_reminder(days_before: int = 3) -> list[dict]:
    now = _now()
    result = []
    with storage._connect() as conn:
        storage._init_db(conn)
        rows = conn.execute(
            """
            SELECT * FROM subscriptions
            WHERE plan = ? AND status = ? AND expires_at IS NOT NULL
            """,
            (PLAN_PRO, STATUS_ACTIVE),
        ).fetchall()
        for row in rows:
            exp = _parse_dt(row["expires_at"])
            if not exp:
                continue
            days_left = (exp.date() - now.date()).days
            if 0 <= days_left <= days_before:
                reminded = _parse_dt(
                    row["reminder_sent_at"]
                    if "reminder_sent_at" in row.keys()
                    else None
                )
                if reminded and reminded.date() == now.date():
                    continue
                result.append(dict(row))
    return result


def mark_subscription_reminded(user_id: int) -> None:
    now = _now().strftime("%Y-%m-%d %H:%M:%S")
    with storage._connect() as conn:
        storage._init_db(conn)
        conn.execute(
            "UPDATE subscriptions SET reminder_sent_at = ? WHERE user_id = ?",
            (now, user_id),
        )
        conn.commit()


def stars_payload(user_id: int) -> str:
    return f"{STARS_PAYLOAD_PREFIX}{user_id}:{int(_now().timestamp())}"


def parse_stars_payload(payload: str) -> Optional[int]:
    if not payload or not payload.startswith(STARS_PAYLOAD_PREFIX):
        return None
    rest = payload[len(STARS_PAYLOAD_PREFIX) :]
    try:
        return int(rest.split(":", 1)[0])
    except ValueError:
        return None
