import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import billing
import review
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


def _player_update(text: str, user_id: int = 7):
    user = MagicMock()
    user.id = user_id
    user.username = "ann"
    user.first_name = "Ann"
    user.last_name = None
    user.language_code = "ru"
    update = MagicMock()
    update.message = MagicMock()
    update.message.text = text
    update.message.from_user = user
    update.message.chat.id = user_id
    update.message.reply_text = AsyncMock()
    update.effective_user = user
    return update


def test_off_topic_reply_is_fixed_and_not_saved_as_note(tmp_path):
    from analyzer import AnalysisResult
    from bot import SESSION_KEY, _process_followup
    from pricing import Usage

    with patch.object(storage, "DB_PATH", tmp_path / "notes.db"):
        storage.set_followup_scope(True)
        player_id = storage.upsert_user(7, "ann", "Ann", None, "ru")
        storage.save_active_session(
            player_id,
            {"analysis": "отчёт", "history": [], "stroke": "forehand"},
        )
        context = MagicMock()
        context.user_data = {"user_id": player_id}
        context.bot.send_chat_action = AsyncMock()
        analyzer = MagicMock()
        analyzer._model = "m"
        analyzer.chat.return_value = AnalysisResult(
            text="OUT_OF_SCOPE",
            usage=Usage(),
            model="m",
        )
        context.application.bot_data = {"analyzer": analyzer, "settings": None}
        sent = []

        async def _send(_ctx, _chat_id, text, reply_markup=None):
            sent.append(text)

        async def _run():
            with (
                patch("bot.services.load_analysis_context", return_value={}),
                patch("bot._cabinet_notify", new=AsyncMock()),
                patch("bot.storage.log_usage"),
                patch("bot._send_formatted", new=_send),
            ):
                await _process_followup(
                    context,
                    context.user_data,
                    7,
                    "напиши стих",
                    lang="ru",
                    language_code="ru",
                )

        asyncio.run(_run())

        assert sent == [
            "Могу отвечать только по этому разбору и по теннису. "
            "По другим темам помочь не могу."
        ]
        history = context.user_data[SESSION_KEY]["history"]
        assert history[-1]["user"] == "напиши стих"
        assert history[-1]["assistant"] == sent[0]
        assert storage.recent_player_notes(player_id) == []


def test_new_analysis_asks_before_reset_and_keep_leaves_the_chat(tmp_path):
    from bot import NEW_CONFIRM_PENDING_KEY, handle_text, new_command

    with patch.object(storage, "DB_PATH", tmp_path / "new.db"):
        storage.set_followup_scope(True)
        player_id = storage.upsert_user(7, "ann", "Ann", None, "ru")
        storage.save_active_session(
            player_id,
            {"analysis": "отчёт", "history": [{"user": "q", "assistant": "a"}]},
        )
        update = _player_update("🔄 Новый разбор")
        context = MagicMock()
        context.user_data = {}
        context.application.bot_data = {}

        async def _ask():
            await new_command(update, context)

        asyncio.run(_ask())
        assert context.user_data[NEW_CONFIRM_PENDING_KEY] is True
        assert storage.load_active_session(player_id)["analysis"] == "отчёт"
        prompt = update.message.reply_text.await_args.args[0]
        assert "сбросится" in prompt

        update.message.text = "какой курс доллара"
        update.message.reply_text = AsyncMock()

        async def _stray():
            with patch(
                "bot._handle_coach_forum_message",
                new=AsyncMock(return_value=False),
            ):
                await handle_text(update, context)

        asyncio.run(_stray())
        assert context.user_data[NEW_CONFIRM_PENDING_KEY] is True
        assert "сбросится" in update.message.reply_text.await_args.args[0]
        assert storage.load_active_session(player_id)["analysis"] == "отчёт"

        update.message.text = "Оставить"
        update.message.reply_text = AsyncMock()

        async def _keep():
            with patch(
                "bot._handle_coach_forum_message",
                new=AsyncMock(return_value=False),
            ):
                await handle_text(update, context)

        asyncio.run(_keep())
        assert NEW_CONFIRM_PENDING_KEY not in context.user_data
        assert storage.load_active_session(player_id)["history"][0]["user"] == "q"
        assert update.message.reply_text.await_args.args[0] == "Продолжаем этот разбор."


def test_new_analysis_reset_clears_only_the_chat(tmp_path):
    from bot import NEW_CONFIRM_PENDING_KEY, handle_text, new_command

    with patch.object(storage, "DB_PATH", tmp_path / "reset.db"):
        storage.set_followup_scope(True)
        player_id = storage.upsert_user(7, "ann", "Ann", None, "ru")
        storage.save_active_session(player_id, {"analysis": "отчёт", "history": []})
        update = _player_update("/new")
        context = MagicMock()
        context.user_data = {}
        context.application.bot_data = {}

        async def _ask():
            await new_command(update, context)

        asyncio.run(_ask())
        update.message.text = "Сбросить"
        update.message.reply_text = AsyncMock()

        async def _reset():
            with patch(
                "bot._handle_coach_forum_message",
                new=AsyncMock(return_value=False),
            ):
                await handle_text(update, context)

        asyncio.run(_reset())
        assert NEW_CONFIRM_PENDING_KEY not in context.user_data
        assert storage.load_active_session(player_id) is None
        assert (
            update.message.reply_text.await_args.args[0]
            == "Переписка сброшена. Отправьте видео для разбора."
        )


def test_new_without_analysis_asks_for_a_video(tmp_path):
    from bot import new_command

    with patch.object(storage, "DB_PATH", tmp_path / "empty.db"):
        storage.set_followup_scope(True)
        storage.upsert_user(7, "ann", "Ann", None, "ru")
        update = _player_update("/new")
        context = MagicMock()
        context.user_data = {}
        context.application.bot_data = {}

        async def _run():
            await new_command(update, context)

        asyncio.run(_run())
        assert (
            update.message.reply_text.await_args.args[0]
            == "Отправьте видео для разбора."
        )


def test_scope_off_keeps_the_old_new_analysis_flow(tmp_path):
    from bot import NEW_CONFIRM_PENDING_KEY, new_command

    with patch.object(storage, "DB_PATH", tmp_path / "off.db"):
        player_id = storage.upsert_user(7, "ann", "Ann", None, "ru")
        storage.save_active_session(player_id, {"analysis": "отчёт", "history": []})
        update = _player_update("/new")
        context = MagicMock()
        context.user_data = {}
        context.application.bot_data = {"admin_user_ids": ()}

        async def _run():
            await new_command(update, context)

        asyncio.run(_run())
        assert NEW_CONFIRM_PENDING_KEY not in context.user_data
        assert storage.load_active_session(player_id) is None
        assert (
            update.message.reply_text.await_args.args[0]
            == "Диалог сброшен. Отправьте новое видео для разбора."
        )


def test_admin_sees_new_flow_while_scope_is_off(tmp_path):
    from bot import NEW_CONFIRM_PENDING_KEY, new_command

    with patch.object(storage, "DB_PATH", tmp_path / "admin.db"):
        player_id = storage.upsert_user(7, "ann", "Ann", None, "ru")
        storage.save_active_session(player_id, {"analysis": "отчёт", "history": []})
        update = _player_update("/new")
        context = MagicMock()
        context.user_data = {}
        context.application.bot_data = {"admin_user_ids": (7,)}

        async def _run():
            await new_command(update, context)

        asyncio.run(_run())
        assert context.user_data[NEW_CONFIRM_PENDING_KEY] is True
        assert storage.load_active_session(player_id)["analysis"] == "отчёт"


def test_scope_off_keeps_model_text_and_saves_the_note(tmp_path):
    from analyzer import AnalysisResult
    from bot import _process_followup
    from pricing import Usage

    with patch.object(storage, "DB_PATH", tmp_path / "chat-off.db"):
        player_id = storage.upsert_user(7, "ann", "Ann", None, "ru")
        storage.save_active_session(player_id, {"analysis": "отчёт", "history": []})
        context = MagicMock()
        context.user_data = {"user_id": player_id}
        context.bot.send_chat_action = AsyncMock()
        context.application.bot_data = {
            "analyzer": MagicMock(_model="m"),
            "admin_user_ids": (),
            "settings": None,
        }
        context.application.bot_data["analyzer"].chat.return_value = AnalysisResult(
            text="OUT_OF_SCOPE",
            usage=Usage(),
            model="m",
        )
        sent = []

        async def _send(_ctx, _chat_id, text, reply_markup=None):
            sent.append(text)

        async def _run():
            with (
                patch("bot.services.load_analysis_context", return_value={}),
                patch("bot._cabinet_notify", new=AsyncMock()),
                patch("bot.storage.log_usage"),
                patch("bot._send_formatted", new=_send),
            ):
                await _process_followup(
                    context,
                    context.user_data,
                    7,
                    "напиши стих",
                    lang="ru",
                    language_code="ru",
                )

        asyncio.run(_run())
        assert sent == ["OUT_OF_SCOPE"]
        notes = storage.recent_player_notes(player_id)
        assert [item["text"] for item in notes] == ["напиши стих"]


def test_followup_forwards_bot_reply_to_cabinet(tmp_path):
    from analyzer import AnalysisResult
    from bot import _process_followup
    from pricing import Usage

    with patch.object(storage, "DB_PATH", tmp_path / "cabinet-reply.db"):
        player_id = storage.upsert_user(7, "ann", "Ann", None, "ru")
        storage.save_active_session(player_id, {"analysis": "отчёт", "history": []})
        context = MagicMock()
        context.user_data = {"user_id": player_id}
        context.bot.send_chat_action = AsyncMock()
        context.application.bot_data = {
            "analyzer": MagicMock(_model="m"),
            "admin_user_ids": (),
            "settings": None,
        }
        context.application.bot_data["analyzer"].chat.return_value = AnalysisResult(
            text="Кисть впереди контакта.",
            usage=Usage(),
            model="m",
        )
        notified = []

        async def _notify(_ctx, user_id, text, user=None):
            notified.append((user_id, text))

        async def _send(_ctx, _chat_id, text, reply_markup=None):
            return None

        async def _run():
            with (
                patch("bot.services.load_analysis_context", return_value={}),
                patch("bot._cabinet_notify", new=_notify),
                patch("bot.storage.log_usage"),
                patch("bot._send_formatted", new=_send),
            ):
                await _process_followup(
                    context,
                    context.user_data,
                    7,
                    "куда смотреть кисть",
                    question_label="Кисть",
                    lang="ru",
                    language_code="ru",
                )

        asyncio.run(_run())
        assert notified[0][0] == player_id
        assert "Вопрос игрока" in notified[0][1]
        assert "куда смотреть кисть" in notified[0][1]
        assert notified[1][0] == player_id
        assert "Ответ бота" in notified[1][1]
        assert "Кисть впереди контакта." in notified[1][1]
        assert "(Кисть)" in notified[1][1]


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
            patch("bot.identity.telegram_id_for", return_value=99),
            patch("bot.storage.get_user_language_code", return_value="ru"),
            patch(
                "bot.storage.get_pending_review_job_for_thread",
                return_value=None,
            ),
            patch("bot.storage.save_coach_correction") as save_corr,
        ):
            assert await _handle_coach_forum_message(update, context) is True
            save_corr.assert_not_called()

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
            patch("bot.identity.telegram_id_for", return_value=99),
            patch("bot.storage.get_user_language_code", return_value="ru"),
            patch(
                "bot.storage.get_pending_review_job_for_thread",
                return_value=None,
            ),
            patch("bot.storage.save_coach_correction"),
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
            patch("bot.identity.telegram_id_for", return_value=99),
            patch("bot.storage.get_user_language_code", return_value="en"),
            patch(
                "bot.storage.get_pending_review_job_for_thread",
                return_value=None,
            ),
            patch("bot.storage.save_coach_correction"),
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
            patch("bot.identity.telegram_id_for", return_value=99),
            patch("bot.storage.get_user_language_code", return_value="ru"),
            patch(
                "bot.storage.get_pending_review_job_for_thread",
                return_value=None,
            ),
            patch("bot.storage.save_coach_correction"),
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
                patch("bot._touch_user", new=AsyncMock(return_value=88)),
                patch("bot._lang_from_update", return_value="ru"),
                patch("bot.is_onboarding_active", return_value=False),
                patch("bot.is_reset_pending", return_value=False),
            ):
                await handle_video(update, context)

        asyncio.run(_run())
        assert update.message.reply_text.await_count == 1
        text = update.message.reply_text.await_args.args[0]
        assert "лимит" in text.lower()


def test_coach_action_callback_sets_fix_mode(tmp_path):
    from bot import handle_coach_eval_callback

    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        job_id = storage.create_review_job(99, video_file_id="v", draft_text="draft")
        storage.update_review_job(job_id, forum_chat_id=-100123, message_thread_id=77)
        settings = _coach_forum_settings()
        query = MagicMock()
        query.data = f"ce:a:{job_id}:fix"
        query.from_user.id = 42
        query.answer = AsyncMock()
        query.edit_message_reply_markup = AsyncMock()
        query.message.reply_text = AsyncMock()
        update = MagicMock()
        update.callback_query = query
        context = _make_coach_context(settings)

        async def _run():
            await handle_coach_eval_callback(update, context)

        asyncio.run(_run())
        query.answer.assert_awaited()
        job = storage.get_review_job(job_id)
        assert job["pending_coach_action"] == "fix"
        query.edit_message_reply_markup.assert_awaited()
        query.message.reply_text.assert_awaited()
        hint = query.message.reply_text.await_args.args[0]
        assert "эталон" in hint.lower()


def test_coach_action_callback_ok_pins_draft(tmp_path):
    from bot import handle_coach_eval_callback

    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        job_id = storage.create_review_job(99, video_file_id="v", draft_text="draft")
        storage.update_review_job(job_id, forum_chat_id=-100123, message_thread_id=77)
        storage.mark_review_sent(
            job_id, status=review.STATUS_AI_SENT, final_text="draft"
        )
        storage.set_pending_coach_action(job_id, review.ACTION_FIX_AI)
        settings = _coach_forum_settings()
        query = MagicMock()
        query.data = f"ce:a:{job_id}:ok"
        query.from_user.id = 42
        query.answer = AsyncMock()
        query.edit_message_reply_markup = AsyncMock()
        query.message.reply_text = AsyncMock()
        update = MagicMock()
        update.callback_query = query
        context = _make_coach_context(settings)

        async def _run():
            await handle_coach_eval_callback(update, context)

        with patch("bot._deliver_review_to_player", new_callable=AsyncMock) as deliver:
            asyncio.run(_run())
            deliver.assert_not_awaited()
        query.answer.assert_awaited()
        job = storage.get_review_job(job_id)
        assert not job["pending_coach_action"]
        assert job["status"] == review.STATUS_SENT_COACH
        assert job["final_text"] == "draft"
        row = storage.get_coach_evaluation(job_id)
        assert row["rating"] == review.RATING_OK
        hint = query.message.reply_text.await_args.args[0]
        assert "закрепл" in hint.lower()
        context.bot.send_message.assert_not_awaited()


def test_coach_ok_does_not_overwrite_fallback(tmp_path):
    from bot import handle_coach_eval_callback

    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        job_id = storage.create_review_job(99, video_file_id="v", draft_text="draft")
        storage.update_review_job(job_id, forum_chat_id=-100123, message_thread_id=77)
        storage.mark_review_sent(
            job_id, status=review.STATUS_SENT_FALLBACK, final_text="fallback"
        )
        settings = _coach_forum_settings()
        query = MagicMock()
        query.data = f"ce:a:{job_id}:ok"
        query.from_user.id = 42
        query.answer = AsyncMock()
        query.edit_message_reply_markup = AsyncMock()
        query.message.reply_text = AsyncMock()
        update = MagicMock()
        update.callback_query = query
        context = _make_coach_context(settings)

        async def _run():
            await handle_coach_eval_callback(update, context)

        asyncio.run(_run())
        job = storage.get_review_job(job_id)
        assert job["status"] == review.STATUS_SENT_FALLBACK
        assert job["final_text"] == "fallback"


def test_coach_forum_fix_saves_correction_not_player(tmp_path):
    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        storage.save_player_forum_topic(99, -100123, 77, title="t")
        job_id = storage.create_review_job(99, video_file_id="v", draft_text="AI draft")
        storage.update_review_job(job_id, forum_chat_id=-100123, message_thread_id=77)
        storage.set_pending_coach_action(job_id, review.ACTION_FIX_AI)
        settings = _coach_forum_settings()
        update = _make_coach_forum_update(text="Исправленный разбор: кисть впереди")
        context = _make_coach_context(settings)

        async def _run():
            assert await _handle_coach_forum_message(update, context) is True

        asyncio.run(_run())
        assert context.bot.send_message.await_count == 0
        context.bot.copy_message.assert_not_awaited()
        row = storage.get_coach_evaluation(job_id)
        assert row is not None
        assert "кисть впереди" in row["delta_text"]
        assert "Эталон" in update.message.reply_text.await_args.args[0]


def test_coach_forum_fix_media_stays_in_cabinet(tmp_path):
    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        storage.save_player_forum_topic(99, -100123, 77, title="t")
        job_id = storage.create_review_job(99, video_file_id="v", draft_text="d")
        storage.update_review_job(job_id, forum_chat_id=-100123, message_thread_id=77)
        storage.set_pending_coach_action(job_id, review.ACTION_FIX_AI)
        settings = _coach_forum_settings()
        update = _make_coach_forum_update(video_note=MagicMock())
        context = _make_coach_context(settings)

        async def _run():
            assert await _handle_coach_forum_message(update, context) is True

        asyncio.run(_run())
        context.bot.copy_message.assert_not_awaited()
        assert "текст" in update.message.reply_text.await_args.args[0].lower()


def test_post_intake_video_to_cabinet_sends_video_with_stroke():
    from bot import _post_intake_video_to_cabinet

    settings = _coach_forum_settings()
    context = _make_coach_context(settings)
    context.bot.send_video = AsyncMock()
    pending = {
        "file_id": "vid123",
        "duration": 12,
        "comment": "локоть",
    }
    user = MagicMock()
    user.first_name = "Ann"
    user.username = "ann"

    async def _run():
        with patch(
            "bot.cabinet.ensure_player_topic", new=AsyncMock(return_value=77)
        ) as ensure:
            ok = await _post_intake_video_to_cabinet(
                context,
                99,
                pending,
                {"stroke": "forehand", "look": "technique"},
                user=user,
            )
            ensure.assert_awaited()
            return ok

    assert asyncio.run(_run()) is True
    header = context.bot.send_message.await_args.kwargs["text"]
    assert "готово к разбору" in header.lower()
    assert "Форхенд" in header or "форхенд" in header.lower()
    assert context.bot.send_message.await_args.kwargs["message_thread_id"] == 77
    context.bot.send_video.assert_awaited_once_with(
        chat_id=-100123,
        message_thread_id=77,
        video="vid123",
    )


def test_begin_analysis_sends_cabinet_video_before_ai():
    from bot import _begin_analysis_after_intake
    from video_intake import get_intake_answers, start_intake_state

    settings = _coach_forum_settings()
    update = MagicMock()
    update.message = MagicMock()
    update.message.from_user.id = 99
    update.message.from_user.first_name = "Ann"
    update.message.chat_id = 99
    update.message.reply_text = AsyncMock()
    context = _make_coach_context(settings)
    context.user_data["user_id"] = 99
    context.user_data["player_id"] = 99
    context.user_data["pending_video"] = {
        "file_id": "vid",
        "mime_type": "video/mp4",
        "comment": "",
        "duration": 10,
        "video_context": None,
    }
    start_intake_state(context.user_data)
    get_intake_answers(context.user_data)["stroke"] = "serve"
    get_intake_answers(context.user_data)["look"] = "contact"

    async def _run():
        with (
            patch(
                "bot._post_intake_video_to_cabinet", new=AsyncMock(return_value=True)
            ) as post_video,
            patch("bot._run_video_analysis", new=AsyncMock()) as run_ai,
        ):
            await _begin_analysis_after_intake(update, context, "ru", "ru")
            post_video.assert_awaited()
            run_ai.assert_awaited()
            assert update.message.reply_text.await_count == 1
            ack = update.message.reply_text.await_args.args[0]
            assert "AI-помощник" in ack
            assert "Анализирую технику" not in ack
            assert post_video.await_count == 1
            assert (
                post_video.await_args.args[3]
                == context.user_data["pending_video"]["video_context"]
            )

    asyncio.run(_run())
    pending = context.user_data["pending_video"]
    assert pending["video_context"] == {"stroke": "serve", "look": "contact"}
    assert pending["cabinet_video_sent"] is True


def test_post_ios_review_to_forum_sends_channel_and_deletes(tmp_path):
    from pathlib import Path

    from bot import post_ios_review_to_forum

    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"mp4")
        pid = storage.get_or_create_apple_player("sub-ios-forum")
        job_id = storage.create_review_job(
            pid,
            video_file_id="ios:" + str(video),
            draft_text="## Краткое резюме\nok",
            focus_text="Кисть",
            source_channel=storage.CHANNEL_IOS,
        )
        settings = _coach_forum_settings()
        application = MagicMock()
        application.bot_data = {"settings": settings}
        application.bot.send_message = AsyncMock()
        application.bot.send_video = AsyncMock()

        async def _run():
            with patch(
                "bot.cabinet.ensure_player_topic", new=AsyncMock(return_value=77)
            ):
                await post_ios_review_to_forum(application, job_id, pid, str(video))

        asyncio.run(_run())
        job = storage.get_review_job(job_id)
        assert job["status"] == review.STATUS_AI_SENT
        assert job["message_thread_id"] == 77
        texts = [
            call.kwargs["text"] for call in application.bot.send_message.await_args_list
        ]
        assert any("Канал: iOS" in text for text in texts)
        application.bot.send_video.assert_awaited()
        assert not Path(video).exists()


def test_review_header_includes_acquisition_source(tmp_path):
    from bot import _ApplicationContext, _post_review_job_to_forum

    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        pid = storage.get_or_create_telegram_player(501)
        storage.set_acquisition_source_if_empty(pid, "minsk_mir")
        job_id = storage.create_review_job(
            pid,
            video_file_id="file-501",
            draft_text="## Краткое резюме\nok",
            focus_text="Кисть",
        )
        settings = _coach_forum_settings()
        application = MagicMock()
        application.bot_data = {"settings": settings}
        application.bot.send_message = AsyncMock()
        application.bot.send_video = AsyncMock()

        async def _run():
            with patch(
                "bot.cabinet.ensure_player_topic", new=AsyncMock(return_value=77)
            ):
                posted = await _post_review_job_to_forum(
                    _ApplicationContext(application), job_id, pid
                )
                assert posted is True

        asyncio.run(_run())
        texts = [
            call.kwargs["text"] for call in application.bot.send_message.await_args_list
        ]
        header = next(text for text in texts if text.startswith("🆕 Разбор"))
        assert "Источник: Минск-Мир" in header
        assert "Канал:" not in header


def test_post_ios_review_forum_fail_still_ai_sent(tmp_path):
    from pathlib import Path

    from bot import post_ios_review_to_forum

    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"mp4")
        pid = storage.get_or_create_apple_player("sub-ios-forum-fail")
        job_id = storage.create_review_job(
            pid,
            video_file_id="ios:" + str(video),
            draft_text="draft",
            source_channel=storage.CHANNEL_IOS,
        )
        settings = _coach_forum_settings()
        application = MagicMock()
        application.bot_data = {"settings": settings}
        application.bot.send_message = AsyncMock()

        async def _run():
            with patch(
                "bot.cabinet.ensure_player_topic", new=AsyncMock(return_value=None)
            ):
                await post_ios_review_to_forum(application, job_id, pid, str(video))

        asyncio.run(_run())
        job = storage.get_review_job(job_id)
        assert job["status"] == review.STATUS_AI_SENT
        application.bot.send_message.assert_not_awaited()
        assert not Path(video).exists()


def test_profile_language_button_sets_bot_and_ai_lang(tmp_path):
    from bot import _lang_from_update, handle_text

    with patch.object(storage, "DB_PATH", tmp_path / "t.db"):
        storage.upsert_user(7, "ann", "Ann", None, "en")
        user = MagicMock()
        user.id = 7
        user.username = "ann"
        user.first_name = "Ann"
        user.last_name = None
        user.language_code = "de"
        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "🇷🇺 Русский"
        update.message.from_user = user
        update.message.chat.id = 7
        update.message.reply_text = AsyncMock()
        update.effective_user = user
        context = MagicMock()
        context.user_data = {}
        context.bot.set_my_commands = AsyncMock()

        async def _run():
            with (
                patch(
                    "bot._handle_survey_other_text",
                    new=AsyncMock(return_value=False),
                ),
                patch(
                    "bot._handle_coach_forum_message",
                    new=AsyncMock(return_value=False),
                ),
                patch(
                    "bot._handle_player_coach_message",
                    new=AsyncMock(return_value=False),
                ),
            ):
                await handle_text(update, context)

        asyncio.run(_run())
        assert storage.get_preferred_language(7) == "ru"
        assert storage.get_user_language_code(7) == "ru"
        assert context.user_data["lang"] == "ru"
        assert context.user_data["language_code"] == "ru"

        followup = MagicMock()
        followup.effective_user = user
        fresh = MagicMock()
        fresh.user_data = {}
        assert _lang_from_update(followup, fresh) == "ru"
        assert fresh.user_data["language_code"] == "ru"


def test_delete_tracked_messages_keeps_the_video():
    from bot import _CLEANUP_KEY, _delete_tracked_messages, _remember_cleanup

    context = MagicMock()
    context.user_data = {}
    context.bot.delete_message = AsyncMock()
    _remember_cleanup(context.user_data, 11)
    _remember_cleanup(context.user_data, "12")
    _remember_cleanup(context.user_data, 13)

    async def _run():
        await _delete_tracked_messages(context, 99)

    asyncio.run(_run())
    deleted = [
        call.kwargs["message_id"] for call in context.bot.delete_message.await_args_list
    ]
    assert deleted == [13, 11]
    assert _CLEANUP_KEY not in context.user_data


def test_present_analysis_sends_summary_then_first_observation(tmp_path):
    from bot import _present_analysis_to_player

    report = (
        "## Краткое резюме\n"
        "Коротко про удар.\n\n"
        "## Разбор по категориям\n"
        "### Техника удара\n"
        "**Наблюдение:** Локоть высоко.\n"
        "**Критичность:** 🔴 Критично\n\n"
        "**Наблюдение:** Нет сплит-степа.\n"
        "**Критичность:** 🟠 Важно\n"
    )
    context = MagicMock()
    context.user_data = {}
    context.bot.send_message = AsyncMock()

    async def _run():
        with (
            patch.object(storage, "DB_PATH", tmp_path / "t.db"),
            patch("bot.asyncio.sleep", new=AsyncMock()) as sleep,
        ):
            await _present_analysis_to_player(
                context,
                chat_id=7,
                user_id=7,
                lang="ru",
                language_code="ru",
                report=report,
                scores={},
                stroke="forehand",
                focus_text="Опустить локоть",
                drill_text="Пауза до отскока",
                drill_id=None,
            )
            sleep.assert_awaited_once_with(2)

    asyncio.run(_run())
    texts = [call.kwargs["text"] for call in context.bot.send_message.await_args_list]
    assert len(texts) == 2
    assert "Кратко по видео" in texts[0]
    assert "Готово" not in texts[0]
    assert "Локоть высоко" in texts[1]
    assert "сплит" not in texts[1].lower()
    markup = context.bot.send_message.await_args_list[1].kwargs["reply_markup"]
    callbacks = [
        button.callback_data for row in markup.inline_keyboard for button in row
    ]
    assert callbacks == ["d:err:deep:0", "d:obs:next:0"]
    assert context.user_data["analysis_dialog"]["shown_count"] == 1
    assert context.user_data["analysis_dialog"]["focus_text"] == "Опустить локоть"
