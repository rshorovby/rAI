import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import billing
import storage
from analytics import (
    EVENT_FEEDBACK_CLEAR,
    EVENT_FEEDBACK_NEGATIVE,
    EVENT_FEEDBACK_POSITIVE,
)
from bot import (
    _FEEDBACK_EVENTS,
    _feedback_keyboard,
    _handle_coach_forum_message,
    _split_message,
    handle_unsupported,
    handle_video,
)
from config import Settings


def _coach_forum_settings() -> Settings:
    return Settings(
        telegram_token="t",
        gemini_api_key="g",
        gemini_model_pro="m",
        gemini_model_free="f",
        admin_user_ids=(1,),
        coach_user_ids=(42,),
        coach_forum_chat_id=-100123,
    )


def _make_coach_forum_update(*, text=None, photo=None, video=None, video_note=None):
    update = MagicMock()
    message = MagicMock()
    message.chat_id = -100123
    message.message_thread_id = 77
    message.message_id = 555
    message.from_user.id = 42
    message.text = text
    message.caption = None
    message.photo = photo
    message.video = video
    message.video_note = video_note
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
    message.reply_text = AsyncMock()
    update.message = message
    return update


def _make_coach_context(settings: Settings):
    context = MagicMock()
    context.user_data = {}
    context.application.bot_data = {"settings": settings}
    context.bot.send_message = AsyncMock()
    context.bot.copy_message = AsyncMock()
    return context


def test_coach_forum_text_goes_to_player():
    settings = _coach_forum_settings()
    update = _make_coach_forum_update(text="Смотри на кисть")
    context = _make_coach_context(settings)

    async def _run():
        with (
            patch(
                "bot.storage.get_player_by_forum_thread",
                return_value={"user_id": 99},
            ),
            patch("bot.storage.get_user_language_code", return_value="ru"),
            patch(
                "bot.storage.get_latest_review_job_for_thread",
                return_value={"id": 7},
            ),
            patch("bot.storage.append_coach_eval_delta") as append_delta,
        ):
            assert await _handle_coach_forum_message(update, context) is True
            append_delta.assert_called_once()
            assert append_delta.call_args.args[0] == 7
            assert "кисть" in append_delta.call_args.args[1]

    asyncio.run(_run())
    assert context.bot.send_message.await_count == 1
    assert context.bot.send_message.await_args.kwargs["chat_id"] == 99
    assert "кисть" in context.bot.send_message.await_args.kwargs["text"]
    assert context.bot.copy_message.await_count == 0
    update.message.reply_text.assert_awaited()


def test_coach_forum_photo_copied_to_player():
    settings = _coach_forum_settings()
    update = _make_coach_forum_update(photo=[MagicMock()])
    context = _make_coach_context(settings)

    async def _run():
        with (
            patch(
                "bot.storage.get_player_by_forum_thread",
                return_value={"user_id": 99},
            ),
            patch("bot.storage.get_user_language_code", return_value="ru"),
            patch(
                "bot.storage.get_latest_review_job_for_thread",
                return_value={"id": 7},
            ),
            patch("bot.storage.append_coach_eval_delta"),
        ):
            assert await _handle_coach_forum_message(update, context) is True

    asyncio.run(_run())
    assert context.bot.send_message.await_count == 1
    assert "тренера" in context.bot.send_message.await_args.kwargs["text"].lower()
    context.bot.copy_message.assert_awaited_once_with(
        chat_id=99,
        from_chat_id=-100123,
        message_id=555,
    )


def test_handle_video_in_coach_forum_does_not_start_analysis():
    settings = _coach_forum_settings()
    update = _make_coach_forum_update(video=MagicMock())
    context = _make_coach_context(settings)

    async def _run():
        with (
            patch(
                "bot.storage.get_player_by_forum_thread",
                return_value={"user_id": 99},
            ),
            patch("bot.storage.get_user_language_code", return_value="en"),
            patch(
                "bot.storage.get_latest_review_job_for_thread",
                return_value={"id": 7},
            ),
            patch("bot.storage.append_coach_eval_delta"),
            patch("bot._touch_user", new=AsyncMock()) as touch,
        ):
            await handle_video(update, context)
            touch.assert_not_awaited()

    asyncio.run(_run())
    context.bot.copy_message.assert_awaited_once()
    assert update.message.reply_text.await_count == 1


def test_handle_unsupported_in_coach_forum_forwards_voice():
    settings = _coach_forum_settings()
    update = _make_coach_forum_update()
    update.message.voice = MagicMock()
    context = _make_coach_context(settings)

    async def _run():
        with (
            patch(
                "bot.storage.get_player_by_forum_thread",
                return_value={"user_id": 99},
            ),
            patch("bot.storage.get_user_language_code", return_value="ru"),
            patch(
                "bot.storage.get_latest_review_job_for_thread",
                return_value={"id": 7},
            ),
            patch("bot.storage.append_coach_eval_delta"),
        ):
            await handle_unsupported(update, context)

    asyncio.run(_run())
    context.bot.copy_message.assert_awaited_once()
    # Не должен отвечать «unsupported»
    assert "не поддерживаются" not in (
        update.message.reply_text.await_args.args[0].lower()
        if update.message.reply_text.await_args
        else ""
    )


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
    with (
        patch.object(storage, "DB_PATH", tmp_path / "t.db"),
        patch.object(billing, "MONETIZATION_ENABLED", True),
    ):
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


def test_coach_eval_callback_saves_rating(tmp_path):
    from bot import handle_coach_eval_callback

    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        job_id = storage.create_review_job(99, video_file_id="v", draft_text="draft")
        settings = _coach_forum_settings()
        query = MagicMock()
        query.data = f"ce:r:{job_id}:ok"
        query.from_user.id = 42
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update = MagicMock()
        update.callback_query = query
        context = _make_coach_context(settings)

        async def _run():
            await handle_coach_eval_callback(update, context)

        asyncio.run(_run())
        query.answer.assert_awaited()
        saved = storage.get_coach_evaluation(job_id)
        assert saved is not None
        assert saved["rating"] == "ok"
        query.edit_message_text.assert_awaited()
