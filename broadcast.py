"""Админская рассылка: всем с Telegram или одному человеку по id."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest, Forbidden, RetryAfter

logger = logging.getLogger(__name__)

AWAITING_KEY = "broadcast_awaiting"
DRAFT_KEY = "broadcast_draft"
TARGET_KEY = "broadcast_target"
SEND_PAUSE_SEC = 0.05
PREVIEW_LIMIT = 300
TEXT_LIMIT = 4096

SendFn = Callable[[int, str, Optional[tuple]], Awaitable[None]]

_send_lock = asyncio.Lock()


class BroadcastInProgress(Exception):
    pass


def busy() -> bool:
    return _send_lock.locked()


def clear_state(user_data: dict) -> None:
    user_data.pop(AWAITING_KEY, None)
    user_data.pop(DRAFT_KEY, None)
    user_data.pop(TARGET_KEY, None)


def usage_text() -> str:
    return (
        "Использование: /broadcast [id]\n"
        "Без id — всем, у кого есть Telegram.\n"
        "С id — только этому человеку. id из кабинета или Telegram.\n"
        "Отмена: /broadcast cancel"
    )


def keyboard(single: bool = False) -> InlineKeyboardMarkup:
    send = "Отправить" if single else "Отправить всем"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(send, callback_data="bc:send"),
                InlineKeyboardButton("Себе", callback_data="bc:me"),
            ],
            [InlineKeyboardButton("Отмена", callback_data="bc:cancel")],
        ]
    )


def recipient_line(target: dict) -> str:
    chat_id = int(target["chat_id"])
    label = (target.get("label") or "").strip()
    if not label or label.isdigit():
        return f"id {chat_id}"
    return f"{label}, id {chat_id}"


def preview(text: str) -> str:
    cleaned = text.strip()
    if len(cleaned) <= PREVIEW_LIMIT:
        return cleaned
    return cleaned[: PREVIEW_LIMIT - 1] + "…"


def confirm_text(count: int, text: str, *, recipient: str = "") -> str:
    if recipient:
        header = f"Получатель: {recipient}."
        question = "Отправить?"
    else:
        header = f"Получателей: {count} — все, у кого есть Telegram."
        question = "Отправить всем?"
    return f"{header}\n\n{preview(text)}\n\n{question}"


def report_text(sent: int, blocked: int, failed: int) -> str:
    return (
        "Рассылка завершена.\n"
        f"Отправлено: {sent}\n"
        f"Заблокировали бота: {blocked}\n"
        f"Не доставлено: {failed}"
    )


def _undeliverable(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "chat not found" in message or "user is deactivated" in message


async def _deliver_one(send: SendFn, chat_id: int, text: str, entities) -> str:
    retried = False
    while True:
        try:
            await send(chat_id, text, entities)
            return "sent"
        except RetryAfter as exc:
            if retried:
                return "failed"
            retried = True
            await asyncio.sleep(float(exc.retry_after) + 0.5)
        except Forbidden:
            return "blocked"
        except BadRequest as exc:
            if _undeliverable(exc):
                return "blocked"
            logger.exception("Рассылка не ушла chat_id=%s", chat_id)
            return "failed"
        except Exception:
            logger.exception("Рассылка не ушла chat_id=%s", chat_id)
            return "failed"


async def deliver(
    send: SendFn,
    chat_ids: list,
    text: str,
    entities=None,
    pause: float = SEND_PAUSE_SEC,
) -> dict:
    if _send_lock.locked():
        raise BroadcastInProgress()
    sent = blocked = failed = 0
    async with _send_lock:
        for chat_id in chat_ids:
            outcome = await _deliver_one(send, int(chat_id), text, entities)
            if outcome == "sent":
                sent += 1
            elif outcome == "blocked":
                blocked += 1
            else:
                failed += 1
            if pause:
                await asyncio.sleep(pause)
    return {"sent": sent, "blocked": blocked, "failed": failed}
