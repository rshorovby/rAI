"""Кабинет тренера: статусы заявки и клавиатуры игрока."""

from __future__ import annotations

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

# Режимы кабинета: ответ игроку vs эталон для ИИ.
ACTION_REPLY_PLAYER = "reply"
ACTION_FIX_AI = "fix"
ACTION_FIX_AI_CONT = "fix_cont"
VALID_COACH_ACTIONS = (ACTION_REPLY_PLAYER, ACTION_FIX_AI)
FIX_AI_PENDING = (ACTION_FIX_AI, ACTION_FIX_AI_CONT)

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


# Старые оценки (колонка в БД, UI убран).
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

_ACTION_BUTTONS = (
    (ACTION_REPLY_PLAYER, "💬 Ответить игроку"),
    (ACTION_FIX_AI, "✏️ Исправить ответ ИИ"),
)


def coach_action_keyboard(job_id: int, action: str = "") -> InlineKeyboardMarkup:
    row = []
    active = ACTION_FIX_AI if action in FIX_AI_PENDING else action
    for key, label in _ACTION_BUTTONS:
        mark = "· " if active == key else ""
        row.append(
            InlineKeyboardButton(
                f"{mark}{label}",
                callback_data=f"ce:a:{job_id}:{key}",
            )
        )
    return InlineKeyboardMarkup([row])


# Alias для старых импортов/тестов.
keyboard_player_waiting = keyboard_message_coach


def topic_title(user_id: int, first_name: str = "", username: str = "") -> str:
    name = (first_name or "").strip() or (f"@{username}" if username else "Игрок")
    # Telegram topic title max 128
    title = f"{name} · {user_id}"
    return title[:128]
