"""Логика сроков тренировки и клавиатуры цепочки practice_plans."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from i18n import t

MSK = ZoneInfo("Europe/Moscow")

DATE_TODAY = "today"
DATE_TOMORROW = "tomorrow"
DATE_PLUS2 = "plus2"
DATE_WEEKEND = "weekend"
DATE_UNKNOWN = "unknown"

POST_YES = "yes"
POST_HARD = "hard"
POST_SKIP = "skip"


def now_msk() -> datetime:
    return datetime.now(MSK)


def today_msk() -> date:
    return now_msk().date()


def resolve_practice_date(
    choice: str, *, today: Optional[date] = None
) -> Optional[date]:
    """Возвращает дату тренировки или None для unknown (вызывающий ставит +1д)."""
    base = today or today_msk()
    if choice == DATE_TODAY:
        return base
    if choice == DATE_TOMORROW:
        return base + timedelta(days=1)
    if choice == DATE_PLUS2:
        return base + timedelta(days=2)
    if choice == DATE_WEEKEND:
        # ближайшая суббота; если уже сб — воскресенье
        weekday = base.weekday()  # пн=0 … вс=6
        if weekday == 5:  # Saturday
            return base + timedelta(days=1)
        if weekday == 6:  # Sunday
            return base
        return base + timedelta(days=(5 - weekday))
    if choice == DATE_UNKNOWN:
        return None
    raise ValueError(f"unknown practice date choice: {choice}")


def fallback_practice_date(*, today: Optional[date] = None) -> date:
    return (today or today_msk()) + timedelta(days=1)


def should_send_pre_now(*, now: Optional[datetime] = None) -> bool:
    current = now or now_msk()
    return current.hour >= 9


def should_send_post_now(*, now: Optional[datetime] = None) -> bool:
    current = now or now_msk()
    return current.hour >= 20


def keyboard_ask_practice(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t(lang, "practice_btn_today"), callback_data=f"p:date:{DATE_TODAY}"
                )
            ],
            [
                InlineKeyboardButton(
                    t(lang, "practice_btn_tomorrow"),
                    callback_data=f"p:date:{DATE_TOMORROW}",
                )
            ],
            [
                InlineKeyboardButton(
                    t(lang, "practice_btn_plus2"), callback_data=f"p:date:{DATE_PLUS2}"
                )
            ],
            [
                InlineKeyboardButton(
                    t(lang, "practice_btn_weekend"),
                    callback_data=f"p:date:{DATE_WEEKEND}",
                )
            ],
            [
                InlineKeyboardButton(
                    t(lang, "practice_btn_unknown"),
                    callback_data=f"p:date:{DATE_UNKNOWN}",
                )
            ],
            [
                InlineKeyboardButton(
                    t(lang, "practice_btn_mute"), callback_data="p:mute"
                )
            ],
        ]
    )


def keyboard_pre_nudge(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t(lang, "practice_btn_pre_ok"), callback_data="p:pre:ok"
                )
            ],
            [
                InlineKeyboardButton(
                    t(lang, "practice_btn_pre_move"), callback_data="p:pre:move"
                )
            ],
        ]
    )


def keyboard_post_checkin(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t(lang, "practice_btn_post_yes"),
                    callback_data=f"p:post:{POST_YES}",
                )
            ],
            [
                InlineKeyboardButton(
                    t(lang, "practice_btn_post_hard"),
                    callback_data=f"p:post:{POST_HARD}",
                )
            ],
            [
                InlineKeyboardButton(
                    t(lang, "practice_btn_post_skip"),
                    callback_data=f"p:post:{POST_SKIP}",
                )
            ],
        ]
    )


def keyboard_after_date_set(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t(lang, "dialog_btn_feedback"), callback_data="d:fb"
                )
            ],
            [
                InlineKeyboardButton(
                    t(lang, "practice_btn_mute"), callback_data="p:mute"
                )
            ],
        ]
    )
