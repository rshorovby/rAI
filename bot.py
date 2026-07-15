import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Callable, Optional

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import storage
from analysis_dialog import (
    clear_dialog,
    current_error_text,
    format_error_card,
    format_section_title,
    format_summary_message,
    get_dialog,
    keyboard_after_drills,
    keyboard_after_error_deep,
    keyboard_after_next,
    keyboard_after_prio,
    keyboard_after_video,
    keyboard_categories,
    keyboard_error,
    keyboard_finish,
    keyboard_summary,
    keyboard_top3,
    start_dialog,
)
from analytics import (
    EVENT_ANALYSIS_FAILED,
    EVENT_ANALYSIS_SUCCESS,
    EVENT_FEEDBACK_CLEAR,
    EVENT_FEEDBACK_NEGATIVE,
    EVENT_FEEDBACK_POSITIVE,
    EVENT_ONBOARDING_COMPLETED,
    EVENT_ONBOARDING_SKIPPED,
    EVENT_ONBOARDING_STARTED,
    EVENT_PROFILE_RESET,
    EVENT_VIDEO_SENT,
    format_analytics_report,
)
from analyzer import VideoAnalyzer
from config import Settings
from errors import format_analysis_error
from formatting import markdown_to_html
from i18n import (
    UI_LANGS,
    get_stored_lang,
    get_stored_language_code,
    sync_user_lang,
    t,
)
from onboarding import (
    advance_step,
    build_profile_dict,
    clear_onboarding_state,
    clear_reset_pending,
    get_onboarding_answers,
    get_onboarding_step,
    is_edit_profile_text,
    is_injuries_none_text,
    is_onboarding_active,
    is_reset_confirm_no,
    is_reset_confirm_yes,
    is_reset_pending,
    is_reset_profile_text,
    is_skip_text,
    match_step_answer,
    onboarding_keyboard,
    profile_actions_keyboard,
    profile_reset_confirm_keyboard,
    set_reset_pending,
    start_onboarding_state,
)
from pose_analysis import cleanup_overlay, create_pose_overlay
from video_intake import (
    advance_intake_step,
    build_video_context,
    clear_intake_state,
    get_intake_answers,
    get_intake_step,
    intake_keyboard,
    is_intake_active,
    is_intake_skip_text,
    match_intake_answer,
    start_intake_state,
)

logger = logging.getLogger(__name__)

MAX_VIDEO_SIZE_MB = 20
SUPPORTED_MIME_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/mpeg",
    "video/x-msvideo",
}

SESSION_KEY = "rally_session"
MAX_HISTORY_TURNS = 10

# callback_data → ключи i18n (подпись кнопки, промпт для модели)
QUICK_QUESTIONS = {
    "main": (
        "quick_main_label",
        "quick_main_prompt",
    ),
    "exercises": (
        "quick_exercises_label",
        "quick_exercises_prompt",
    ),
}

_QUICK_PROMPTS = {
    "ru": {
        "quick_main_label": "🔴 Разбор главной ошибки",
        "quick_main_prompt": (
            "Сделай подробный разбор самой критичной ошибки из анализа: что именно "
            "происходит в технике, почему это снижает эффективность и травмоопасно, "
            "и пошагово — как это исправить на тренировке."
        ),
        "quick_exercises_label": "🏋️ 3 упражнения",
        "quick_exercises_prompt": (
            "Назови 3 упражнения, на которых игроку стоит сосредоточиться для улучшения "
            "техники, исходя из разбора. Для каждого: на какую проблему направлено, "
            "как выполнять и сколько повторений/подходов."
        ),
    },
    "en": {
        "quick_main_label": "🔴 Main error breakdown",
        "quick_main_prompt": (
            "Give a detailed breakdown of the most critical error from the analysis: "
            "what exactly happens in the technique, why it reduces effectiveness and "
            "injury risk, and step-by-step how to fix it in practice."
        ),
        "quick_exercises_label": "🏋️ 3 drills",
        "quick_exercises_prompt": (
            "Name 3 drills the player should focus on to improve technique based on "
            "the analysis. For each: which issue it targets, how to perform it, "
            "and reps/sets."
        ),
    },
}


def _telegram_user_from_update(update: Update):
    if update.message:
        return update.message.from_user
    if update.callback_query:
        return update.callback_query.from_user
    return update.effective_user


async def _touch_user(update: Update) -> None:
    user = _telegram_user_from_update(update)
    if not user:
        return
    await asyncio.to_thread(
        storage.upsert_user,
        user.id,
        user.username,
        user.first_name,
        user.last_name,
        user.language_code,
    )


async def _log_event(user_id: int, event_type: str, payload: str = "") -> None:
    await asyncio.to_thread(storage.log_event, user_id, event_type, payload)


def _clear_user_state(user_data: dict) -> None:
    _clear_session(user_data)
    clear_intake_state(user_data)
    clear_onboarding_state(user_data)
    clear_reset_pending(user_data)
    clear_dialog(user_data)
    user_data.pop("pending_video", None)


async def _execute_profile_reset(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    lang: str,
    user_id: int,
) -> None:
    message = update.message
    if not message:
        return

    await asyncio.to_thread(storage.reset_player_data, user_id)
    await _log_event(user_id, EVENT_PROFILE_RESET)
    _clear_user_state(context.user_data)
    await _begin_onboarding(context, user_id, is_new_user=True)
    await _send_onboarding_question(message, lang, "level", intro=t(lang, "ob_intro"))


async def _show_profile(
    message,
    lang: str,
    user_id: int,
) -> None:
    text = await asyncio.to_thread(storage.format_profile_for_user, user_id, lang)
    await message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=profile_actions_keyboard(lang),
    )


async def _begin_onboarding(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    *,
    is_new_user: bool,
) -> None:
    start_onboarding_state(context.user_data)
    if is_new_user:
        await _log_event(user_id, EVENT_ONBOARDING_STARTED)


def _lang_from_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    code = update.effective_user.language_code if update.effective_user else None
    return sync_user_lang(context.user_data, code)


def _language_code_from_context(context: ContextTypes.DEFAULT_TYPE) -> str:
    return get_stored_language_code(context.user_data)


def _get_session(user_data: dict) -> dict:
    return user_data.setdefault(SESSION_KEY, {"analysis": None, "history": []})


def _clear_session(user_data: dict) -> None:
    user_data.pop(SESSION_KEY, None)


def _save_analysis(user_data: dict, report: str) -> None:
    user_data[SESSION_KEY] = {"analysis": report, "history": []}


def _get_user_id(user_data: dict) -> Optional[int]:
    return user_data.get("user_id")


def _bot_commands(lang: str) -> list[BotCommand]:
    return [
        BotCommand("start", t(lang, "cmd_start")),
        BotCommand("help", t(lang, "cmd_help")),
        BotCommand("profile", t(lang, "cmd_profile")),
        BotCommand("new", t(lang, "cmd_new")),
        BotCommand("history", t(lang, "cmd_history")),
    ]


def _main_menu_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(t(lang, "btn_help")), KeyboardButton(t(lang, "btn_new"))],
            [KeyboardButton(t(lang, "btn_history"))],
        ],
        resize_keyboard=True,
    )


def _retry_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(t(lang, "retry_button"), callback_data="retry")]]
    )


def _feedback_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t(lang, "feedback_useful"), callback_data="fb:pos"
                ),
                InlineKeyboardButton(
                    t(lang, "feedback_not_useful"), callback_data="fb:neg"
                ),
            ],
            [
                InlineKeyboardButton(
                    t(lang, "feedback_actionable"), callback_data="fb:clear"
                ),
            ],
        ]
    )


_FEEDBACK_EVENTS = {
    "pos": EVENT_FEEDBACK_POSITIVE,
    "neg": EVENT_FEEDBACK_NEGATIVE,
    "clear": EVENT_FEEDBACK_CLEAR,
}


def _quick_questions_keyboard(lang: str) -> InlineKeyboardMarkup:
    prompts = _QUICK_PROMPTS.get(lang, _QUICK_PROMPTS["en"])
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(prompts[label_key], callback_data=f"q:{key}")]
            for key, (label_key, _prompt_key) in QUICK_QUESTIONS.items()
        ]
    )


def _menu_handlers() -> dict[str, Callable]:
    handlers: dict[str, Callable] = {}
    for lang in UI_LANGS:
        handlers[t(lang, "btn_help")] = help_command
        handlers[t(lang, "btn_new")] = new_command
        handlers[t(lang, "btn_history")] = history_command
    return handlers


_MENU_HANDLERS: dict[str, Callable] = {}


def _split_message(text: str, limit: int = 4000) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > limit:
            if current:
                chunks.append(current.rstrip())
            current = line
        else:
            current += line
    if current:
        chunks.append(current.rstrip())
    return chunks


async def _send_onboarding_question(
    message,
    lang: str,
    step: str,
    *,
    intro: Optional[str] = None,
) -> None:
    parts = []
    if intro:
        parts.append(intro)
    parts.append(t(lang, f"ob_question_{step}"))
    await message.reply_text(
        "\n\n".join(parts),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=onboarding_keyboard(lang, step),
    )


async def _finish_onboarding_skip(
    update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str, user_id: int
) -> None:
    await asyncio.to_thread(storage.mark_profile_skipped, user_id)
    await _log_event(user_id, EVENT_ONBOARDING_SKIPPED)
    clear_onboarding_state(context.user_data)
    await update.message.reply_text(
        t(lang, "ob_skip_warning"),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_main_menu_keyboard(lang),
    )


async def _finish_onboarding_complete(
    update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str, user_id: int
) -> None:
    profile = build_profile_dict(get_onboarding_answers(context.user_data))
    await asyncio.to_thread(storage.save_player_profile, user_id, profile)
    await _log_event(user_id, EVENT_ONBOARDING_COMPLETED)
    clear_onboarding_state(context.user_data)
    await update.message.reply_text(
        t(lang, "ob_complete"),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_main_menu_keyboard(lang),
    )


async def _handle_onboarding_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    lang: str,
    user_text: str,
) -> None:
    message = update.message
    user_id = message.from_user.id
    context.user_data["user_id"] = user_id
    step = get_onboarding_step(context.user_data)
    if not step:
        return

    if is_skip_text(lang, user_text):
        await _finish_onboarding_skip(update, context, lang, user_id)
        return

    if step == "injuries":
        injuries = "" if is_injuries_none_text(lang, user_text) else user_text
        get_onboarding_answers(context.user_data)["injuries"] = injuries
        await _finish_onboarding_complete(update, context, lang, user_id)
        return

    value = match_step_answer(lang, step, user_text)
    if not value:
        await message.reply_text(
            t(lang, "ob_invalid_answer"),
            reply_markup=onboarding_keyboard(lang, step),
        )
        return

    get_onboarding_answers(context.user_data)[step] = value
    next_step = advance_step(context.user_data)
    if next_step:
        await _send_onboarding_question(message, lang, next_step)


async def _reply_formatted(message, text: str, **kwargs) -> None:
    try:
        await message.reply_text(
            markdown_to_html(text),
            parse_mode=ParseMode.HTML,
            **kwargs,
        )
    except BadRequest:
        logger.warning("HTML-разметка не прошла, отправляю plain text")
        await message.reply_text(text, **kwargs)


async def _send_formatted(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    **kwargs,
) -> None:
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=markdown_to_html(text),
            parse_mode=ParseMode.HTML,
            **kwargs,
        )
    except BadRequest:
        logger.warning("HTML-разметка не прошла, отправляю plain text")
        await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)


async def _process_followup(
    context: ContextTypes.DEFAULT_TYPE,
    user_data: dict,
    chat_id: int,
    user_text: str,
    *,
    question_label: Optional[str] = None,
    lang: Optional[str] = None,
    language_code: Optional[str] = None,
) -> None:
    ui_lang = lang or get_stored_lang(user_data)
    model_lang = language_code or get_stored_language_code(user_data)

    session = _get_session(user_data)
    analysis = session.get("analysis")
    if not analysis:
        raise RuntimeError(t(ui_lang, "no_session_internal"))

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    analyzer: VideoAnalyzer = context.application.bot_data["analyzer"]
    history: list[dict[str, str]] = session.get("history", [])

    user_id = _get_user_id(user_data)
    player_history = (
        await asyncio.to_thread(storage.get_player_history, user_id) if user_id else []
    )
    player_profile = (
        await asyncio.to_thread(storage.get_player_profile, user_id)
        if user_id
        else None
    )

    reply = await asyncio.to_thread(
        analyzer.chat,
        analysis,
        history,
        user_text,
        player_history,
        model_lang,
        player_profile,
    )
    logger.info("Ответ ИИ получен (%s символов)", len(reply))
    history.append({"user": user_text, "assistant": reply})
    session["history"] = history[-MAX_HISTORY_TURNS:]

    prefix = f"↳ {question_label}\n\n" if question_label else ""
    chunks = _split_message(reply)
    for i, chunk in enumerate(chunks):
        text = f"{prefix}{chunk}" if i == 0 and prefix else chunk
        await _send_formatted(context, chat_id, text)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang_from_update(update, context)
    user_id = update.message.from_user.id
    context.user_data["user_id"] = user_id
    await _touch_user(update)

    has_record = await asyncio.to_thread(storage.has_profile_record, user_id)
    if not has_record:
        await _begin_onboarding(context, user_id, is_new_user=True)
        await _send_onboarding_question(
            update.message, lang, "level", intro=t(lang, "ob_intro")
        )
        return

    await update.message.reply_text(
        t(lang, "welcome"),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_main_menu_keyboard(lang),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang_from_update(update, context)
    await update.message.reply_text(
        t(lang, "help"),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_main_menu_keyboard(lang),
    )


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang_from_update(update, context)
    _clear_session(context.user_data)
    clear_intake_state(context.user_data)
    clear_dialog(context.user_data)
    context.user_data.pop("pending_video", None)
    await update.message.reply_text(
        t(lang, "new_reset"),
        reply_markup=_main_menu_keyboard(lang),
    )


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang_from_update(update, context)
    user_id = update.message.from_user.id
    context.user_data["user_id"] = user_id
    text = await asyncio.to_thread(storage.format_history_for_user, user_id, lang)
    if not text:
        await update.message.reply_text(
            t(lang, "history_empty"),
            reply_markup=_main_menu_keyboard(lang),
        )
        return
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_main_menu_keyboard(lang),
    )


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang_from_update(update, context)
    user_id = update.message.from_user.id
    context.user_data["user_id"] = user_id
    clear_reset_pending(context.user_data)
    await _touch_user(update)
    await _show_profile(update.message, lang, user_id)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_ids = context.application.bot_data.get("admin_user_ids", ())
    user_id = update.message.from_user.id
    if not admin_ids:
        await update.message.reply_text(
            "⚠️ ADMIN_USER_IDS не задан в `.env` на сервере."
        )
        return
    if user_id not in admin_ids:
        await update.message.reply_text("⛔ Команда только для администратора.")
        return

    data = await asyncio.to_thread(storage.get_analytics_summary)
    report = format_analytics_report(data)
    await update.message.reply_text(report)


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return

    lang = _lang_from_update(update, context)

    if is_reset_pending(context.user_data):
        await message.reply_text(
            t(lang, "profile_reset_confirm_prompt"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=profile_reset_confirm_keyboard(lang),
        )
        return

    if is_onboarding_active(context.user_data):
        step = get_onboarding_step(context.user_data)
        await message.reply_text(
            t(lang, "ob_in_progress_video"),
            reply_markup=onboarding_keyboard(lang, step),
        )
        return

    user_id = message.from_user.id
    context.user_data["user_id"] = user_id
    await _touch_user(update)

    has_record = await asyncio.to_thread(storage.has_profile_record, user_id)
    if not has_record:
        await _begin_onboarding(context, user_id, is_new_user=True)
        await _send_onboarding_question(
            message, lang, "level", intro=t(lang, "ob_intro")
        )
        return

    video = message.video or message.video_note
    if not video:
        return

    if video.file_size and video.file_size > MAX_VIDEO_SIZE_MB * 1024 * 1024:
        await message.reply_text(t(lang, "video_too_large", max_mb=MAX_VIDEO_SIZE_MB))
        return

    mime_type = getattr(video, "mime_type", None) or "video/mp4"
    if mime_type not in SUPPORTED_MIME_TYPES:
        await message.reply_text(t(lang, "video_unsupported"))
        return

    user_comment = message.caption
    context.user_data["pending_video"] = {
        "file_id": video.file_id,
        "mime_type": mime_type,
        "comment": user_comment,
        "video_context": None,
    }
    clear_intake_state(context.user_data)
    start_intake_state(context.user_data)
    await _log_event(user_id, EVENT_VIDEO_SENT)

    await message.reply_text(
        f"{t(lang, 'vi_got_video')}\n\n{t(lang, 'vi_question_stroke')}",
        reply_markup=intake_keyboard(lang, "stroke"),
    )


async def _begin_analysis_after_intake(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    lang: str,
    language_code: str,
) -> None:
    message = update.message
    user_id = message.from_user.id
    answers = get_intake_answers(context.user_data)
    pending = context.user_data.get("pending_video")
    if pending is not None:
        pending["video_context"] = build_video_context(answers)
    clear_intake_state(context.user_data)

    status_key = (
        "status_analyzing_comment"
        if pending and pending.get("comment")
        else "status_analyzing"
    )
    status_message = await message.reply_text(
        t(lang, status_key),
        reply_markup=_main_menu_keyboard(lang),
    )
    await _run_video_analysis(
        context, message.chat_id, user_id, status_message, lang, language_code
    )


async def _handle_video_intake_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    lang: str,
    language_code: str,
    user_text: str,
) -> None:
    message = update.message
    step = get_intake_step(context.user_data)
    if not step:
        return

    if not context.user_data.get("pending_video"):
        clear_intake_state(context.user_data)
        await message.reply_text(
            t(lang, "video_not_found"),
            reply_markup=_main_menu_keyboard(lang),
        )
        return

    if is_intake_skip_text(lang, user_text):
        await _begin_analysis_after_intake(update, context, lang, language_code)
        return

    value = match_intake_answer(lang, step, user_text)
    if not value:
        await message.reply_text(
            t(lang, "vi_invalid"),
            reply_markup=intake_keyboard(lang, step),
        )
        return

    get_intake_answers(context.user_data)[step] = value
    next_step = advance_intake_step(context.user_data)
    if next_step:
        await message.reply_text(
            t(lang, f"vi_question_{next_step}"),
            reply_markup=intake_keyboard(lang, next_step),
        )
        return

    await _begin_analysis_after_intake(update, context, lang, language_code)


async def _send_pose_overlay(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    lang: str,
    pose_result,
) -> None:
    if pose_result is None:
        return
    if pose_result.ok and pose_result.overlay_path:
        try:
            with pose_result.overlay_path.open("rb") as video_file:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=InputFile(video_file, filename="pose_overlay.mp4"),
                    caption=t(lang, "pose_caption"),
                    supports_streaming=True,
                )
            return
        except Exception:
            logger.exception("Не удалось отправить pose overlay")
    await context.bot.send_message(
        chat_id=chat_id,
        text=t(lang, "pose_unavailable"),
    )


async def _reply_dialog(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    reply_markup=None,
) -> None:
    chunks = _split_message(text)
    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        html = markdown_to_html(chunk)
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=html,
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        except BadRequest:
            await context.bot.send_message(
                chat_id=chat_id,
                text=chunk,
                reply_markup=markup,
            )


async def _send_next_video_and_prompt_feedback(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    lang: str,
    state: dict,
) -> None:
    next_video = (state.get("sections") or {}).get("next_video") or ""
    if next_video:
        await context.bot.send_message(
            chat_id=chat_id,
            text=t(lang, "followup_hint_next", next_video=next_video),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard_after_next(lang),
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=t(lang, "followup_hint"),
            reply_markup=keyboard_after_next(lang),
        )
    state["step"] = "next"


async def _send_feedback_step(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    lang: str,
    user_data: dict,
) -> None:
    clear_dialog(user_data)
    await context.bot.send_message(
        chat_id=chat_id,
        text=t(lang, "feedback_prompt"),
        reply_markup=_feedback_keyboard(lang),
    )


async def _run_lazy_skeleton(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    lang: str,
    state: dict,
) -> None:
    file_id = state.get("video_file_id")
    mime_type = state.get("video_mime") or "video/mp4"
    if not file_id:
        await context.bot.send_message(
            chat_id=chat_id, text=t(lang, "pose_unavailable")
        )
        return

    await context.bot.send_message(
        chat_id=chat_id,
        text=t(lang, "dialog_skeleton_explain"),
        parse_mode=ParseMode.MARKDOWN,
    )
    status = await context.bot.send_message(
        chat_id=chat_id, text=t(lang, "dialog_skeleton_working")
    )

    suffix = ".mp4"
    if mime_type == "video/quicktime":
        suffix = ".mov"
    elif mime_type == "video/webm":
        suffix = ".webm"

    temp_path: Optional[Path] = None
    pose_result = None
    try:
        telegram_file = await context.bot.get_file(file_id)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            temp_path = Path(tmp.name)
            await telegram_file.download_to_drive(custom_path=str(temp_path))
        pose_result = await asyncio.to_thread(create_pose_overlay, temp_path)
        try:
            await status.delete()
        except BadRequest:
            pass
        await _send_pose_overlay(context, chat_id, lang, pose_result)
        state["skeleton_shown"] = True
        await context.bot.send_message(
            chat_id=chat_id,
            text=t(lang, "dialog_continue"),
            reply_markup=keyboard_summary(lang, state),
        )
    except Exception:
        logger.exception("Lazy skeleton failed")
        try:
            await status.edit_text(t(lang, "pose_unavailable"))
        except BadRequest:
            await context.bot.send_message(
                chat_id=chat_id, text=t(lang, "pose_unavailable")
            )
    finally:
        cleanup_overlay(pose_result)
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


async def handle_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    lang = sync_user_lang(context.user_data, query.from_user.language_code)
    language_code = _language_code_from_context(context)
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    context.user_data["user_id"] = user_id
    await _touch_user(update)

    state = get_dialog(context.user_data)
    if not state:
        await context.bot.send_message(chat_id=chat_id, text=t(lang, "dialog_stale"))
        return

    action = query.data.removeprefix("d:")
    sections = state.get("sections") or {}

    if action == "summary":
        state["step"] = "summary"
        await _reply_dialog(
            context,
            chat_id,
            format_summary_message(lang, state),
            keyboard_summary(lang, state),
        )
        return

    if action == "video":
        state["step"] = "video"
        await _reply_dialog(
            context,
            chat_id,
            format_section_title(lang, "dialog_title_video", sections.get("video", "")),
            keyboard_after_video(lang),
        )
        return

    if action == "errors":
        errors = sections.get("errors") or []
        if not errors:
            await context.bot.send_message(
                chat_id=chat_id, text=t(lang, "dialog_no_errors")
            )
            return
        state["step"] = "errors"
        state["error_index"] = 0
        await _reply_dialog(
            context,
            chat_id,
            format_error_card(lang, state),
            keyboard_error(lang, state),
        )
        return

    if action == "err:next":
        errors = sections.get("errors") or []
        idx = int(state.get("error_index") or 0) + 1
        if idx >= len(errors):
            await context.bot.send_message(
                chat_id=chat_id,
                text=t(lang, "dialog_errors_done"),
                reply_markup=keyboard_finish(lang),
            )
            return
        state["error_index"] = idx
        state["step"] = "errors"
        await _reply_dialog(
            context,
            chat_id,
            format_error_card(lang, state),
            keyboard_error(lang, state),
        )
        return

    if action == "err:done":
        await context.bot.send_message(
            chat_id=chat_id,
            text=t(lang, "dialog_errors_done"),
            reply_markup=keyboard_finish(lang),
        )
        return

    if action == "err:deep":
        item = current_error_text(state)
        if not item:
            await context.bot.send_message(
                chat_id=chat_id, text=t(lang, "dialog_no_errors")
            )
            return
        if lang == "ru":
            prompt = (
                "Это одна ошибка из разбора техники (по приоритету). "
                "Дай короткую рекомендацию: что изменить на тренировке и одно "
                f"конкретное упражнение (пока без ссылки на видео):\n{item}"
            )
        else:
            prompt = (
                "This is one technique error from the analysis (by priority). "
                "Give a short tip: what to change in practice and one specific "
                f"drill (no video link yet):\n{item}"
            )
        try:
            await _process_followup(
                context,
                context.user_data,
                chat_id,
                prompt,
                question_label=t(lang, "dialog_btn_err_deep"),
                lang=lang,
                language_code=language_code,
            )
        except Exception:
            logger.exception("dialog err deep failed")
        await context.bot.send_message(
            chat_id=chat_id, text=t(lang, "dialog_drill_soon")
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text=t(lang, "dialog_continue"),
            reply_markup=keyboard_after_error_deep(lang, state),
        )
        return

    if action == "cats":
        cats = sections.get("categories") or []
        if not cats:
            await context.bot.send_message(
                chat_id=chat_id, text=t(lang, "dialog_no_cats")
            )
            return
        state["step"] = "cats"
        await context.bot.send_message(
            chat_id=chat_id,
            text=t(lang, "dialog_title_cats"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard_categories(lang, state),
        )
        return

    if action.startswith("cat:"):
        try:
            idx = int(action.split(":", 1)[1])
        except ValueError:
            return
        cats = sections.get("categories") or []
        if idx < 0 or idx >= len(cats):
            await context.bot.send_message(
                chat_id=chat_id, text=t(lang, "dialog_no_cats")
            )
            return
        cat = cats[idx]
        visited = state.setdefault("visited_categories", [])
        if idx not in visited:
            visited.append(idx)
        state["step"] = "cats"
        body = f"**{cat['title']}**\n\n{cat['body']}"
        await _reply_dialog(context, chat_id, body, keyboard_categories(lang, state))
        return

    if action == "top3":
        state["step"] = "top3"
        await _reply_dialog(
            context,
            chat_id,
            format_section_title(lang, "dialog_title_top3", sections.get("top3", "")),
            keyboard_top3(lang, state),
        )
        return

    if action.startswith("prio:"):
        try:
            n = int(action.split(":", 1)[1])
        except ValueError:
            return
        items = sections.get("top3_items") or []
        if n < 1 or n > len(items):
            await context.bot.send_message(
                chat_id=chat_id, text=t(lang, "dialog_no_prio")
            )
            return
        item = items[n - 1]
        state["step"] = "top3"
        if lang == "ru":
            prompt = (
                "Сделай подробный разбор этого приоритета из анализа "
                f"(что именно не так и как исправить на тренировке):\n{item}"
            )
        else:
            prompt = (
                "Give a detailed breakdown of this training priority from the analysis "
                f"(what's wrong and how to fix it):\n{item}"
            )
        title = t(lang, "dialog_title_prio", n=n)
        await _reply_dialog(context, chat_id, f"{title}\n\n{item}")
        try:
            await _process_followup(
                context,
                context.user_data,
                chat_id,
                prompt,
                question_label=title,
                lang=lang,
                language_code=language_code,
            )
        except Exception:
            logger.exception("dialog prio deepen failed")
        await context.bot.send_message(
            chat_id=chat_id,
            text=t(lang, "dialog_continue"),
            reply_markup=keyboard_after_prio(lang),
        )
        return

    if action == "drills":
        state["step"] = "drills"
        prompts = _QUICK_PROMPTS.get(lang, _QUICK_PROMPTS["en"])
        label = prompts["quick_exercises_label"]
        prompt = prompts["quick_exercises_prompt"]
        try:
            await _process_followup(
                context,
                context.user_data,
                chat_id,
                prompt,
                question_label=label,
                lang=lang,
                language_code=language_code,
            )
        except Exception:
            logger.exception("dialog drills failed")
            await context.bot.send_message(
                chat_id=chat_id, text=t(lang, "quick_question_failed")
            )
            return
        await context.bot.send_message(
            chat_id=chat_id,
            text=t(lang, "dialog_continue"),
            reply_markup=keyboard_after_drills(lang),
        )
        return

    if action == "finish":
        state["step"] = "finish"
        await context.bot.send_message(
            chat_id=chat_id,
            text=t(lang, "dialog_title_finish"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard_finish(lang),
        )
        return

    if action in ("next", "done"):
        await _send_next_video_and_prompt_feedback(context, chat_id, lang, state)
        return

    if action == "ask":
        await context.bot.send_message(chat_id=chat_id, text=t(lang, "dialog_ask_hint"))
        return

    if action == "fb":
        await _send_feedback_step(context, chat_id, lang, context.user_data)
        return

    if action == "skeleton":
        await _run_lazy_skeleton(context, chat_id, lang, state)
        return


async def _run_video_analysis(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int,
    status_message,
    lang: str,
    language_code: str,
) -> None:
    pending = context.user_data.get("pending_video")
    if not pending:
        await status_message.edit_text(t(lang, "video_not_found"))
        return

    mime_type = pending["mime_type"]
    user_comment = pending.get("comment")
    video_context = pending.get("video_context")
    video_file_id = pending["file_id"]

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    analyzer: VideoAnalyzer = context.application.bot_data["analyzer"]

    suffix = ".mp4"
    if mime_type == "video/quicktime":
        suffix = ".mov"
    elif mime_type == "video/webm":
        suffix = ".webm"

    temp_path: Optional[Path] = None
    try:
        telegram_file = await context.bot.get_file(video_file_id)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            temp_path = Path(tmp.name)
            await telegram_file.download_to_drive(custom_path=str(temp_path))

        player_history = await asyncio.to_thread(storage.get_player_history, user_id)
        player_profile = await asyncio.to_thread(storage.get_player_profile, user_id)

        report = await asyncio.to_thread(
            analyzer.analyze,
            temp_path,
            user_comment,
            player_history,
            language_code,
            player_profile,
            video_context,
        )

        _save_analysis(context.user_data, report)
        await asyncio.to_thread(storage.save_session, user_id, report, language_code)
        context.user_data.pop("pending_video", None)

        state = start_dialog(
            context.user_data,
            report,
            language_code,
            video_file_id=video_file_id,
            video_mime=mime_type,
        )

        await status_message.delete()
        await _reply_dialog(
            context,
            chat_id,
            format_summary_message(lang, state),
            keyboard_summary(lang, state),
        )
        await _log_event(user_id, EVENT_ANALYSIS_SUCCESS)

    except TimeoutError:
        await _log_event(user_id, EVENT_ANALYSIS_FAILED, "TimeoutError")
        await status_message.edit_text(
            format_analysis_error(TimeoutError(), lang),
            reply_markup=_retry_keyboard(lang),
        )
    except Exception as exc:
        logger.exception("Ошибка анализа видео для user_id=%s", user_id)
        await _log_event(user_id, EVENT_ANALYSIS_FAILED, str(exc)[:200])
        await status_message.edit_text(
            format_analysis_error(exc, lang),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_retry_keyboard(lang),
        )
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    lang = sync_user_lang(context.user_data, query.from_user.language_code)
    key = query.data.removeprefix("fb:")
    event_type = _FEEDBACK_EVENTS.get(key)
    if not event_type:
        return

    user_id = query.from_user.id
    context.user_data["user_id"] = user_id
    await _touch_user(update)
    await _log_event(user_id, event_type)

    try:
        await query.edit_message_text(t(lang, "feedback_thanks"))
    except BadRequest:
        await query.message.reply_text(t(lang, "feedback_thanks"))


async def handle_retry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    lang = sync_user_lang(context.user_data, query.from_user.language_code)
    language_code = _language_code_from_context(context)

    user_id = query.from_user.id
    context.user_data["user_id"] = user_id
    await _touch_user(update)

    if not context.user_data.get("pending_video"):
        await query.message.reply_text(
            t(lang, "video_not_found_retry"),
            reply_markup=_main_menu_keyboard(lang),
        )
        return

    status_message = await query.message.reply_text(t(lang, "retry_status"))
    await _run_video_analysis(
        context,
        query.message.chat_id,
        user_id,
        status_message,
        lang,
        language_code,
    )


async def handle_quick_question(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    lang = sync_user_lang(context.user_data, query.from_user.language_code)
    language_code = _language_code_from_context(context)
    prompts = _QUICK_PROMPTS.get(lang, _QUICK_PROMPTS["en"])

    key = query.data.removeprefix("q:")
    question = QUICK_QUESTIONS.get(key)
    if not question:
        return

    label_key, prompt_key = question
    label = prompts[label_key]
    prompt = prompts[prompt_key]
    context.user_data["user_id"] = query.from_user.id
    await _touch_user(update)

    session = _get_session(context.user_data)
    if not session.get("analysis"):
        await query.message.reply_text(
            t(lang, "context_lost"),
            reply_markup=_main_menu_keyboard(lang),
        )
        return

    logger.info("Быстрый вопрос '%s' от user_id=%s", key, query.from_user.id)
    try:
        await _process_followup(
            context,
            context.user_data,
            query.message.chat_id,
            prompt,
            question_label=label,
            lang=lang,
            language_code=language_code,
        )
    except Exception:
        logger.exception("Ошибка быстрого вопроса для user_id=%s", query.from_user.id)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=t(lang, "quick_question_failed"),
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return

    lang = _lang_from_update(update, context)
    language_code = _language_code_from_context(context)

    user_text = message.text.strip()
    if not user_text:
        return

    await _touch_user(update)

    menu_handler = _MENU_HANDLERS.get(user_text)
    if menu_handler:
        await menu_handler(update, context)
        return

    if is_reset_pending(context.user_data):
        user_id = message.from_user.id
        context.user_data["user_id"] = user_id
        if is_reset_confirm_yes(user_text):
            await _execute_profile_reset(update, context, lang, user_id)
            return
        if is_reset_confirm_no(user_text):
            clear_reset_pending(context.user_data)
            await _show_profile(message, lang, user_id)
            return
        await message.reply_text(
            t(lang, "profile_reset_confirm_prompt"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=profile_reset_confirm_keyboard(lang),
        )
        return

    if is_reset_profile_text(user_text):
        set_reset_pending(context.user_data)
        await message.reply_text(
            t(lang, "profile_reset_confirm_prompt"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=profile_reset_confirm_keyboard(lang),
        )
        return

    if is_edit_profile_text(user_text):
        clear_reset_pending(context.user_data)
        start_onboarding_state(context.user_data)
        await _send_onboarding_question(
            message,
            lang,
            "level",
            intro=t(lang, "profile_edit_prompt"),
        )
        return

    if is_onboarding_active(context.user_data):
        await _handle_onboarding_text(update, context, lang, user_text)
        return

    if is_intake_active(context.user_data):
        await _handle_video_intake_text(update, context, lang, language_code, user_text)
        return

    session = _get_session(context.user_data)
    analysis = session.get("analysis")
    if not analysis:
        await message.reply_text(t(lang, "no_active_analysis"))
        return

    try:
        await _process_followup(
            context,
            context.user_data,
            message.chat_id,
            user_text,
            lang=lang,
            language_code=language_code,
        )
    except Exception as exc:
        logger.exception("Ошибка диалога для user_id=%s", message.from_user.id)
        await message.reply_text(
            format_analysis_error(exc, lang),
            parse_mode=ParseMode.MARKDOWN,
        )


async def handle_unsupported(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not update.message:
        return
    lang = _lang_from_update(update, context)
    await update.message.reply_text(t(lang, "unsupported"))


_MENU_HANDLERS.update(_menu_handlers())


async def _setup_bot_menu(application: Application) -> None:
    for lang in UI_LANGS:
        await application.bot.set_my_commands(
            _bot_commands(lang),
            language_code=lang,
        )
        await application.bot.set_my_description(
            description=t(lang, "bot_description"),
            language_code=lang,
        )
        await application.bot.set_my_short_description(
            short_description=t(lang, "bot_short_description"),
            language_code=lang,
        )
    await application.bot.set_my_commands(_bot_commands("en"))
    await application.bot.set_my_description(
        description=t("en", "bot_description"),
    )
    await application.bot.set_my_short_description(
        short_description=t("en", "bot_short_description"),
    )


def build_application(settings: Settings) -> Application:
    analyzer = VideoAnalyzer(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
    )

    app = (
        Application.builder()
        .token(settings.telegram_token)
        .post_init(_setup_bot_menu)
        .build()
    )
    app.bot_data["analyzer"] = analyzer
    app.bot_data["admin_user_ids"] = settings.admin_user_ids
    if not settings.admin_user_ids:
        logger.warning("ADMIN_USER_IDS не задан — команда /stats недоступна")

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CommandHandler("reset", new_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CallbackQueryHandler(handle_feedback, pattern=r"^fb:"))
    app.add_handler(CallbackQueryHandler(handle_dialog, pattern=r"^d:"))
    app.add_handler(CallbackQueryHandler(handle_quick_question, pattern=r"^q:"))
    app.add_handler(CallbackQueryHandler(handle_retry, pattern=r"^retry$"))
    app.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, handle_video))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_unsupported))

    return app
