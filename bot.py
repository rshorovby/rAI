import asyncio
import logging
import tempfile
from pathlib import Path
from typing import List, Optional

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from analyzer import VideoAnalyzer
from config import Settings
from errors import format_analysis_error

logger = logging.getLogger(__name__)

MAX_VIDEO_SIZE_MB = 20
SUPPORTED_MIME_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/mpeg",
    "video/x-msvideo",
}

WELCOME_TEXT = (
    "🎾 *RallyAI — разбор техники тенниса*\n\n"
    "Отправьте видео (10–30 сек), где игрок в центре кадра. "
    "Желательно съёмка сбоку или сзади — так проще оценить технику и работу ног.\n\n"
    "*Как пользоваться:*\n"
    "1. Запишите короткий ролик с одного или нескольких ракурсов\n"
    "2. Отправьте его как видео (не как файл, если возможно)\n"
    "3. Подождите 30–90 секунд — бот пришлёт разбор\n\n"
    "Команды:\n"
    "/help — справка\n"
    "/about — о сервисе"
)

HELP_TEXT = (
    "📋 *Справка*\n\n"
    "• Принимаются видео до 20 МБ\n"
    "• Оптимальная длительность: 10–30 секунд\n"
    "• Лучшие ракурсы: сбоку, сзади-сбоку, иногда сверху\n"
    "• На видео должен быть виден игрок и его удары/движение\n\n"
    "Бот анализирует технику, работу ног и даёт рекомендации "
    "с градацией по критичности."
)

ABOUT_TEXT = (
    "ℹ️ *О RallyAI*\n\n"
    "Бот использует Google Gemini для анализа видео. "
    "ИИ оценивает технику ударов, передвижение и баланс, "
    "выделяет ошибки по критичности и предлагает упражнения.\n\n"
    "⚠️ Это не замена живого тренера, а вспомогательный инструмент "
    "для самоанализа и подготовки к тренировке."
)


def _split_message(text: str, limit: int = 4000) -> List[str]:
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


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_TEXT, parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN)


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(ABOUT_TEXT, parse_mode=ParseMode.MARKDOWN)


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

    status_message = await message.reply_text(
        "⏳ Видео получено. Анализирую технику — это может занять до минуты..."
    )
    await context.bot.send_chat_action(
        chat_id=message.chat_id, action=ChatAction.TYPING
    )

    analyzer: VideoAnalyzer = context.application.bot_data["analyzer"]

    suffix = ".mp4"
    if mime_type == "video/quicktime":
        suffix = ".mov"
    elif mime_type == "video/webm":
        suffix = ".webm"

    temp_path: Optional[Path] = None
    try:
        telegram_file = await context.bot.get_file(video.file_id)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            temp_path = Path(tmp.name)
            await telegram_file.download_to_drive(custom_path=str(temp_path))

        report = await asyncio.to_thread(analyzer.analyze, temp_path)

        await status_message.delete()
        for chunk in _split_message(report):
            await message.reply_text(chunk)

    except TimeoutError:
        await status_message.edit_text(format_analysis_error(TimeoutError()))
    except Exception as exc:
        logger.exception("Ошибка анализа видео для user_id=%s", message.from_user.id)
        await status_message.edit_text(
            format_analysis_error(exc),
            parse_mode=ParseMode.MARKDOWN,
        )
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


async def handle_unsupported(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "Отправьте видео с теннисистом (10–30 сек). "
        "Документы и фото пока не поддерживаются."
    )


def build_application(settings: Settings) -> Application:
    analyzer = VideoAnalyzer(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
    )

    app = (
        Application.builder()
        .token(settings.telegram_token)
        .build()
    )
    app.bot_data["analyzer"] = analyzer

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(
        MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, handle_video)
    )
    app.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, handle_unsupported)
    )

    return app
