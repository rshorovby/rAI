import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from telegram.error import BadRequest, Forbidden, RetryAfter

import broadcast
import storage
from bot import (
    broadcast_command,
    handle_broadcast_callback,
    handle_text,
)


def _user(user_id: int = 1):
    user = MagicMock()
    user.id = user_id
    user.username = "admin"
    user.first_name = "Ann"
    user.last_name = None
    user.language_code = "ru"
    return user


def _context(user_id: int = 1):
    context = MagicMock()
    context.user_data = {}
    context.args = []
    context.application.bot_data = {"admin_user_ids": (user_id,), "settings": None}
    context.bot.send_message = AsyncMock()
    return context


def _message(text: str, user_id: int = 1):
    user = _user(user_id)
    message = MagicMock()
    message.text = text
    message.from_user = user
    message.chat.id = user_id
    message.chat.type = "private"
    message.chat_id = user_id
    message.entities = ()
    message.caption = None
    message.photo = None
    message.video = None
    message.video_note = None
    message.audio = None
    message.voice = None
    message.document = None
    message.sticker = None
    message.animation = None
    message.contact = None
    message.location = None
    message.venue = None
    message.poll = None
    message.dice = None
    message.message_thread_id = None
    message.reply_text = AsyncMock()
    return message


def _text_update(text: str, user_id: int = 1):
    user = _user(user_id)
    update = MagicMock()
    update.effective_user = user
    update.message = _message(text, user_id)
    update.callback_query = None
    return update


def _callback_update(data: str, user_id: int = 1):
    user = _user(user_id)
    update = MagicMock()
    update.effective_user = user
    query = MagicMock()
    query.data = data
    query.from_user = user
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message.reply_text = AsyncMock()
    update.callback_query = query
    update.message = None
    return update


def test_recipients_include_inactive_and_skip_apple_only(tmp_path):
    with patch.object(storage, "DB_PATH", tmp_path / "broadcast.db"):
        storage.upsert_user(7, "old", "Old", None, "ru")
        storage.upsert_user(8, "new", "New", None, "en")
        storage.get_or_create_apple_player("apple-only")
        with storage._connect() as conn:
            conn.execute(
                "UPDATE users SET last_seen_at = ? WHERE user_id = ?",
                ("2020-01-01 00:00:00", 7),
            )
            conn.commit()
        assert storage.list_broadcast_chat_ids() == [7, 8]


def test_deliver_counts_blocked_and_retries_flood():
    calls = []

    async def send(chat_id, text, entities):
        calls.append(chat_id)
        if chat_id == 2 and calls.count(2) == 1:
            raise RetryAfter(1)
        if chat_id == 3:
            raise Forbidden("bot was blocked by the user")
        if chat_id == 4:
            raise BadRequest("Chat not found")
        if chat_id == 5:
            raise RuntimeError("boom")

    async def _run():
        with patch("broadcast.asyncio.sleep", new=AsyncMock()):
            return await broadcast.deliver(send, [1, 2, 3, 4, 5], "привет", pause=0)

    result = asyncio.run(_run())
    assert result == {"sent": 2, "blocked": 2, "failed": 1}
    assert calls.count(2) == 2


def test_non_admin_cannot_start_broadcast():
    context = _context()
    context.application.bot_data["admin_user_ids"] = (1,)
    update = _text_update("/broadcast", user_id=7)
    asyncio.run(broadcast_command(update, context))
    reply = update.message.reply_text.await_args.args[0]
    assert "администратора" in reply
    assert broadcast.AWAITING_KEY not in context.user_data


def test_admin_draft_counts_everyone_with_telegram(tmp_path):
    with patch.object(storage, "DB_PATH", tmp_path / "broadcast.db"):
        storage.upsert_user(7, "old", "Old", None, "ru")
        with storage._connect() as conn:
            conn.execute(
                "UPDATE users SET last_seen_at = ? WHERE user_id = ?",
                ("2020-01-01 00:00:00", 7),
            )
            conn.commit()
        context = _context()
        start = _text_update("/broadcast")
        asyncio.run(broadcast_command(start, context))
        assert context.user_data[broadcast.AWAITING_KEY] is True

        draft = _text_update("Обновление\nбот считает streak")
        draft.message.entities = ("bold",)
        asyncio.run(handle_text(draft, context))
        text = draft.message.reply_text.await_args.args[0]
        assert "Получателей: 2" in text
        assert "Обновление" in text
        assert context.user_data[broadcast.DRAFT_KEY]["text"].startswith("Обновление")
        assert context.user_data[broadcast.DRAFT_KEY]["entities"] == ("bold",)
        assert broadcast.AWAITING_KEY not in context.user_data


def test_plain_text_is_not_a_draft(tmp_path):
    with patch.object(storage, "DB_PATH", tmp_path / "broadcast.db"):
        context = _context()
        update = _text_update("как держать ракетку")
        asyncio.run(handle_text(update, context))
        reply = update.message.reply_text.await_args.args[0]
        assert "Получателей" not in reply
        assert broadcast.DRAFT_KEY not in context.user_data


def test_send_reports_and_second_click_does_not_overwrite(tmp_path):
    with patch.object(storage, "DB_PATH", tmp_path / "broadcast.db"):
        storage.upsert_user(7, "a", "A", None, "ru")
        storage.upsert_user(8, "b", "B", None, "en")

        def send_message(**kwargs):
            if kwargs["chat_id"] == 8:
                raise Forbidden("bot was blocked by the user")
            return MagicMock()

        context = _context()
        context.bot.send_message = AsyncMock(side_effect=send_message)
        context.user_data[broadcast.DRAFT_KEY] = {
            "text": "Дайджест",
            "entities": (),
        }
        update = _callback_update("bc:send")

        async def _run():
            with patch("broadcast.asyncio.sleep", new=AsyncMock()):
                await handle_broadcast_callback(update, context)
                edits = update.callback_query.edit_message_text.await_count
                await handle_broadcast_callback(update, context)
                return edits

        edits_after_first = asyncio.run(_run())
        assert edits_after_first == 2
        assert update.callback_query.edit_message_text.await_count == 2
        report = update.callback_query.edit_message_text.await_args.args[0]
        assert "Отправлено: 1" in report
        assert "Заблокировали бота: 1" in report
        assert broadcast.DRAFT_KEY not in context.user_data
        with storage._connect() as conn:
            row = conn.execute("SELECT * FROM broadcasts").fetchone()
        assert row["sent_count"] == 1
        assert row["blocked_count"] == 1
        assert row["body"] == "Дайджест"
        assert row["audience"] == "all_telegram"


def test_preview_to_self_keeps_draft():
    context = _context()
    context.user_data[broadcast.DRAFT_KEY] = {
        "text": "Черновик",
        "entities": ("ent",),
    }
    update = _callback_update("bc:me")
    asyncio.run(handle_broadcast_callback(update, context))
    kwargs = context.bot.send_message.await_args.kwargs
    assert kwargs["chat_id"] == 1
    assert kwargs["text"] == "Черновик"
    assert kwargs["entities"] == ("ent",)
    assert broadcast.DRAFT_KEY in context.user_data
    note = update.callback_query.message.reply_text.await_args.args[0]
    assert "Копия отправлена" in note


def test_cancel_clears_draft():
    context = _context()
    context.user_data[broadcast.AWAITING_KEY] = True
    context.user_data[broadcast.DRAFT_KEY] = {"text": "нет", "entities": ()}
    update = _callback_update("bc:cancel")
    asyncio.run(handle_broadcast_callback(update, context))
    assert broadcast.DRAFT_KEY not in context.user_data
    assert broadcast.AWAITING_KEY not in context.user_data
    text = update.callback_query.edit_message_text.await_args.args[0]
    assert text == "Рассылка отменена."
