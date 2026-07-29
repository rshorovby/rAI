import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import billing
import storage
from analytics import (
    EVENT_FEEDBACK_CLEAR,
    EVENT_FEEDBACK_NEGATIVE,
    EVENT_FEEDBACK_POSITIVE,
)
from bot import _FEEDBACK_EVENTS, _feedback_keyboard, _split_message, handle_video


def test_short_text_single_chunk():
    assert _split_message("привет") == ["привет"]


def test_long_text_is_split():
    text = "\n".join(f"строка {i}" for i in range(2000))
    chunks = _split_message(text, limit=1000)
    assert len(chunks) > 1
    assert all(len(c) <= 1000 for c in chunks)


def test_split_preserves_all_lines():
    text = "\n".join(f"line{i}" for i in range(500))
    chunks = _split_message(text, limit=500)
    rejoined = "\n".join(chunks)
    for i in range(500):
        assert f"line{i}" in rejoined


def test_feedback_keyboard_has_three_buttons():
    markup = _feedback_keyboard("ru")
    buttons = [btn for row in markup.inline_keyboard for btn in row]
    assert len(buttons) == 3
    assert {btn.callback_data for btn in buttons} == {"fb:pos", "fb:neg", "fb:clear"}


def test_feedback_events_mapping():
    assert _FEEDBACK_EVENTS["pos"] == EVENT_FEEDBACK_POSITIVE
    assert _FEEDBACK_EVENTS["neg"] == EVENT_FEEDBACK_NEGATIVE
    assert _FEEDBACK_EVENTS["clear"] == EVENT_FEEDBACK_CLEAR


def test_quota_blocks_when_exhausted(tmp_path):
    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        storage.upsert_user(88, None, "Q", None, "ru")
        storage.save_player_profile(
            88,
            {
                "level": "amateur",
                "focus": "fh",
                "hand": "right",
                "injuries": "",
            },
        )
        storage.save_session(88, "## Краткое резюме\na\n")
        storage.save_session(88, "## Краткое резюме\nb\n")
        assert not billing.has_quota(88)

        update = MagicMock()
        update.message = MagicMock()
        update.message.from_user.id = 88
        update.message.from_user.language_code = "ru"
        update.effective_user = update.message.from_user
        update.message.video = MagicMock(
            file_size=1000, duration=10, mime_type="video/mp4", file_id="f"
        )
        update.message.video_note = None
        update.message.caption = None
        update.message.reply_text = AsyncMock()
        context = MagicMock()
        context.user_data = {}

        async def _run():
            with (
                patch("bot._touch_user", new=AsyncMock()),
                patch("bot._lang_from_update", return_value="ru"),
                patch("bot.is_onboarding_active", return_value=False),
                patch("bot.is_reset_pending", return_value=False),
            ):
                await handle_video(update, context)

        asyncio.run(_run())
        assert update.message.reply_text.await_count == 1
        text = update.message.reply_text.await_args.args[0]
        assert "лимит" in text.lower()
