import asyncio
import json
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
    LabeledPrice,
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
    PreCheckoutQueryHandler,
    filters,
)

import billing
import drills
import practice
import review
import storage
from analysis_dialog import (
    DIALOG_KEY,
    clear_dialog,
    current_error_text,
    format_error_card,
    format_section_title,
    format_summary_message,
    get_dialog,
    keyboard_after_drills,
    keyboard_after_error_deep,
    keyboard_after_prio,
    keyboard_after_video,
    keyboard_categories,
    keyboard_error,
    keyboard_finish,
    keyboard_summary,
    keyboard_top3,
)
from analysis_dialog import (
    parse_report as parse_dialog_sections,
)
from analytics import (
    EVENT_ANALYSIS_FAILED,
    EVENT_ANALYSIS_SUCCESS,
    EVENT_FEEDBACK_CLEAR,
    EVENT_FEEDBACK_NEGATIVE,
    EVENT_FEEDBACK_POSITIVE,
    EVENT_INVOICE_SENT,
    EVENT_ONBOARDING_COMPLETED,
    EVENT_ONBOARDING_SKIPPED,
    EVENT_ONBOARDING_STARTED,
    EVENT_PAYMENT_SUCCESS,
    EVENT_PAYWALL_SHOWN,
    EVENT_PRACTICE_DATE_SET,
    EVENT_PRACTICE_POST_ANSWERED,
    EVENT_PRACTICE_PRE_SENT,
    EVENT_PROFILE_RESET,
    EVENT_REVIEW_QUEUED,
    EVENT_REVIEW_SENT_COACH,
    EVENT_REVIEW_SENT_FALLBACK,
    EVENT_VIDEO_SENT,
    format_analytics_report,
)
from analyzer import VideoAnalyzer
from config import Settings
from error_reporting import alert_admins, report_failure
from errors import format_analysis_error, is_model_overloaded
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
from pricing import cost_for_usage
from report_parser import format_scores_line, parse_report, sparkline
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


def _get_user_id(user_data: dict) -> Optional[int]:
    return user_data.get("user_id")


def _persist_session(user_data: dict) -> None:
    user_id = _get_user_id(user_data)
    session = user_data.get(SESSION_KEY)
    if user_id and session:
        storage.save_active_session(user_id, session)


def _get_session(user_data: dict) -> dict:
    if SESSION_KEY in user_data and user_data[SESSION_KEY]:
        return user_data[SESSION_KEY]
    user_id = _get_user_id(user_data)
    if user_id:
        loaded = storage.load_active_session(user_id)
        if loaded:
            user_data[SESSION_KEY] = loaded
            return loaded
    return user_data.setdefault(SESSION_KEY, {"analysis": None, "history": []})


def _clear_session(user_data: dict) -> None:
    user_data.pop(SESSION_KEY, None)
    user_id = _get_user_id(user_data)
    if user_id:
        storage.clear_active_session(user_id)


def _save_analysis(user_data: dict, report: str, stroke: Optional[str] = None) -> None:
    user_data[SESSION_KEY] = {
        "analysis": report,
        "history": [],
        "stroke": stroke,
    }
    _persist_session(user_data)


def _paywall_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(t(lang, "btn_upgrade_pro"), callback_data="pay:pro")]]
    )


def _bot_commands(lang: str) -> list[BotCommand]:
    return [
        BotCommand("start", t(lang, "cmd_start")),
        BotCommand("help", t(lang, "cmd_help")),
        BotCommand("plan", t(lang, "cmd_plan")),
        BotCommand("progress", t(lang, "cmd_progress")),
        BotCommand("focus", t(lang, "cmd_focus")),
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


def _retry_keyboard(lang: str, *, offer_simple: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(t(lang, "retry_button"), callback_data="retry")],
    ]
    if offer_simple:
        rows.append(
            [
                InlineKeyboardButton(
                    t(lang, "retry_simple_button"), callback_data="retry:simple"
                )
            ]
        )
    return InlineKeyboardMarkup(rows)


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

    settings: Settings = context.application.bot_data.get("settings")
    use_model = (
        settings.model_for(billing.is_pro(user_id))
        if settings and user_id
        else analyzer._model
    )
    result = await asyncio.to_thread(
        analyzer.chat,
        analysis,
        history,
        user_text,
        player_history,
        model_lang,
        player_profile,
        session.get("stroke"),
        use_model,
    )
    reply = result.text
    logger.info("Ответ ИИ получен (%s символов)", len(reply))
    if user_id:
        await asyncio.to_thread(
            storage.log_usage,
            user_id,
            "chat",
            result.model,
            result.usage.input_tokens,
            result.usage.output_tokens,
            result.usage.thinking_tokens,
            None,
            cost_for_usage(result.usage, result.model),
        )
    history.append({"user": user_text, "assistant": reply})
    session["history"] = history[-MAX_HISTORY_TURNS:]
    _persist_session(user_data)

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


def _admin_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
    """None если ок; иначе текст ошибки для ответа админу/юзеру."""
    admin_ids = context.application.bot_data.get("admin_user_ids", ())
    user_id = update.message.from_user.id
    if not admin_ids:
        return "⚠️ ADMIN_USER_IDS не задан в `.env` на сервере."
    if user_id not in admin_ids:
        return "⛔ Команда только для администратора."
    return None


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    denied = _admin_gate(update, context)
    if denied:
        await update.message.reply_text(denied)
        return

    data = await asyncio.to_thread(storage.get_analytics_summary)
    report = format_analytics_report(data)
    await update.message.reply_text(report)


async def grant_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Админ: /grant <user_id> [months] — выдать Pro."""
    denied = _admin_gate(update, context)
    if denied:
        await update.message.reply_text(denied)
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Использование: /grant <user_id> [months]\nПример: /grant 123456789 1"
        )
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("user_id должен быть числом.")
        return
    months = billing.PRO_MONTHS_DEFAULT
    if len(args) > 1:
        try:
            months = max(1, int(args[1]))
        except ValueError:
            await update.message.reply_text("months должен быть числом.")
            return

    sub = await asyncio.to_thread(
        billing.grant_pro,
        target_id,
        months,
        billing.PROVIDER_ADMIN,
        None,
    )
    expires = sub.get("expires_at") or "—"
    await update.message.reply_text(
        f"✅ Pro выдан user_id={target_id} на {months} мес.\nДо: {expires}"
    )
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=t("ru", "payment_success"),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        logger.exception("Не удалось уведомить user_id=%s о grant Pro", target_id)


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

    plan = await asyncio.to_thread(billing.get_plan, user_id)
    if plan.analyses_left <= 0:
        await _log_event(user_id, EVENT_PAYWALL_SHOWN)
        await message.reply_text(
            t(
                lang,
                "paywall_text",
                used=plan.analyses_used,
                limit=plan.analyses_limit,
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_paywall_keyboard(lang),
        )
        return

    video = message.video or message.video_note
    if not video:
        return

    if video.file_size and video.file_size > MAX_VIDEO_SIZE_MB * 1024 * 1024:
        await message.reply_text(t(lang, "video_too_large", max_mb=MAX_VIDEO_SIZE_MB))
        return

    duration = getattr(video, "duration", None) or 0
    if duration and duration > plan.max_video_seconds:
        await message.reply_text(
            t(
                lang,
                "video_too_long",
                max_sec=plan.max_video_seconds,
                plan=plan.plan,
            )
        )
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
        "duration": duration,
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
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=t(lang, "followup_hint"),
        )
    state["step"] = "next"


async def _ask_next_practice(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    lang: str,
    user_id: int,
) -> None:
    plan = await asyncio.to_thread(storage.get_active_practice_plan, user_id)
    if not plan:
        return
    if plan.get("status") == "scheduled" and plan.get("next_practice_on"):
        return
    if plan.get("status") == "snoozed":
        return
    focus = (plan.get("focus_text") or "").strip() or "—"
    drill = (plan.get("drill_text") or "").strip() or "—"
    await context.bot.send_message(
        chat_id=chat_id,
        text=t(lang, "practice_ask", focus=focus, drill=drill),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=practice.keyboard_ask_practice(lang),
    )


async def _send_practice_pre_now(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    lang: str,
    plan: dict,
) -> None:
    focus = (plan.get("focus_text") or "").strip() or "—"
    drill = (plan.get("drill_text") or "").strip() or "—"
    await context.bot.send_message(
        chat_id=chat_id,
        text=t(lang, "practice_pre", focus=focus, drill=drill),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=practice.keyboard_pre_nudge(lang),
    )
    await asyncio.to_thread(storage.mark_practice_pre_sent, int(plan["id"]))
    await _log_event(chat_id, EVENT_PRACTICE_PRE_SENT)


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


def _restore_dialog_from_session(user_data: dict, user_id: int) -> Optional[dict]:
    state = get_dialog(user_data)
    if state:
        return state
    loaded = storage.load_active_session(user_id)
    if not loaded:
        return None
    dialog = loaded.get("analysis_dialog")
    if not isinstance(dialog, dict):
        return None
    user_data[DIALOG_KEY] = dialog
    user_data[SESSION_KEY] = {
        "analysis": loaded.get("analysis"),
        "history": loaded.get("history") or [],
        "stroke": loaded.get("stroke"),
        "analysis_dialog": dialog,
    }
    return dialog


def _persist_dialog_state(user_data: dict) -> None:
    user_id = _get_user_id(user_data)
    state = get_dialog(user_data)
    if not user_id or not state:
        return
    session = _get_session(user_data)
    session["analysis_dialog"] = state
    user_data[SESSION_KEY] = session
    _persist_session(user_data)


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

    state = _restore_dialog_from_session(context.user_data, user_id)
    if not state:
        await context.bot.send_message(chat_id=chat_id, text=t(lang, "dialog_stale"))
        return

    action = query.data.removeprefix("d:")
    sections = state.get("sections") or {}
    try:
        await _handle_dialog_action(
            update, context, lang, language_code, chat_id, state, action, sections
        )
    finally:
        _persist_dialog_state(context.user_data)


async def _handle_dialog_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    lang: str,
    language_code: str,
    chat_id: int,
    state: dict,
    action: str,
    sections: dict,
) -> None:
    query = update.callback_query

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
        )
        await _ask_next_practice(context, chat_id, lang, query.from_user.id)
        return

    if action in ("next", "done"):
        await _send_next_video_and_prompt_feedback(context, chat_id, lang, state)
        await _ask_next_practice(context, chat_id, lang, query.from_user.id)
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


async def _ensure_player_forum_topic(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    forum_chat_id: int,
) -> Optional[int]:
    existing = await asyncio.to_thread(
        storage.get_player_forum_topic, user_id, forum_chat_id
    )
    if existing:
        return int(existing["message_thread_id"])

    try:
        chat = await context.bot.get_chat(user_id)
        first_name = getattr(chat, "first_name", "") or ""
        username = getattr(chat, "username", "") or ""
    except Exception:
        first_name, username = "", ""
        logger.exception("get_chat failed for topic title user_id=%s", user_id)

    title = review.topic_title(user_id, first_name, username)
    try:
        topic = await context.bot.create_forum_topic(chat_id=forum_chat_id, name=title)
    except Exception:
        logger.exception(
            "create_forum_topic failed chat_id=%s user_id=%s", forum_chat_id, user_id
        )
        return None

    thread_id = int(topic.message_thread_id)
    await asyncio.to_thread(
        storage.save_player_forum_topic,
        user_id,
        forum_chat_id,
        thread_id,
        title,
    )
    return thread_id


async def _post_review_job_to_forum(
    context: ContextTypes.DEFAULT_TYPE,
    job_id: int,
    user_id: int,
) -> bool:
    settings: Settings = context.application.bot_data.get("settings")
    if not settings or not settings.coach_forum_chat_id:
        logger.error("COACH_FORUM_CHAT_ID не задан — кабинет недоступен")
        return False

    job = await asyncio.to_thread(storage.get_review_job, job_id)
    if not job:
        return False

    forum_chat_id = settings.coach_forum_chat_id
    thread_id = await _ensure_player_forum_topic(context, user_id, forum_chat_id)
    if thread_id is None:
        return False

    await asyncio.to_thread(
        storage.update_review_job,
        job_id,
        forum_chat_id=forum_chat_id,
        message_thread_id=thread_id,
        status=review.STATUS_QUEUED,
    )

    header = (
        f"🆕 Заявка #{job_id}\n"
        f"user_id: `{user_id}`\n"
        f"Фокус: {job.get('focus_text') or '—'}\n"
        f"Упражнение: {job.get('drill_text') or '—'}\n"
        f"Статус: в очереди"
    )
    try:
        await context.bot.send_message(
            chat_id=forum_chat_id,
            message_thread_id=thread_id,
            text=header,
            parse_mode=ParseMode.MARKDOWN,
        )
        try:
            await context.bot.send_video(
                chat_id=forum_chat_id,
                message_thread_id=thread_id,
                video=job["video_file_id"],
            )
        except BadRequest:
            await context.bot.send_message(
                chat_id=forum_chat_id,
                message_thread_id=thread_id,
                text="⚠️ Не удалось переслать видео (file_id). Попросите игрока прислать ещё раз.",
            )
        draft = (job.get("draft_text") or "")[:3500]
        await context.bot.send_message(
            chat_id=forum_chat_id,
            message_thread_id=thread_id,
            text=f"🤖 *AI-черновик:*\n\n{draft}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=review.keyboard_coach_job(job_id),
        )
    except Exception:
        logger.exception("post review to forum failed job_id=%s", job_id)
        return False
    return True


async def _deliver_review_to_player(
    context: ContextTypes.DEFAULT_TYPE,
    job: dict,
    *,
    final_text: str,
    status: str,
    coach_notes: str = "",
) -> None:
    user_id = int(job["user_id"])
    lang = "ru" if (job.get("language_code") or "").startswith("ru") else "en"
    language_code = job.get("language_code") or lang
    video_file_id = job["video_file_id"]
    mime_type = job.get("video_mime") or "video/mp4"
    focus_text = job.get("focus_text") or ""
    drill_text = job.get("drill_text") or ""
    drill_id = job.get("drill_id")
    stroke = job.get("stroke") or ""
    try:
        scores = json.loads(job.get("scores_json") or "{}")
    except json.JSONDecodeError:
        scores = {}

    await asyncio.to_thread(
        storage.mark_review_sent,
        int(job["id"]),
        status=status,
        final_text=final_text,
        coach_notes=coach_notes,
    )
    await asyncio.to_thread(
        storage.save_session,
        user_id,
        final_text,
        language_code,
        scores,
        focus_text,
        stroke,
    )

    state = {
        "step": "summary",
        "language_code": language_code,
        "sections": parse_dialog_sections(final_text, language_code),
        "skeleton_shown": False,
        "video_file_id": video_file_id,
        "video_mime": mime_type,
        "visited_categories": [],
        "error_index": 0,
    }
    payload = {
        "analysis": final_text,
        "history": [],
        "stroke": stroke or None,
        "analysis_dialog": state,
    }
    await asyncio.to_thread(storage.save_active_session, user_id, payload)

    summary = format_summary_message(lang, state)
    if scores:
        summary = f"{summary}\n\n{format_scores_line(scores, lang)}"
    if status == review.STATUS_SENT_COACH:
        await context.bot.send_message(
            chat_id=user_id, text=t(lang, "review_delivered_coach")
        )
    await _reply_dialog(
        context,
        user_id,
        summary,
        keyboard_summary(lang, state),
    )

    if drill_id or drill_text:
        picked = []
        if drill_id:
            picked = await asyncio.to_thread(drills.pick_drills, [drill_id], None, 1)
        for drill in picked:
            await context.bot.send_message(
                chat_id=user_id,
                text=drills.format_drill_message(drill, lang),
                parse_mode=ParseMode.MARKDOWN,
            )
    await asyncio.to_thread(
        storage.create_practice_plan,
        user_id,
        focus_text,
        drill_text,
        drill_id,
    )
    event = (
        EVENT_REVIEW_SENT_FALLBACK
        if status == review.STATUS_SENT_FALLBACK
        else EVENT_REVIEW_SENT_COACH
    )
    await _log_event(user_id, event, str(job["id"]))


async def _run_video_analysis(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int,
    status_message,
    lang: str,
    language_code: str,
    model_override: Optional[str] = None,
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

        # квота ещё раз перед дорогим вызовом (гонка / ретраи)
        plan = await asyncio.to_thread(billing.get_plan, user_id)
        if plan.analyses_left <= 0:
            await _log_event(user_id, EVENT_PAYWALL_SHOWN)
            await status_message.edit_text(
                t(
                    lang,
                    "paywall_text",
                    used=plan.analyses_used,
                    limit=plan.analyses_limit,
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=_paywall_keyboard(lang),
            )
            return

        player_history = await asyncio.to_thread(storage.get_player_history, user_id)
        player_profile = await asyncio.to_thread(storage.get_player_profile, user_id)
        focus_row = await asyncio.to_thread(storage.get_player_focus, user_id)
        active_focus = (focus_row or {}).get("focus")
        drills_catalog = await asyncio.to_thread(drills.catalog_for_prompt)
        settings: Settings = context.application.bot_data.get("settings")
        if model_override:
            use_model = model_override
        elif settings:
            use_model = settings.model_for(plan.is_pro)
        else:
            use_model = analyzer._model
        used_simple = bool(
            settings
            and model_override
            and model_override == settings.gemini_model_free
            and model_override != settings.gemini_model_pro
        )

        result = await asyncio.to_thread(
            analyzer.analyze,
            temp_path,
            user_comment,
            player_history,
            language_code,
            player_profile,
            video_context,
            use_model,
            active_focus,
            drills_catalog,
        )
        parsed = parse_report(result.text)
        report = parsed.text
        stroke = (video_context or {}).get("stroke") if video_context else None
        video_seconds = pending.get("duration")

        await asyncio.to_thread(
            storage.log_usage,
            user_id,
            "analyze",
            result.model,
            result.usage.input_tokens,
            result.usage.output_tokens,
            result.usage.thinking_tokens,
            float(video_seconds) if video_seconds else None,
            cost_for_usage(result.usage, result.model),
        )

        focus_text = parsed.focus or ""
        # Черновик в историю/фокус сразу; игроку отчёт — только после ревью/fallback.
        await asyncio.to_thread(
            storage.save_session,
            user_id,
            report,
            language_code,
            parsed.scores,
            focus_text,
            stroke or "",
        )
        if focus_text:
            await asyncio.to_thread(
                storage.set_player_focus, user_id, focus_text, stroke, 7
            )
        context.user_data.pop("pending_video", None)

        picked = await asyncio.to_thread(drills.pick_drills, parsed.drill_ids, None, 2)
        primary = picked[0] if picked else None
        drill_text = ""
        drill_id = None
        if primary:
            localized = drills.localize_drill(primary, lang)
            drill_text = (localized.get("title") or localized.get("id") or "").strip()
            drill_id = primary.get("id")
        if not drill_text:
            sections = parse_dialog_sections(report, language_code)
            top_items = sections.get("top3_items") or []
            drill_text = (top_items[0] if top_items else focus_text) or ""

        job_id = await asyncio.to_thread(
            storage.create_review_job,
            user_id,
            video_file_id=video_file_id,
            video_mime=mime_type,
            language_code=language_code,
            draft_text=report,
            focus_text=focus_text,
            drill_text=drill_text,
            drill_id=drill_id,
            scores=parsed.scores,
            stroke=stroke or "",
        )
        await _log_event(user_id, EVENT_ANALYSIS_SUCCESS)
        await _log_event(user_id, EVENT_REVIEW_QUEUED, str(job_id))

        posted = await _post_review_job_to_forum(context, job_id, user_id)
        try:
            await status_message.delete()
        except BadRequest:
            pass
        if used_simple:
            await context.bot.send_message(
                chat_id=chat_id,
                text=t(lang, "analysis_used_simple_model"),
            )
        await context.bot.send_message(
            chat_id=chat_id,
            text=t(lang, "review_received"),
            reply_markup=review.keyboard_player_waiting(lang),
        )
        if not posted:
            logger.error(
                "Не удалось запостить review job_id=%s в Forum — "
                "проверьте COACH_FORUM_CHAT_ID и права бота",
                job_id,
            )

    except TimeoutError as exc:
        # квота не списывается — сессия не сохранена
        report_failure(exc, "TimeoutError при анализе")
        await _log_event(user_id, EVENT_ANALYSIS_FAILED, "TimeoutError")
        await status_message.edit_text(
            format_analysis_error(TimeoutError(), lang),
            reply_markup=_retry_keyboard(lang, offer_simple=True),
        )
    except Exception as exc:
        logger.exception("Ошибка анализа видео для user_id=%s", user_id)
        report_failure(exc)
        overloaded = is_model_overloaded(exc)
        if not overloaded:
            admin_ids = context.application.bot_data.get("admin_user_ids") or ()
            if admin_ids:
                await alert_admins(
                    context.bot,
                    admin_ids,
                    f"Ошибка анализа user_id={user_id}: "
                    f"{type(exc).__name__}: {exc}"[:500],
                )
        await _log_event(user_id, EVENT_ANALYSIS_FAILED, str(exc)[:200])
        await status_message.edit_text(
            format_analysis_error(exc, lang),
            parse_mode=ParseMode.MARKDOWN if not overloaded else None,
            reply_markup=_retry_keyboard(lang, offer_simple=overloaded),
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

    use_simple = (query.data or "") == "retry:simple"
    settings: Settings = context.application.bot_data.get("settings")
    model_override = None
    if use_simple and settings:
        model_override = settings.gemini_model_free

    status_text = (
        t(lang, "retry_simple_status") if use_simple else t(lang, "retry_status")
    )
    status_message = await query.message.reply_text(status_text)
    await _run_video_analysis(
        context,
        query.message.chat_id,
        user_id,
        status_message,
        lang,
        language_code,
        model_override=model_override,
    )


async def handle_practice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    lang = sync_user_lang(context.user_data, query.from_user.language_code)
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    context.user_data["user_id"] = user_id
    await _touch_user(update)

    parts = query.data.split(":")
    if len(parts) < 2:
        return
    kind = parts[1]

    plan = await asyncio.to_thread(storage.get_active_practice_plan, user_id)

    if kind == "mute":
        await asyncio.to_thread(storage.snooze_practice_plan, user_id, 7)
        await query.message.reply_text(t(lang, "practice_muted"))
        return

    if kind == "date":
        if not plan or plan.get("status") not in ("awaiting_date", "scheduled"):
            await query.message.reply_text(t(lang, "practice_no_plan"))
            return
        choice = parts[2] if len(parts) > 2 else ""
        try:
            practice_day = practice.resolve_practice_date(choice)
        except ValueError:
            return
        skip_pre = False
        if practice_day is None:
            practice_day = practice.fallback_practice_date()
            skip_pre = True
            await asyncio.to_thread(
                storage.set_practice_date,
                int(plan["id"]),
                practice_day.isoformat(),
                skip_pre=True,
            )
            await _log_event(user_id, EVENT_PRACTICE_DATE_SET, "unknown")
            await query.message.reply_text(
                t(lang, "practice_date_unknown"),
                reply_markup=practice.keyboard_after_date_set(lang),
            )
            return

        await asyncio.to_thread(
            storage.set_practice_date,
            int(plan["id"]),
            practice_day.isoformat(),
            skip_pre=skip_pre,
        )
        await _log_event(user_id, EVENT_PRACTICE_DATE_SET, practice_day.isoformat())
        date_label = practice_day.strftime("%d.%m.%Y")
        await query.message.reply_text(
            t(lang, "practice_date_saved", date=date_label),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=practice.keyboard_after_date_set(lang),
        )
        # «сегодня вечером» после 09:00 МСК — pre сразу
        if practice_day == practice.today_msk() and practice.should_send_pre_now():
            refreshed = await asyncio.to_thread(
                storage.get_practice_plan, int(plan["id"])
            )
            if refreshed and not refreshed.get("pre_sent_at"):
                await _send_practice_pre_now(context, chat_id, lang, refreshed)
        return

    if kind == "pre":
        if not plan:
            await query.message.reply_text(t(lang, "practice_no_plan"))
            return
        action = parts[2] if len(parts) > 2 else ""
        if action == "ok":
            await query.message.reply_text(t(lang, "practice_pre_ok"))
            return
        if action == "move":
            await asyncio.to_thread(
                storage.create_practice_plan,
                user_id,
                plan.get("focus_text") or "",
                plan.get("drill_text") or "",
                plan.get("drill_id"),
            )
            await _ask_next_practice(context, chat_id, lang, user_id)
            return
        return

    if kind == "post":
        if not plan:
            await query.message.reply_text(t(lang, "practice_no_plan"))
            return
        answer = parts[2] if len(parts) > 2 else ""
        await asyncio.to_thread(
            storage.set_practice_post_answer, int(plan["id"]), answer
        )
        await _log_event(user_id, EVENT_PRACTICE_POST_ANSWERED, answer)

        if answer == practice.POST_YES:
            next_video = await asyncio.to_thread(storage.get_latest_next_video, user_id)
            await query.message.reply_text(
                t(
                    lang,
                    "practice_post_yes",
                    next_video=next_video or t(lang, "followup_hint"),
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        if answer == practice.POST_HARD:
            cue = (plan.get("focus_text") or "").strip() or "—"
            alt = await asyncio.to_thread(
                drills.pick_drills,
                None,
                None,
                2,
            )
            current_id = plan.get("drill_id")
            alt_drill = "—"
            for d in alt:
                if d.get("id") != current_id:
                    alt_drill = drills.localize_drill(d, lang).get("title") or "—"
                    break
            if alt_drill == "—" and alt:
                alt_drill = drills.localize_drill(alt[0], lang).get("title") or "—"
            await query.message.reply_text(
                t(lang, "practice_post_hard", cue=cue, alt_drill=alt_drill),
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        if answer == practice.POST_SKIP:
            await asyncio.to_thread(
                storage.create_practice_plan,
                user_id,
                plan.get("focus_text") or "",
                plan.get("drill_text") or "",
                plan.get("drill_id"),
            )
            await query.message.reply_text(t(lang, "practice_post_skip"))
            await _ask_next_practice(context, chat_id, lang, user_id)
            return
        return


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


async def handle_review_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()
    settings: Settings = context.application.bot_data.get("settings")
    user_id = query.from_user.id

    # Игрок: написать тренеру
    if query.data == "rvp:msg":
        lang = sync_user_lang(context.user_data, query.from_user.language_code)
        job = await asyncio.to_thread(storage.get_open_review_job, user_id)
        if not job:
            await query.message.reply_text(t(lang, "review_no_open_job"))
            return
        context.user_data[review.PLAYER_MSG_PENDING_KEY] = int(job["id"])
        await query.message.reply_text(t(lang, "review_message_prompt"))
        return

    if not query.data.startswith("rv:"):
        return
    if not settings or not settings.is_coach(user_id):
        await query.message.reply_text("Недостаточно прав.")
        return

    parts = query.data.split(":")
    if len(parts) < 3:
        return
    try:
        job_id = int(parts[1])
    except ValueError:
        return
    action = parts[2]
    job = await asyncio.to_thread(storage.get_review_job, job_id)
    if not job or job.get("status") not in (
        review.STATUS_QUEUED,
        review.STATUS_IN_REVIEW,
    ):
        await query.message.reply_text("Заявка уже закрыта или не найдена.")
        return

    thread_id = query.message.message_thread_id
    chat_id = query.message.chat_id

    if action == review.ACTION_SEND:
        final_text = review.compose_final_report(
            job.get("draft_text") or "",
            lang="ru" if (job.get("language_code") or "").startswith("ru") else "en",
        )
        await _deliver_review_to_player(
            context,
            job,
            final_text=final_text,
            status=review.STATUS_SENT_COACH,
        )
        await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=f"✅ Отправлено игроку (job #{job_id}) как есть.",
        )
        return

    if action == review.ACTION_REPLACE:
        await asyncio.to_thread(
            storage.update_review_job,
            job_id,
            pending_coach_action=review.ACTION_REPLACE,
            status=review.STATUS_IN_REVIEW,
            reviewer_id=user_id,
        )
        await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=(
                "✏️ Пришлите *полный* финальный текст отчёта следующим сообщением "
                "в эту тему."
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if action == review.ACTION_NOTES:
        await asyncio.to_thread(
            storage.update_review_job,
            job_id,
            pending_coach_action=review.ACTION_NOTES,
            status=review.STATUS_IN_REVIEW,
            reviewer_id=user_id,
        )
        await context.bot.send_message(
            chat_id=chat_id,
            message_thread_id=thread_id,
            text=(
                "➕ Пришлите замечания тренера следующим сообщением в эту тему. "
                "Они будут добавлены к AI-черновику."
            ),
        )
        return


async def _handle_coach_forum_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str
) -> bool:
    """Обработка текста тренера в теме Forum. True если съели сообщение."""
    message = update.message
    settings: Settings = context.application.bot_data.get("settings")
    if not settings or not settings.coach_forum_chat_id:
        return False
    if message.chat_id != settings.coach_forum_chat_id:
        return False
    if not settings.is_coach(message.from_user.id):
        return False
    thread_id = message.message_thread_id
    if not thread_id:
        return False

    job = await asyncio.to_thread(
        storage.get_open_review_by_thread, settings.coach_forum_chat_id, thread_id
    )
    if not job:
        return False
    pending = job.get("pending_coach_action")
    if not pending:
        return False

    lang = "ru" if (job.get("language_code") or "").startswith("ru") else "en"
    if pending == review.ACTION_REPLACE:
        final_text = review.compose_final_report(
            job.get("draft_text") or "",
            replacement=user_text,
            lang=lang,
        )
        await _deliver_review_to_player(
            context,
            job,
            final_text=final_text,
            status=review.STATUS_SENT_COACH,
        )
        await message.reply_text(
            f"✅ Заменённый текст отправлен игроку (#{job['id']})."
        )
        return True

    if pending == review.ACTION_NOTES:
        final_text = review.compose_final_report(
            job.get("draft_text") or "",
            coach_notes=user_text,
            lang=lang,
        )
        await _deliver_review_to_player(
            context,
            job,
            final_text=final_text,
            status=review.STATUS_SENT_COACH,
            coach_notes=user_text,
        )
        await message.reply_text(
            f"✅ Отчёт с замечаниями отправлен игроку (#{job['id']})."
        )
        return True
    return False


async def _handle_player_coach_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str
) -> bool:
    job_id = context.user_data.get(review.PLAYER_MSG_PENDING_KEY)
    if not job_id:
        return False
    message = update.message
    lang = _lang_from_update(update, context)
    job = await asyncio.to_thread(storage.get_review_job, int(job_id))
    context.user_data.pop(review.PLAYER_MSG_PENDING_KEY, None)
    if not job or job.get("status") not in (
        review.STATUS_QUEUED,
        review.STATUS_IN_REVIEW,
    ):
        await message.reply_text(t(lang, "review_no_open_job"))
        return True

    settings: Settings = context.application.bot_data.get("settings")
    forum_chat_id = job.get("forum_chat_id") or (
        settings.coach_forum_chat_id if settings else None
    )
    thread_id = job.get("message_thread_id")
    if not forum_chat_id or not thread_id:
        await message.reply_text(
            "Кабинет ещё не готов принять сообщение. Попробуйте чуть позже."
        )
        return True

    uname = message.from_user.username or message.from_user.first_name or "player"
    await context.bot.send_message(
        chat_id=int(forum_chat_id),
        message_thread_id=int(thread_id),
        text=f"💬 Сообщение от игрока (@{uname} / {message.from_user.id}):\n\n{user_text}",
    )
    await message.reply_text(t(lang, "review_message_sent"))
    return True


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

    if await _handle_coach_forum_text(update, context, user_text):
        return
    if await _handle_player_coach_message(update, context, user_text):
        return

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


async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return
    lang = _lang_from_update(update, context)
    user_id = message.from_user.id
    context.user_data["user_id"] = user_id
    await _touch_user(update)
    plan = await asyncio.to_thread(billing.get_plan, user_id)
    reset = plan.reset_at.strftime("%Y-%m-%d")
    expires = plan.expires_at or "—"
    text = t(
        lang,
        "plan_status",
        plan=("Pro" if plan.is_pro else "Free"),
        used=plan.analyses_used,
        limit=plan.analyses_limit,
        left=plan.analyses_left,
        reset=reset,
        expires=expires,
    )
    markup = None if plan.is_pro else _paywall_keyboard(lang)
    await message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)


async def focus_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return
    lang = _lang_from_update(update, context)
    user_id = message.from_user.id
    context.user_data["user_id"] = user_id
    await _touch_user(update)
    focus = await asyncio.to_thread(storage.get_player_focus, user_id)
    if not focus:
        await message.reply_text(t(lang, "focus_empty"))
        return
    await message.reply_text(
        t(
            lang,
            "focus_status",
            focus=focus["focus"],
            stroke=focus.get("stroke") or "—",
            expires=focus.get("expires_at") or "—",
        ),
        parse_mode=ParseMode.MARKDOWN,
    )


async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return
    lang = _lang_from_update(update, context)
    user_id = message.from_user.id
    context.user_data["user_id"] = user_id
    await _touch_user(update)
    rows = await asyncio.to_thread(storage.get_progress_scores, user_id, 90)
    if not rows:
        await message.reply_text(t(lang, "progress_empty"))
        return
    from report_parser import SKILL_KEYS

    lines = [t(lang, "progress_header")]
    for key in SKILL_KEYS:
        values = [r["scores"][key] for r in rows if key in r["scores"]]
        if not values:
            continue
        label = format_scores_line({key: values[-1]}, lang).split()[0]
        lines.append(
            f"• {label}: {sparkline(values)} "
            f"({values[0]:.0f}→{values[-1]:.0f}, n={len(values)})"
        )
    recent = rows[-1]
    if recent.get("focus"):
        lines.append("")
        lines.append(t(lang, "progress_last_focus", focus=recent["focus"]))
    await message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def send_pro_invoice(
    update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str, user_id: int
) -> None:
    chat = update.effective_chat
    if not chat:
        return
    payload = billing.stars_payload(user_id)
    title = t(lang, "invoice_title")
    description = t(lang, "invoice_description")
    await context.bot.send_invoice(
        chat_id=chat.id,
        title=title,
        description=description,
        payload=payload,
        provider_token="",  # Stars
        currency=billing.STARS_CURRENCY,
        prices=[LabeledPrice(label=title, amount=billing.DEFAULT_STARS_PRICE)],
    )
    await _log_event(user_id, EVENT_INVOICE_SENT)


async def handle_pay_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    lang = sync_user_lang(context.user_data, query.from_user.language_code)
    user_id = query.from_user.id
    context.user_data["user_id"] = user_id
    await _touch_user(update)
    await send_pro_invoice(update, context, lang, user_id)


async def handle_precheckout(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.pre_checkout_query
    if not query:
        return
    user_id = billing.parse_stars_payload(query.invoice_payload or "")
    if user_id is None or user_id != query.from_user.id:
        await query.answer(ok=False, error_message="Invalid payment payload")
        return
    await query.answer(ok=True)


async def handle_successful_payment(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    message = update.message
    if not message or not message.successful_payment:
        return
    lang = _lang_from_update(update, context)
    user_id = message.from_user.id
    context.user_data["user_id"] = user_id
    payment = message.successful_payment
    payment_id = (
        payment.telegram_payment_charge_id or payment.provider_payment_charge_id
    )
    await asyncio.to_thread(
        billing.grant_pro,
        user_id,
        1,
        billing.PROVIDER_STARS,
        payment_id,
    )
    await _log_event(user_id, EVENT_PAYMENT_SUCCESS, payment_id or "")
    await message.reply_text(t(lang, "payment_success"), parse_mode=ParseMode.MARKDOWN)


def build_application(settings: Settings) -> Application:
    analyzer = VideoAnalyzer(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model_pro,
    )
    try:
        drills.sync_drills_from_wiki()
    except Exception:
        logger.exception("Не удалось синхронизировать drills из wiki")

    app = (
        Application.builder()
        .token(settings.telegram_token)
        .post_init(_setup_bot_menu)
        .build()
    )
    app.bot_data["analyzer"] = analyzer
    app.bot_data["settings"] = settings
    app.bot_data["admin_user_ids"] = settings.admin_user_ids
    if not settings.admin_user_ids:
        logger.warning("ADMIN_USER_IDS не задан — команды /stats и /grant недоступны")
    if not settings.coach_forum_chat_id:
        logger.warning(
            "COACH_FORUM_CHAT_ID не задан — заявки в кабинет тренера не попадут"
        )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("plan", plan_command))
    app.add_handler(CommandHandler("focus", focus_command))
    app.add_handler(CommandHandler("progress", progress_command))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CommandHandler("reset", new_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("grant", grant_command))
    app.add_handler(CallbackQueryHandler(handle_feedback, pattern=r"^fb:"))
    app.add_handler(CallbackQueryHandler(handle_practice, pattern=r"^p:"))
    app.add_handler(CallbackQueryHandler(handle_review_callback, pattern=r"^rv"))
    app.add_handler(CallbackQueryHandler(handle_dialog, pattern=r"^d:"))
    app.add_handler(CallbackQueryHandler(handle_quick_question, pattern=r"^q:"))
    app.add_handler(CallbackQueryHandler(handle_retry, pattern=r"^retry(:simple)?$"))
    app.add_handler(CallbackQueryHandler(handle_pay_callback, pattern=r"^pay:"))
    app.add_handler(PreCheckoutQueryHandler(handle_precheckout))
    app.add_handler(
        MessageHandler(filters.SUCCESSFUL_PAYMENT, handle_successful_payment)
    )
    app.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE, handle_video))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_unsupported))

    return app
