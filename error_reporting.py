"""Sentry и алерты админам в Telegram (опционально)."""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_sentry_inited = False


def init_sentry() -> bool:
    global _sentry_inited
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        logger.info("SENTRY_DSN не задан — Sentry отключён")
        return False
    try:
        import sentry_sdk
    except ImportError:
        logger.warning("sentry-sdk не установлен")
        return False
    sentry_sdk.init(dsn=dsn, traces_sample_rate=0.0)
    _sentry_inited = True
    return True


def capture_exception(exc: BaseException) -> None:
    if not _sentry_inited:
        return
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except Exception:
        logger.exception("Не удалось отправить ошибку в Sentry")


async def alert_admins(
    bot,
    admin_ids: tuple[int, ...],
    text: str,
) -> None:
    for admin_id in admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=text[:3500])
        except Exception:
            logger.exception("Не удалось отправить алерт admin_id=%s", admin_id)


def report_failure(
    exc: Optional[BaseException] = None,
    message: str = "",
) -> None:
    if exc is not None:
        capture_exception(exc)
    if message:
        logger.error(message)
