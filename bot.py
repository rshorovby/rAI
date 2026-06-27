import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Optional

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

WELCOME_TEXT = (
    "🎾 *RallyAI — разбор техники тенниса*\n\n"
    "Отправьте видео (10–30 сек), где игрок в центре кадра. "
    "Желательно съёмка сбоку или сзади — так проще оценить технику и работу ног.\n\n"
    "*Как пользоваться:*\n"
    "1. Запишите короткий ролик с одного или нескольких ракурсов\n"
    "2. Отправьте его как видео — можно добавить подпись с вопросом или контекстом\n"
    "3. Подождите 30–90 секунд — бот пришлёт разбор\n"
    "4. Задавайте уточняющие вопросы в чате — бот помнит последний разбор\n\n"
    "Используйте кнопки меню внизу или команды:\n"
    "/help — справка\n"
    "/about — о сервисе\n"
    "/new — новый разбор\n"
    "/history — мои прошлые разборы"
)

HELP_TEXT = (
    "📋 *Справка*\n\n"
    "• Принимаются видео до 20 МБ\n"
    "• Оптимальная длительность: 10–30 секунд\n"
    "• Лучшие ракурсы: сбоку, сзади-сбоку, иногда сверху\n"
    "• На видео должен быть виден игрок и его удары/движение\n"
    "• К видео можно добавить подпись: «это форхенд сверху», «болит локоть» и т.п.\n\n"
    "После разбора пишите вопросы обычным сообщением — бот ответит в контексте "
    "последнего видео. Новое видео автоматически начинает новый диалог.\n\n"
    "/new — сбросить текущий диалог без отправки видео"
)

ABOUT_TEXT = (
    "ℹ️ *О RallyAI*\n\n"
    "Бот использует Google Gemini для анализа видео. "
    "ИИ оценивает технику ударов, передвижение и баланс, "
    "выделяет ошибки по критичности и предлагает упражнения.\n\n"
    "⚠️ Это не замена живого тренера, а вспомогательный инструмент "
    "для самоанализа и подготовки к тренировке."
)

BTN_HELP = "📋 Справка"
BTN_ABOUT = "ℹ️ О сервисе"
BTN_NEW = "🔄 Новый разбор"
BTN_HISTORY = "📊 Мои разборы"

BOT_COMMANDS = [
    BotCommand("start", "Начать работу"),
    BotCommand("help", "Справка по использованию"),
    BotCommand("about", "О сервисе"),
    BotCommand("new", "Новый разбор"),
    BotCommand("history", "Мои прошлые разборы"),
]

# callback_data → (подпись кнопки, промпт для модели)
QUICK_QUESTIONS = {
    "main": (
        "🔴 Разбор главной ошибки",
        "Сделай подробный разбор самой критичной ошибки из анализа: что именно "
        "происходит в технике, почему это снижает эффективность и травмоопасно, "
        "и пошагово — как это исправить на тренировке.",
    ),
    "exercises": (
        "🏋️ 3 упражнения",
        "Назови 3 упражнения, на которых игроку стоит сосредоточиться для улучшения "
        "техники, исходя из разбора. Для каждого: на какую проблему направлено, "
        "как выполнять и сколько повторений/подходов.",
    ),
}


def _get_session(user_data: dict) -> dict:
    return user_data.setdefault(SESSION_KEY, {"analysis": None, "history": []})


def _clear_session(user_data: dict) -> None:
    user_data.pop(SESSION_KEY, None)


def _save_analysis(user_data: dict, report: str) -> None:
    user_data[SESSION_KEY] = {"analysis": report, "history": []}


def _get_user_id(user_data: dict) -> Optional[int]:
    return user_data.get("user_id")


def _main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(BTN_HELP), KeyboardButton(BTN_ABOUT)],
            [KeyboardButton(BTN_NEW), KeyboardButton(BTN_HISTORY)],
        ],
        resize_keyboard=True,
    )


def _retry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔄 Повторить разбор", callback_data="retry")]]
    )


def _quick_questions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(label, callback_data=f"q:{key}")]
            for key, (label, _prompt) in QUICK_QUESTIONS.items()
        ]
    )


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
) -> None:
    session = _get_session(user_data)
    analysis = session.get("analysis")
    if not analysis:
        raise RuntimeError("Нет активного разбора. Отправьте видео.")

    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    analyzer: VideoAnalyzer = context.application.bot_data["analyzer"]
    history: list[dict[str, str]] = session.get("history", [])

    user_id = _get_user_id(user_data)
    player_history = (
        await asyncio.to_thread(storage.get_player_history, user_id) if user_id else []
    )

    reply = await asyncio.to_thread(
        analyzer.chat, analysis, history, user_text, player_history
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
    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_main_menu_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        HELP_TEXT,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_main_menu_keyboard(),
    )


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        ABOUT_TEXT,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_main_menu_keyboard(),
    )


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _clear_session(context.user_data)
    await update.message.reply_text(
        "Диалог сброшен. Отправьте новое видео для разбора.",
        reply_markup=_main_menu_keyboard(),
    )


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    context.user_data["user_id"] = user_id
    text = await asyncio.to_thread(storage.format_history_for_user, user_id)
    if not text:
        await update.message.reply_text(
            "У вас пока нет сохранённых разборов. Отправьте видео — и я его запомню.",
            reply_markup=_main_menu_keyboard(),
        )
        return
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_main_menu_keyboard(),
    )


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return

    video = message.video or message.video_note
    if not video:
        return

    if video.file_size and video.file_size > MAX_VIDEO_SIZE_MB * 1024 * 1024:
        await message.reply_text(
            f"Видео слишком большое. Максимум — {MAX_VIDEO_SIZE_MB} МБ."
        )
        return

    mime_type = getattr(video, "mime_type", None) or "video/mp4"
    if mime_type not in SUPPORTED_MIME_TYPES:
        await message.reply_text(
            "Формат видео не поддерживается. Отправьте MP4, MOV или WebM."
        )
        return

    user_id = message.from_user.id
    context.user_data["user_id"] = user_id

    user_comment = message.caption
    # Сохраняем данные видео, чтобы можно было повторить разбор без пересылки
    context.user_data["pending_video"] = {
        "file_id": video.file_id,
        "mime_type": mime_type,
        "comment": user_comment,
    }

    status_text = (
        "⏳ Видео получено. Анализирую технику — это может занять до минуты..."
    )
    if user_comment:
        status_text = "⏳ Видео и комментарий получены. Анализирую — это может занять до минуты..."
    status_message = await message.reply_text(status_text)

    await _run_video_analysis(context, message.chat_id, user_id, status_message)


async def _run_video_analysis(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int,
    status_message,
) -> None:
    """Скачивает сохранённое видео, прогоняет анализ и отправляет отчёт.

    При ошибке редактирует status_message и вешает кнопку «Повторить»."""
    pending = context.user_data.get("pending_video")
    if not pending:
        await status_message.edit_text("Видео не найдено. Отправьте его заново.")
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
            analyzer.analyze, temp_path, user_comment, player_history
        )

        _save_analysis(context.user_data, report)
        await asyncio.to_thread(storage.save_session, user_id, report)
        context.user_data.pop("pending_video", None)

        await status_message.delete()
        for chunk in _split_message(report):
            await _send_formatted(context, chat_id, chunk)
        await context.bot.send_message(
            chat_id=chat_id,
            text="💬 Можете задавать уточняющие вопросы текстом.",
        )

    except TimeoutError:
        await status_message.edit_text(format_analysis_error(TimeoutError()))
    except Exception as exc:
        logger.exception("Ошибка анализа видео для user_id=%s", user_id)
        await status_message.edit_text(
            format_analysis_error(exc),
            parse_mode=ParseMode.MARKDOWN,
        )
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


async def handle_retry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user_id = query.from_user.id
    context.user_data["user_id"] = user_id

    if not context.user_data.get("pending_video"):
        await query.message.reply_text(
            "Видео не найдено — отправьте его заново.",
            reply_markup=_main_menu_keyboard(),
        )
        return

    status_message = await query.message.reply_text(
        "⏳ Повторяю разбор — это может занять до минуты..."
    )
    await _run_video_analysis(context, query.message.chat_id, user_id, status_message)


async def handle_quick_question(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    key = query.data.removeprefix("q:")
    question = QUICK_QUESTIONS.get(key)
    if not question:
        return

    label, prompt = question
    context.user_data["user_id"] = query.from_user.id

    session = _get_session(context.user_data)
    if not session.get("analysis"):
        await query.message.reply_text(
            "Контекст разбора потерян (возможно, бот перезапускался). "
            "Отправьте видео заново — и кнопки снова заработают.",
            reply_markup=_main_menu_keyboard(),
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
        )
    except Exception:
        logger.exception("Ошибка быстрого вопроса для user_id=%s", query.from_user.id)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=(
                "⚠️ Не удалось получить ответ от ИИ. Попробуйте ещё раз "
                "или задайте вопрос текстом."
            ),
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return

    user_text = message.text.strip()
    if not user_text:
        return

    menu_actions = {
        BTN_HELP: help_command,
        BTN_ABOUT: about_command,
        BTN_NEW: new_command,
        BTN_HISTORY: history_command,
    }
    menu_handler = menu_actions.get(user_text)
    if menu_handler:
        await menu_handler(update, context)
        return

    session = _get_session(context.user_data)
    analysis = session.get("analysis")
    if not analysis:
        await message.reply_text(
            "Сначала отправьте видео для разбора — после этого можно задавать "
            "вопросы и просить разъяснения. К видео можно добавить подпись с контекстом."
        )
        return

    try:
        await _process_followup(
            context,
            context.user_data,
            message.chat_id,
            user_text,
        )
    except Exception as exc:
        logger.exception("Ошибка диалога для user_id=%s", message.from_user.id)
        await message.reply_text(
            format_analysis_error(exc),
            parse_mode=ParseMode.MARKDOWN,
        )


async def handle_unsupported(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "Отправьте видео с теннисистом (10–30 сек) или задайте текстовый вопрос "
        "после разбора. Документы и фото пока не поддерживаются."
    )


async def _setup_bot_menu(application: Application) -> None:
    await application.bot.set_my_commands(BOT_COMMANDS)


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
