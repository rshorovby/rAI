import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Callable, Optional

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
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
        BotCommand("about", t(lang, "cmd_about")),
        BotCommand("new", t(lang, "cmd_new")),
        BotCommand("history", t(lang, "cmd_history")),
    ]


def _main_menu_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(t(lang, "btn_help")), KeyboardButton(t(lang, "btn_about"))],
            [
                KeyboardButton(t(lang, "btn_new")),
                KeyboardButton(t(lang, "btn_history")),
            ],
        ],
        resize_keyboard=True,
    )


def _retry_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(t(lang, "retry_button"), callback_data="retry")]]
    )


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
        handlers[t(lang, "btn_about")] = about_command
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

    reply = await asyncio.to_thread(
        analyzer.chat,
        analysis,
        history,
        user_text,
        player_history,
        model_lang,
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


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang_from_update(update, context)
    await update.message.reply_text(
        t(lang, "about"),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_main_menu_keyboard(lang),
    )


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang_from_update(update, context)
    _clear_session(context.user_data)
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


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return

    lang = _lang_from_update(update, context)
    language_code = _language_code_from_context(context)

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

    user_id = message.from_user.id
    context.user_data["user_id"] = user_id

    user_comment = message.caption
    context.user_data["pending_video"] = {
        "file_id": video.file_id,
        "mime_type": mime_type,
        "comment": user_comment,
    }

    status_key = "status_analyzing_comment" if user_comment else "status_analyzing"
    status_message = await message.reply_text(t(lang, status_key))

    await _run_video_analysis(
        context, message.chat_id, user_id, status_message, lang, language_code
    )


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

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    analyzer: VideoAnalyzer = context.application.bot_data["analyzer"]

    suffix = ".mp4"
    if mime_type == "video/quicktime":
        suffix = ".mov"
    elif mime_type == "video/webm":
        suffix = ".webm"

    temp_path: Optional[Path] = None
    try:
        telegram_file = await context.bot.get_file(pending["file_id"])
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            temp_path = Path(tmp.name)
            await telegram_file.download_to_drive(custom_path=str(temp_path))

        player_history = await asyncio.to_thread(storage.get_player_history, user_id)
        report = await asyncio.to_thread(
            analyzer.analyze,
            temp_path,
            user_comment,
            player_history,
            language_code,
        )

        _save_analysis(context.user_data, report)
        await asyncio.to_thread(storage.save_session, user_id, report, language_code)
        context.user_data.pop("pending_video", None)

        await status_message.delete()
        for chunk in _split_message(report):
            await _send_formatted(context, chat_id, chunk)
        await context.bot.send_message(
            chat_id=chat_id,
            text=t(lang, "followup_hint"),
        )

    except TimeoutError:
        await status_message.edit_text(
            format_analysis_error(TimeoutError(), lang),
            reply_markup=_retry_keyboard(lang),
        )
    except Exception as exc:
        logger.exception("Ошибка анализа видео для user_id=%s", user_id)
        await status_message.edit_text(
            format_analysis_error(exc, lang),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_retry_keyboard(lang),
        )
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


async def handle_retry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    lang = sync_user_lang(context.user_data, query.from_user.language_code)
    language_code = _language_code_from_context(context)

    user_id = query.from_user.id
    context.user_data["user_id"] = user_id

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

    menu_handler = _MENU_HANDLERS.get(user_text)
    if menu_handler:
        await menu_handler(update, context)
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

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CommandHandler("reset", new_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CallbackQueryHandler(handle_quick_question, pattern=r"^q:"))
    app.add_handler(CallbackQueryHandler(handle_retry, pattern=r"^retry$"))
    app.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, handle_video))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_unsupported))

    return app
