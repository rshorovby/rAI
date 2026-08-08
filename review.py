"""Заявки на ревью тренера (Product V2) — клавиатуры и склейка текста."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from i18n import t

STATUS_QUEUED = "queued"
STATUS_IN_REVIEW = "in_review"
STATUS_SENT_COACH = "sent_coach"
STATUS_SENT_FALLBACK = "sent_fallback"
STATUS_CANCELLED = "cancelled"

ACTION_SEND = "send"
ACTION_REPLACE = "replace"
ACTION_NOTES = "notes"

COACH_PENDING_KEY = "coach_review_pending"  # context.user_data у тренера
PLAYER_MSG_PENDING_KEY = "player_coach_message_job"  # ждём текст игрока тренеру


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


def keyboard_coach_job(job_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Отправить как есть",
                    callback_data=f"rv:{job_id}:{ACTION_SEND}",
                )
            ],
            [
                InlineKeyboardButton(
                    "✏️ Заменить текст",
                    callback_data=f"rv:{job_id}:{ACTION_REPLACE}",
                )
            ],
            [
                InlineKeyboardButton(
                    "➕ Замечания тренера",
                    callback_data=f"rv:{job_id}:{ACTION_NOTES}",
                )
            ],
        ]
    )


def keyboard_player_waiting(lang: str) -> InlineKeyboardMarkup:
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


def topic_title(user_id: int, first_name: str = "", username: str = "") -> str:
    name = (first_name or "").strip() or (f"@{username}" if username else "Игрок")
    # Telegram topic title max 128
    title = f"{name} · {user_id}"
    return title[:128]
