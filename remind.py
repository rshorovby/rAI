#!/usr/bin/env python3
"""Рассылка напоминаний, practice pre/post и недельных дайджестов."""

import asyncio
import logging
import sys

from telegram import Bot

import practice
import storage
from analytics import (
    EVENT_PRACTICE_POST_SENT,
    EVENT_PRACTICE_PRE_SENT,
    EVENT_REMINDER_SENT,
)
from config import load_settings
from i18n import normalize_language_code, t
from practice import keyboard_post_checkin, keyboard_pre_nudge

logger = logging.getLogger(__name__)


def _ui_lang(language_code: str) -> str:
    return "ru" if normalize_language_code(language_code or "") == "ru" else "en"


def _focus_drill(row: dict) -> tuple[str, str]:
    focus = (row.get("focus_text") or "").strip() or "—"
    drill = (row.get("drill_text") or "").strip() or "—"
    return focus, drill


async def run_reminders(days: int = 7) -> int:
    settings = load_settings()
    bot = Bot(settings.telegram_token)
    users = storage.get_users_for_reminder(days=days)
    sent = 0
    for row in users:
        user_id = row["user_id"]
        lang = _ui_lang(row.get("language_code") or "")
        task = (row.get("next_video") or "").strip()
        if task:
            text = t(lang, "reminder_with_task", task=task)
        else:
            text = t(lang, "reminder_generic")
        try:
            await bot.send_message(chat_id=user_id, text=text)
            storage.mark_reminder_sent(user_id)
            storage.log_event(user_id, EVENT_REMINDER_SENT)
            sent += 1
            logger.info("Напоминание отправлено user_id=%s", user_id)
        except Exception:
            logger.exception("Не удалось отправить напоминание user_id=%s", user_id)
    return sent


async def run_digests() -> int:
    settings = load_settings()
    bot = Bot(settings.telegram_token)
    users = storage.get_users_for_digest()
    sent = 0
    for row in users:
        user_id = int(row["user_id"])
        lang = _ui_lang(row.get("language_code") or "")
        focus_row = storage.get_player_focus(user_id)
        focus = (focus_row or {}).get("focus") or "—"
        analyses = int(row.get("analyses_week") or 0)
        streak = int(row.get("streak_weeks") or 0)
        text = t(
            lang,
            "digest_weekly",
            focus=focus,
            streak=streak + (1 if analyses else 0),
            analyses=analyses,
        )
        try:
            await bot.send_message(chat_id=user_id, text=text, parse_mode="Markdown")
            storage.mark_digest_sent(user_id, had_analysis=analyses > 0)
            sent += 1
            logger.info("Дайджест отправлен user_id=%s", user_id)
        except Exception:
            logger.exception("Не удалось отправить дайджест user_id=%s", user_id)
    return sent


async def run_practice_nudges() -> tuple[int, int]:
    """Отправляет due pre/post по московскому времени. Возвращает (pre, post)."""
    settings = load_settings()
    bot = Bot(settings.telegram_token)
    today = practice.today_msk().isoformat()
    storage.auto_schedule_stale_practice_plans(today)
    pre_sent = 0
    post_sent = 0

    if practice.should_send_pre_now():
        for row in storage.list_due_practice_pre(today):
            user_id = int(row["user_id"])
            lang = _ui_lang(row.get("language_code") or "")
            focus, drill = _focus_drill(row)
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=t(lang, "practice_pre", focus=focus, drill=drill),
                    parse_mode="Markdown",
                    reply_markup=keyboard_pre_nudge(lang),
                )
                storage.mark_practice_pre_sent(int(row["id"]))
                storage.log_event(user_id, EVENT_PRACTICE_PRE_SENT)
                pre_sent += 1
                logger.info("Practice pre отправлен user_id=%s", user_id)
            except Exception:
                logger.exception(
                    "Не удалось отправить practice pre user_id=%s", user_id
                )

    if practice.should_send_post_now():
        for row in storage.list_due_practice_post(today):
            user_id = int(row["user_id"])
            lang = _ui_lang(row.get("language_code") or "")
            _, drill = _focus_drill(row)
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=t(lang, "practice_post", drill=drill),
                    reply_markup=keyboard_post_checkin(lang),
                )
                storage.mark_practice_post_sent(int(row["id"]))
                storage.log_event(user_id, EVENT_PRACTICE_POST_SENT)
                post_sent += 1
                logger.info("Practice post отправлен user_id=%s", user_id)
            except Exception:
                logger.exception(
                    "Не удалось отправить practice post user_id=%s", user_id
                )

    return pre_sent, post_sent


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
        level=logging.INFO,
    )
    mode = "remind"
    days = 7
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "digest":
            mode = "digest"
        elif arg == "practice":
            mode = "practice"
        else:
            days = int(arg)
    if mode == "digest":
        count = asyncio.run(run_digests())
        print(f"Отправлено дайджестов: {count}")
    elif mode == "practice":
        pre, post = asyncio.run(run_practice_nudges())
        print(f"Practice nudges: pre={pre}, post={post}")
    else:
        count = asyncio.run(run_reminders(days))
        print(f"Отправлено напоминаний: {count}")


if __name__ == "__main__":
    main()
