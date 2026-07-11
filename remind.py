#!/usr/bin/env python3
"""Рассылка напоминаний «пришли видео» через N дней после разбора."""

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


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
        level=logging.INFO,
    )
    days = 7
    if len(sys.argv) > 1:
        days = int(sys.argv[1])
    count = asyncio.run(run_reminders(days=days))
    print(f"Отправлено напоминаний: {count}")


if __name__ == "__main__":
    main()
