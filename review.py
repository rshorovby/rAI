"""Кабинет тренера: статусы заявки и клавиатуры игрока."""

from __future__ import annotations

from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from i18n import t

STATUS_QUEUED = "queued"
STATUS_IN_REVIEW = "in_review"
STATUS_AI_SENT = "ai_sent"
STATUS_AI_FAILED = "ai_failed"
STATUS_SENT_COACH = "sent_coach"
STATUS_SENT_FALLBACK = "sent_fallback"
STATUS_CANCELLED = "cancelled"

# Устаревшие действия (кнопки убраны; оставлены для совместимости callback).
ACTION_SEND = "send"
ACTION_REPLACE = "replace"
ACTION_NOTES = "notes"

PLAYER_MSG_PENDING_KEY = "player_coach_message_pending"


def compose_final_report(
    draft_text: str,
    *,
    coach_notes: str = "",
    replacement: str = "",
    fallback: bool = False,
    lang: str = "ru",
) -> str:
    body = (replacement or draft_text or "").strip()
    notes = (coach_notes or "").strip()
    parts = []
    if fallback:
        parts.append(t(lang, "review_fallback_banner"))
    if notes:
        parts.append(t(lang, "review_coach_notes_block", notes=notes))
    if body:
        parts.append(body)
    return "\n\n".join(parts).strip()


def keyboard_message_coach(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t(lang, "review_btn_message_coach"),
                    callback_data="rvp:msg",
                )
            ]
        ]
    )


# Оценка AI-черновика тренером (кабинет).
RATING_OK = "ok"
RATING_ADDED = "added"
RATING_MISS = "miss"
VALID_RATINGS = (RATING_OK, RATING_ADDED, RATING_MISS)

TAG_PRIORITY = "priority"
TAG_HALLUCINATION = "hallucination"
TAG_MISSED = "missed"
TAG_TONE = "tone"
TAG_HOMEWORK = "homework"
VALID_TAGS = (
    TAG_PRIORITY,
    TAG_HALLUCINATION,
    TAG_MISSED,
    TAG_TONE,
    TAG_HOMEWORK,
)

_RATING_BUTTONS = (
    (RATING_OK, "✅ Ок"),
    (RATING_ADDED, "✏️ Дополнил"),
    (RATING_MISS, "❌ Мимо"),
)
_TAG_BUTTONS = (
    (TAG_PRIORITY, "приоритеты"),
    (TAG_HALLUCINATION, "выдумал"),
    (TAG_MISSED, "пропустил"),
    (TAG_TONE, "тон"),
    (TAG_HOMEWORK, "домашка"),
)
_RATING_LABELS = {
    RATING_OK: "Ок — как есть",
    RATING_ADDED: "Дополнил",
    RATING_MISS: "Мимо",
}


def coach_eval_prompt(
    job_id: int, rating: str = "", tags: Optional[list] = None
) -> str:
    lines = [
        f"⭐ Оценка AI-разбора #{job_id}",
        "",
        "Как черновик для этого видео?",
        "Ок — отправил бы как есть",
        "Дополнил — в целом верно, допишу акцент",
        "Мимо — не те приоритеты или факты",
        "",
        "Комментарий игроку в этой теме сохранится как эталон правки.",
    ]
    if rating in _RATING_LABELS:
        lines.extend(["", f"Сейчас: {_RATING_LABELS[rating]}"])
    selected = [tag for tag in (tags or []) if tag in dict(_TAG_BUTTONS)]
    if selected:
        labels = [label for key, label in _TAG_BUTTONS if key in selected]
        lines.append("Теги: " + ", ".join(labels))
    return "\n".join(lines)


def coach_eval_keyboard(
    job_id: int, rating: str = "", tags: Optional[list] = None
) -> InlineKeyboardMarkup:
    selected_tags = set(tags or [])
    rating_row = []
    for key, label in _RATING_BUTTONS:
        mark = "· " if rating == key else ""
        rating_row.append(
            InlineKeyboardButton(
                f"{mark}{label}",
                callback_data=f"ce:r:{job_id}:{key}",
            )
        )
    rows = [rating_row]
    if rating in (RATING_ADDED, RATING_MISS):
        tag_row = []
        for key, label in _TAG_BUTTONS:
            prefix = "✓ " if key in selected_tags else ""
            tag_row.append(
                InlineKeyboardButton(
                    f"{prefix}{label}",
                    callback_data=f"ce:t:{job_id}:{key}",
                )
            )
        rows.append(tag_row[:3])
        rows.append(tag_row[3:])
    return InlineKeyboardMarkup(rows)


# Alias для старых импортов/тестов.
keyboard_player_waiting = keyboard_message_coach


def topic_title(user_id: int, first_name: str = "", username: str = "") -> str:
    name = (first_name or "").strip() or (f"@{username}" if username else "Игрок")
    # Telegram topic title max 128
    title = f"{name} · {user_id}"
    return title[:128]
