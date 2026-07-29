#!/usr/bin/env python3
"""Рассылка напоминаний и недельных дайджестов."""

import asyncio
import logging
import sys

from telegram import Bot

import storage
from analytics import EVENT_REMINDER_SENT
from config import load_settings
from i18n import normalize_language_code, t

logger = logging.getLogger(__name__)


def _ui_lang(language_code: str) -> str:
    return "ru" if normalize_language_code(language_code or "") == "ru" else "en"


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
        # если на этой неделе был разбор — стрик продолжится в mark_digest_sent
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


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
        level=logging.INFO,
    )
    mode = "remind"
    days = 7
    if len(sys.argv) > 1:
        if sys.argv[1] == "digest":
            mode = "digest"
        else:
            days = int(sys.argv[1])
    if mode == "digest":
        count = asyncio.run(run_digests())
        print(f"Отправлено дайджестов: {count}")
    else:
        count = asyncio.run(run_reminders(days))
        print(f"Отправлено напоминаний: {count}")


if __name__ == "__main__":
    main()
