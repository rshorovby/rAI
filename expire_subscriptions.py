#!/usr/bin/env python3
"""Истечение Pro-подписок и напоминания за 3 дня до конца."""

import asyncio
import logging

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

import billing
import storage
from analytics import EVENT_SUBSCRIPTION_EXPIRED
from config import load_settings
from i18n import normalize_language_code, t

logger = logging.getLogger(__name__)


def _ui_lang(language_code: str) -> str:
    return "ru" if normalize_language_code(language_code or "") == "ru" else "en"


async def run() -> tuple[int, int]:
    if not billing.MONETIZATION_ENABLED:
        logger.info("Монетизация выключена — напоминания о Pro пропущены")
        return 0, 0
    settings = load_settings()
    bot = Bot(settings.telegram_token)
    reminded = 0
    for row in billing.subscriptions_needing_reminder(3):
        user_id = int(row["user_id"])
        with storage._connect() as conn:
            storage._init_db(conn)
            u = conn.execute(
                "SELECT language_code FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        lang = _ui_lang((u["language_code"] if u else None) or "")
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        t(lang, "btn_upgrade_pro"), callback_data="pay:pro"
                    )
                ]
            ]
        )
        try:
            await bot.send_message(
                chat_id=user_id,
                text=t(lang, "subscription_expiring", expires=row.get("expires_at")),
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
            billing.mark_subscription_reminded(user_id)
            reminded += 1
        except Exception:
            logger.exception("Не удалось напомнить о подписке user_id=%s", user_id)

    expired_ids = billing.expire_subscriptions()
    for user_id in expired_ids:
        storage.log_event(user_id, EVENT_SUBSCRIPTION_EXPIRED)
        with storage._connect() as conn:
            storage._init_db(conn)
            u = conn.execute(
                "SELECT language_code FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        lang = _ui_lang((u["language_code"] if u else None) or "")
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        t(lang, "btn_upgrade_pro"), callback_data="pay:pro"
                    )
                ]
            ]
        )
        try:
            await bot.send_message(
                chat_id=user_id,
                text=t(lang, "subscription_expired"),
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
        except Exception:
            logger.exception("Не удалось уведомить об истечении user_id=%s", user_id)
    return reminded, len(expired_ids)


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
        level=logging.INFO,
    )
    reminded, expired = asyncio.run(run())
    print(f"Напоминаний: {reminded}, истекло: {expired}")


if __name__ == "__main__":
    main()
