import asyncio
import json
import logging
import tempfile
from pathlib import Path
from typing import Callable, Optional

from telegram import (
    BotCommand,
    BotCommandScopeChat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    LabeledPrice,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ChatAction, ChatType, ParseMode
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

import acquisition
import billing
import broadcast
import cabinet
import drills
import identity
import practice
import review
import services
import storage
import survey
import trainer
from analysis_dialog import (
    DIALOG_KEY,
    clear_dialog,
    current_error_text,
    current_remark_kind,
    format_error_card,
    format_focus_message,
    format_section_title,
    format_summary_message,
    get_dialog,
    keyboard_after_drills,
    keyboard_after_error_deep,
    keyboard_after_focus,
    keyboard_after_prio,
    keyboard_after_video,
    keyboard_categories,
    keyboard_closing,
    keyboard_error,
    keyboard_finish,
    keyboard_observation,
    keyboard_remark,
    keyboard_summary,
    keyboard_top3,
    observation_total,
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
    EVENT_SURVEY_COMPLETED,
    EVENT_SURVEY_SENT,
    EVENT_VIDEO_SENT,
    format_analytics_report,
    format_daly_report,
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
    language_choice,
    match_step_answer,
    onboarding_keyboard,
    profile_actions_keyboard,
    profile_reset_confirm_keyboard,
    set_reset_pending,
    start_onboarding_state,
    step_progress,
)
from pricing import cost_for_usage
from prompts import follow_up_player_text
from report_parser import format_scores_line, sparkline
from video_intake import (
    STROKE_KEYS,
    advance_intake_step,
    build_video_context,
    clear_intake_state,
    get_intake_answers,
    get_intake_step,
    intake_keyboard,
    intake_value_label,
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
_CLEANUP_KEY = "analysis_cleanup_ids"
NEW_CONFIRM_PENDING_KEY = "new_analysis_confirm"
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


async def _touch_user(
    update: Update, context: Optional[ContextTypes.DEFAULT_TYPE] = None
) -> Optional[int]:
    user = _telegram_user_from_update(update)
    if not user:
        return None
    player_id = await asyncio.to_thread(
        storage.upsert_user,
        user.id,
        user.username,
        user.first_name,
        user.last_name,
        user.language_code,
    )
    if context is not None:
        context.user_data["telegram_id"] = user.id
        context.user_data["player_id"] = player_id
        context.user_data["user_id"] = player_id
    return player_id


def _player_chat_id(player_id: int) -> Optional[int]:
    return identity.telegram_id_for(player_id)


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
    await _cabinet_notify(
        context,
        user_id,
        cabinet.format_profile_reset(user_id),
        user=update.effective_user,
    )
    await _begin_onboarding(context, user_id, is_new_user=True)
    await _send_onboarding_question(message, lang, "level", intro=t(lang, "ob_intro"))


async def _show_profile(
    message,
    lang: str,
    user_id: int,
) -> None:
    text = await asyncio.to_thread(storage.format_profile_for_user, user_id, lang)
    preferred = await asyncio.to_thread(storage.get_preferred_language, user_id)
    await message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=profile_actions_keyboard(lang, preferred or None),
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


def _manual_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    user = update.effective_user
    if not user:
        return ""
    player_id = context.user_data.get("player_id")
    if not player_id:
        player_id = storage.player_id_for_telegram(user.id)
    if not player_id:
        return ""
    return storage.get_preferred_language(player_id)


def _lang_from_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    device = update.effective_user.language_code if update.effective_user else None
    return sync_user_lang(
        context.user_data, _manual_language(update, context) or device
    )


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
    user_data: Optional[dict] = None,
) -> None:
    parts = []
    if intro:
        parts.append(intro)
    n, total = step_progress(step)
    parts.append(t(lang, "ob_progress", n=n, total=total))
    parts.append(t(lang, f"ob_question_{step}"))
    markup = onboarding_keyboard(lang, step)
    if user_data is not None and trainer.wizard(user_data):
        markup = trainer.with_cancel(markup, lang)
    await message.reply_text(
        "\n\n".join(parts),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup,
    )


async def _cabinet_notify(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    text: str,
    *,
    user=None,
) -> None:
    settings: Settings = context.application.bot_data.get("settings")
    if not settings or not settings.coach_forum_chat_id:
        return
    first_name = getattr(user, "first_name", "") or ""
    username = getattr(user, "username", "") or ""
    await cabinet.notify(
        context.bot,
        settings.coach_forum_chat_id,
        user_id,
        text,
        first_name=first_name,
        username=username,
    )


async def _load_coach_corrections(user_id: Optional[int]) -> list:
    player_id = int(user_id) if user_id else None
    return await asyncio.to_thread(storage.get_coach_corrections_for_prompt, player_id)


async def _bind_trainer_onboarding_player(
    context: ContextTypes.DEFAULT_TYPE, fallback_user_id: int
) -> Optional[int]:
    """Создаёт карточку в момент завершения анкеты. None — имя уже занято."""
    wiz = trainer.wizard(context.user_data)
    if not wiz or wiz.get("kind") not in ("create", "edit"):
        return fallback_user_id
    if wiz.get("kind") == "edit":
        return int(wiz["player_id"])
    if wiz.get("player_id"):
        return int(wiz["player_id"])
    card = await asyncio.to_thread(
        storage.create_trainer_card, int(wiz["trainer_id"]), wiz["name"]
    )
    if not card:
        return None
    wiz["player_id"] = int(card["player_id"])
    context.user_data[trainer.WIZARD_KEY] = wiz
    return int(card["player_id"])


async def _trainer_keyboard(telegram_id: int, lang: str) -> ReplyKeyboardMarkup:
    card = await asyncio.to_thread(storage.get_active_trainer_card, telegram_id)
    return trainer.menu_keyboard(lang, has_active=card is not None)


async def _trainer_show_home(message, lang: str, telegram_id: int) -> None:
    card = await asyncio.to_thread(storage.get_active_trainer_card, telegram_id)
    if card:
        text = t(lang, "tr_home_active", name=card["name"])
    else:
        text = t(lang, "tr_home_empty")
    await message.reply_text(
        text,
        reply_markup=trainer.menu_keyboard(lang, has_active=card is not None),
    )


async def _finish_onboarding_skip(
    update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str, user_id: int
) -> None:
    bound = await _bind_trainer_onboarding_player(context, user_id)
    if bound is None:
        trainer.clear_wizard(context.user_data)
        clear_onboarding_state(context.user_data)
        await update.message.reply_text(t(lang, "tr_name_taken"))
        if update.effective_user:
            await _trainer_show_home(update.message, lang, update.effective_user.id)
        return
    user_id = bound
    await asyncio.to_thread(storage.mark_profile_skipped, user_id)
    await _log_event(user_id, EVENT_ONBOARDING_SKIPPED)
    wiz = trainer.wizard(context.user_data)
    clear_onboarding_state(context.user_data)
    trainer.clear_wizard(context.user_data)
    actor = update.effective_user
    if actor and await asyncio.to_thread(storage.is_trainer, actor.id):
        card = await asyncio.to_thread(storage.get_trainer_card_by_player, user_id)
        name = (card or {}).get("name") or (wiz or {}).get("name") or ""
        key = (
            "tr_profile_updated"
            if wiz and wiz.get("kind") == "edit"
            else "tr_card_ready"
        )
        await update.message.reply_text(
            t(lang, key, name=name),
            reply_markup=await _trainer_keyboard(actor.id, lang),
        )
    else:
        await update.message.reply_text(
            t(lang, "ob_skip_warning"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_main_menu_keyboard(lang),
        )
    profile_text = await asyncio.to_thread(
        storage.format_profile_for_user, user_id, "ru"
    )
    await _cabinet_notify(
        context,
        user_id,
        cabinet.format_onboarding_done(
            user_id,
            profile_text,
            skipped=True,
            first_name=getattr(update.effective_user, "first_name", "") or "",
            username=getattr(update.effective_user, "username", "") or "",
        ),
        user=update.effective_user,
    )


async def _finish_onboarding_complete(
    update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str, user_id: int
) -> None:
    bound = await _bind_trainer_onboarding_player(context, user_id)
    if bound is None:
        trainer.clear_wizard(context.user_data)
        clear_onboarding_state(context.user_data)
        await update.message.reply_text(t(lang, "tr_name_taken"))
        if update.effective_user:
            await _trainer_show_home(update.message, lang, update.effective_user.id)
        return
    user_id = bound
    profile = build_profile_dict(get_onboarding_answers(context.user_data))
    await asyncio.to_thread(storage.save_player_profile, user_id, profile)
    await _log_event(user_id, EVENT_ONBOARDING_COMPLETED)
    wiz = trainer.wizard(context.user_data)
    clear_onboarding_state(context.user_data)
    trainer.clear_wizard(context.user_data)
    actor = update.effective_user
    if actor and await asyncio.to_thread(storage.is_trainer, actor.id):
        card = await asyncio.to_thread(storage.get_trainer_card_by_player, user_id)
        name = (card or {}).get("name") or (wiz or {}).get("name") or ""
        key = (
            "tr_profile_updated"
            if wiz and wiz.get("kind") == "edit"
            else "tr_card_ready"
        )
        await update.message.reply_text(
            t(lang, key, name=name),
            reply_markup=await _trainer_keyboard(actor.id, lang),
        )
    else:
        await update.message.reply_text(
            t(lang, "ob_complete"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_main_menu_keyboard(lang),
        )
    profile_text = await asyncio.to_thread(
        storage.format_profile_for_user, user_id, "ru"
    )
    await _cabinet_notify(
        context,
        user_id,
        cabinet.format_onboarding_done(
            user_id,
            profile_text,
            skipped=False,
            first_name=getattr(update.effective_user, "first_name", "") or "",
            username=getattr(update.effective_user, "username", "") or "",
        ),
        user=update.effective_user,
    )


async def _handle_onboarding_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    lang: str,
    user_text: str,
) -> None:
    message = update.message
    user_id = message.from_user.id
    if trainer.wizard(context.user_data):
        if trainer.is_cancel_text(lang, user_text):
            trainer.clear_wizard(context.user_data)
            clear_onboarding_state(context.user_data)
            await message.reply_text(t(lang, "tr_cancelled"))
            await _trainer_show_home(message, lang, user_id)
            return
    else:
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
        markup = onboarding_keyboard(lang, step)
        if trainer.wizard(context.user_data):
            markup = trainer.with_cancel(markup, lang)
        await message.reply_text(
            t(lang, "ob_invalid_answer"),
            reply_markup=markup,
        )
        return

    get_onboarding_answers(context.user_data)[step] = value
    next_step = advance_step(context.user_data)
    if next_step:
        await _send_onboarding_question(
            message, lang, next_step, user_data=context.user_data
        )


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


def _remember_free_question(
    user_id, user_text: str, question_label: Optional[str]
) -> None:
    if not user_id or question_label:
        return
    storage.add_player_note(user_id, user_text)


async def _followup_scope_on(
    context: ContextTypes.DEFAULT_TYPE, user_data: dict
) -> bool:
    if await asyncio.to_thread(storage.followup_scope_enabled):
        return True
    admin_ids = context.application.bot_data.get("admin_user_ids") or ()
    telegram_id = user_data.get("telegram_id")
    return telegram_id in admin_ids


def _new_confirm_pending(user_data: dict) -> bool:
    return bool(user_data.get(NEW_CONFIRM_PENDING_KEY))


def _set_new_confirm_pending(user_data: dict) -> None:
    user_data[NEW_CONFIRM_PENDING_KEY] = True


def _clear_new_confirm_pending(user_data: dict) -> None:
    user_data.pop(NEW_CONFIRM_PENDING_KEY, None)


def _new_confirm_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(t(lang, "new_confirm_yes"))],
            [KeyboardButton(t(lang, "new_confirm_no"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _is_new_confirm_choice(text: str, key: str) -> bool:
    return any(text == t(lang, key) for lang in UI_LANGS)


def _reset_chat_state(user_data: dict) -> None:
    _clear_new_confirm_pending(user_data)
    clear_intake_state(user_data)
    clear_dialog(user_data)
    user_data.pop("pending_video", None)
    _clear_session(user_data)


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
    analysis_ctx = (
        await asyncio.to_thread(
            services.load_analysis_context, user_id, session.get("stroke")
        )
        if user_id
        else {}
    )
    player_history = analysis_ctx.get("history") or []
    player_profile = analysis_ctx.get("profile")
    coach_corrections = analysis_ctx.get("corrections") or []

    settings: Settings = context.application.bot_data.get("settings")
    use_model = (
        settings.model_for(billing.is_pro(user_id))
        if settings and user_id
        else analyzer._model
    )
    if user_id:
        await _cabinet_notify(
            context,
            user_id,
            cabinet.format_followup(
                user_id, question=user_text, label=question_label or ""
            ),
        )

    scoped = await _followup_scope_on(context, user_data)
    if scoped and analysis_ctx:
        analysis_ctx = dict(analysis_ctx)
        analysis_ctx["omit_chat_notes"] = True
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
        coach_corrections,
        analysis_ctx or None,
        scoped,
    )
    if scoped:
        reply = follow_up_player_text(result.text, t(ui_lang, "followup_out_of_scope"))
    else:
        await asyncio.to_thread(
            _remember_free_question, user_id, user_text, question_label
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
        await _cabinet_notify(
            context,
            user_id,
            cabinet.format_followup_reply(
                user_id, reply=reply, label=question_label or ""
            ),
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
    player_id = await _touch_user(update, context)
    if player_id is None:
        return
    actor = update.effective_user
    if actor and await asyncio.to_thread(storage.is_trainer, actor.id):
        if await asyncio.to_thread(storage.trainer_instruction_pending, actor.id):
            await update.message.reply_text(t(lang, "tr_instruction"))
            await asyncio.to_thread(storage.mark_trainer_instruction_sent, actor.id)
        await _trainer_show_home(update.message, lang, actor.id)
        return

    has_record = await asyncio.to_thread(storage.has_profile_record, player_id)
    user = update.effective_user or update.message.from_user
    clicked = acquisition.normalize_start_code(
        (context.args or [None])[0] if context.args else None
    )
    if clicked:
        stored = await asyncio.to_thread(
            storage.set_acquisition_source_if_empty, player_id, clicked
        )
        await _log_event(player_id, acquisition.EVENT_ACQUISITION_START, clicked)
    else:
        stored = await asyncio.to_thread(storage.get_acquisition_source, player_id)
    await _cabinet_notify(
        context,
        player_id,
        cabinet.format_start(
            player_id,
            first_name=getattr(user, "first_name", "") or "",
            username=getattr(user, "username", "") or "",
            is_new=not has_record,
            acquisition=acquisition.source_label(stored),
            visit=acquisition.source_label(clicked),
        ),
        user=user,
    )
    if not has_record:
        await _begin_onboarding(context, player_id, is_new_user=True)
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
    actor = update.effective_user
    if actor and await asyncio.to_thread(storage.is_trainer, actor.id):
        await update.message.reply_text(
            t(lang, "tr_instruction"),
            reply_markup=await _trainer_keyboard(actor.id, lang),
        )
        return
    await update.message.reply_text(
        t(lang, "help"),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_main_menu_keyboard(lang),
    )


async def link_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return
    lang = _lang_from_update(update, context)
    if await asyncio.to_thread(storage.is_trainer, message.from_user.id):
        await _trainer_show_home(message, lang, message.from_user.id)
        return
    player_id = await _touch_user(update, context)
    if player_id is None:
        return
    args = context.args or []
    if not args:
        code = await asyncio.to_thread(
            storage.create_link_code, player_id, storage.LINK_TG_TO_IOS
        )
        await message.reply_text(t(lang, "link_code", code=code))
        return
    ios_player = await asyncio.to_thread(
        storage.consume_link_code, args[0], storage.LINK_IOS_TO_TG
    )
    if ios_player is None:
        await message.reply_text(t(lang, "link_invalid"))
        return
    if await asyncio.to_thread(storage.has_player_history, player_id):
        await message.reply_text(t(lang, "link_telegram_not_empty"))
        return
    telegram_id = message.from_user.id
    await asyncio.to_thread(storage.attach_telegram_identity, ios_player, telegram_id)
    await message.reply_text(t(lang, "link_ok"))


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang_from_update(update, context)
    if update.effective_user and await asyncio.to_thread(
        storage.is_trainer, update.effective_user.id
    ):
        await _trainer_show_home(update.message, lang, update.effective_user.id)
        return
    await _touch_user(update, context)
    session = _get_session(context.user_data)
    if await _followup_scope_on(context, context.user_data):
        if session.get("analysis"):
            _set_new_confirm_pending(context.user_data)
            await update.message.reply_text(
                t(lang, "new_confirm_prompt"),
                reply_markup=_new_confirm_keyboard(lang),
            )
            return
        _reset_chat_state(context.user_data)
        await update.message.reply_text(
            t(lang, "new_send_video"),
            reply_markup=_main_menu_keyboard(lang),
        )
        return
    _reset_chat_state(context.user_data)
    await update.message.reply_text(
        t(lang, "new_reset_legacy"),
        reply_markup=_main_menu_keyboard(lang),
    )


async def _confirm_new_analysis(
    message, context: ContextTypes.DEFAULT_TYPE, lang: str, user_text: str
) -> None:
    if _is_new_confirm_choice(user_text, "new_confirm_yes"):
        _reset_chat_state(context.user_data)
        await message.reply_text(
            t(lang, "new_reset"),
            reply_markup=_main_menu_keyboard(lang),
        )
        return
    if _is_new_confirm_choice(user_text, "new_confirm_no"):
        _clear_new_confirm_pending(context.user_data)
        await message.reply_text(
            t(lang, "new_kept"),
            reply_markup=_main_menu_keyboard(lang),
        )
        return
    await message.reply_text(
        t(lang, "new_confirm_prompt"),
        reply_markup=_new_confirm_keyboard(lang),
    )


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang_from_update(update, context)
    actor = update.effective_user
    if actor and await asyncio.to_thread(storage.is_trainer, actor.id):
        card = await asyncio.to_thread(storage.get_active_trainer_card, actor.id)
        if not card:
            await _trainer_show_home(update.message, lang, actor.id)
            return
        player_id = int(card["player_id"])
    else:
        player_id = await _touch_user(update, context)
        if player_id is None:
            return
    text = await asyncio.to_thread(storage.format_history_for_user, player_id, lang)
    markup = _main_menu_keyboard(lang)
    if actor and await asyncio.to_thread(storage.is_trainer, actor.id):
        markup = await _trainer_keyboard(actor.id, lang)
    if not text:
        await update.message.reply_text(
            t(lang, "history_empty"),
            reply_markup=markup,
        )
        return
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup,
    )


async def _apply_chat_commands(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, lang: str
) -> None:
    try:
        await context.bot.set_my_commands(
            _bot_commands(lang),
            scope=BotCommandScopeChat(chat_id),
        )
    except Exception:
        logger.exception("Не удалось обновить команды чата chat_id=%s", chat_id)


async def _apply_language(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    choice: str,
) -> None:
    message = update.message
    if not message:
        return
    player_id = context.user_data.get("player_id")
    if player_id is None:
        player_id = await _touch_user(update, context)
    if player_id is None:
        return
    await asyncio.to_thread(storage.set_preferred_language, player_id, choice)
    sync_user_lang(context.user_data, choice)
    clear_reset_pending(context.user_data)
    if message.chat:
        await _apply_chat_commands(context, message.chat.id, choice)
    language = t(choice, f"profile_lang_name_{choice}")
    await message.reply_text(t(choice, "profile_lang_saved", language=language))
    if is_onboarding_active(context.user_data):
        step = get_onboarding_step(context.user_data)
        if step:
            await _send_onboarding_question(message, choice, step)
            return
    await _show_profile(message, choice, player_id)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = _lang_from_update(update, context)
    clear_reset_pending(context.user_data)
    actor = update.effective_user
    if actor and await asyncio.to_thread(storage.is_trainer, actor.id):
        card = await asyncio.to_thread(storage.get_active_trainer_card, actor.id)
        if not card or not update.message:
            if update.message:
                await _trainer_show_home(update.message, lang, actor.id)
            return
        text = await asyncio.to_thread(
            storage.format_profile_for_user, int(card["player_id"]), lang
        )
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=await _trainer_keyboard(actor.id, lang),
        )
        return
    player_id = await _touch_user(update, context)
    if player_id is None or not update.message:
        return
    await _show_profile(update.message, lang, player_id)


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


async def daly_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    denied = _admin_gate(update, context)
    if denied:
        await update.message.reply_text(denied)
        return

    data = await asyncio.to_thread(storage.get_daly_summary)
    await update.message.reply_text(format_daly_report(data))


async def followup_scope_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    denied = _admin_gate(update, context)
    if denied:
        await update.message.reply_text(denied)
        return
    args = [part.lower() for part in (context.args or [])]
    if not args:
        enabled = await asyncio.to_thread(storage.followup_scope_enabled)
        state = "включён для всех" if enabled else "выключен"
        await update.message.reply_text(
            f"Follow-up scope: {state}.\n"
            "Пока выключен, у игроков прежний диалог. "
            "Админ видит новый флоу и так.\n"
            "Включить для всех: /followup on\n"
            "Выключить: /followup off"
        )
        return
    if args[0] not in ("on", "off"):
        await update.message.reply_text("Использование: /followup on | off")
        return
    enabled = args[0] == "on"
    await asyncio.to_thread(storage.set_followup_scope, enabled)
    if enabled:
        await update.message.reply_text("Follow-up scope включён для всех.")
        return
    await update.message.reply_text(
        "Follow-up scope выключен. У игроков снова прежний диалог."
    )


def _is_admin_id(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    admin_ids = context.application.bot_data.get("admin_user_ids") or ()
    return user_id in admin_ids


async def _send_broadcast_message(bot, chat_id: int, text: str, entities) -> None:
    kwargs = {"chat_id": chat_id, "text": text}
    if entities:
        kwargs["entities"] = entities
    await bot.send_message(**kwargs)


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Админ: /broadcast — черновик сообщения всем пользователям с Telegram."""
    denied = _admin_gate(update, context)
    if denied:
        await update.message.reply_text(denied)
        return
    if update.message.chat.type != ChatType.PRIVATE:
        await update.message.reply_text("Рассылка запускается в личном чате с ботом.")
        return

    args = [part.lower() for part in (context.args or [])]
    if args[:1] == ["cancel"]:
        broadcast.clear_state(context.user_data)
        await update.message.reply_text("Рассылка отменена.")
        return

    had_draft = broadcast.AWAITING_KEY in context.user_data or (
        broadcast.DRAFT_KEY in context.user_data
    )
    context.user_data[broadcast.AWAITING_KEY] = True
    context.user_data.pop(broadcast.DRAFT_KEY, None)
    prefix = "Предыдущий черновик сброшен.\n" if had_draft else ""
    await update.message.reply_text(
        prefix + "Пришли текст рассылки следующим сообщением.\n"
        "Форматирование Telegram сохранится.\n"
        "Отмена: /broadcast cancel"
    )


async def _consume_broadcast_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    if not context.user_data.get(broadcast.AWAITING_KEY):
        return False
    message = update.message
    if not message or not _is_admin_id(context, message.from_user.id):
        context.user_data.pop(broadcast.AWAITING_KEY, None)
        return False
    text = message.text or ""
    if len(text) > broadcast.TEXT_LIMIT:
        await message.reply_text(
            "Сообщение длиннее 4096 символов. Сократи и пришли ещё раз."
        )
        return True
    entities = tuple(message.entities or ())
    context.user_data[broadcast.DRAFT_KEY] = {"text": text, "entities": entities}
    context.user_data.pop(broadcast.AWAITING_KEY, None)
    chat_ids = await asyncio.to_thread(storage.list_broadcast_chat_ids)
    await message.reply_text(
        broadcast.confirm_text(len(chat_ids), text),
        reply_markup=broadcast.keyboard(),
    )
    return True


async def handle_broadcast_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if not _is_admin_id(context, query.from_user.id):
        return

    action = (query.data or "").split(":", 1)[-1]
    draft = context.user_data.get(broadcast.DRAFT_KEY)
    if action == "cancel":
        if not draft or draft.get("sending"):
            return
        broadcast.clear_state(context.user_data)
        await query.edit_message_text("Рассылка отменена.")
        return
    if not draft or not draft.get("text"):
        return
    if draft.get("sending") or broadcast.busy():
        return

    text = draft["text"]
    entities = draft.get("entities") or None
    if action == "me":
        try:
            await _send_broadcast_message(
                context.bot, query.from_user.id, text, entities
            )
        except Exception:
            logger.exception("Не удалось отправить копию рассылки админу")
            await query.message.reply_text("Не удалось отправить копию.")
            return
        await query.message.reply_text(
            "Копия отправлена тебе. Кнопки выше всё ещё работают."
        )
        return
    if action != "send":
        return

    draft["sending"] = True
    await query.edit_message_text("Отправляю…")
    chat_ids = await asyncio.to_thread(storage.list_broadcast_chat_ids)
    try:
        result = await broadcast.deliver(
            lambda chat_id, body, ents: _send_broadcast_message(
                context.bot, chat_id, body, ents
            ),
            chat_ids,
            text,
            entities,
        )
    except broadcast.BroadcastInProgress:
        draft["sending"] = False
        await query.edit_message_text("Рассылка уже идёт.")
        return
    except Exception:
        draft["sending"] = False
        logger.exception("Рассылка прервалась")
        await query.edit_message_text(
            "Рассылка прервалась. Черновик на месте: повторная отправка "
            "придёт и тем, кому уже ушло."
        )
        return

    context.user_data.pop(broadcast.DRAFT_KEY, None)
    context.user_data.pop(broadcast.AWAITING_KEY, None)
    await asyncio.to_thread(
        storage.record_broadcast,
        query.from_user.id,
        text,
        result["sent"],
        result["blocked"],
        result["failed"],
    )
    await query.edit_message_text(
        broadcast.report_text(result["sent"], result["blocked"], result["failed"])
    )


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
        services.grant_pro,
        identity.get_or_create_telegram_player(target_id),
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


async def set_trainer_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Админ: /set_trainer <telegram_id> [off] — режим тренера с учениками."""
    denied = _admin_gate(update, context)
    if denied:
        await update.message.reply_text(denied)
        return
    if update.message.chat.type != ChatType.PRIVATE:
        await update.message.reply_text("Команда запускается в личном чате с ботом.")
        return
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "Использование: /set_trainer <telegram_id>\n"
            "Снять: /set_trainer <telegram_id> off"
        )
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("telegram_id должен быть числом.")
        return
    turning_off = len(args) > 1 and args[1].lower() == "off"
    if turning_off:
        removed = await asyncio.to_thread(storage.revoke_trainer, target_id)
        if not removed:
            await update.message.reply_text(f"user_id={target_id} не был тренером.")
            return
        delivered = True
        try:
            await context.bot.send_message(
                chat_id=target_id, text=t("ru", "tr_off_notice")
            )
        except Exception:
            delivered = False
            logger.exception("Не удалось уведомить user_id=%s о снятии", target_id)
        note = (
            ""
            if delivered
            else "\nСообщение не доставлено — пользователь не открывал бота."
        )
        await update.message.reply_text(
            f"Режим тренера снят с user_id={target_id}.{note}"
        )
        return

    await asyncio.to_thread(storage.grant_trainer, target_id)
    delivered = True
    try:
        await context.bot.send_message(
            chat_id=target_id, text=t("ru", "tr_instruction")
        )
    except Exception:
        delivered = False
        logger.exception("Не удалось отправить инструкцию user_id=%s", target_id)
    if delivered:
        await asyncio.to_thread(storage.mark_trainer_instruction_sent, target_id)
        await update.message.reply_text(
            f"Режим тренера включён для user_id={target_id}. Инструкция отправлена."
        )
        return
    await update.message.reply_text(
        f"Режим тренера включён для user_id={target_id}.\n"
        "Инструкция не доставлена: пользователь ещё не открывал бота. "
        "Она придёт при /start."
    )


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return

    if await _handle_coach_forum_message(update, context):
        return

    lang = _lang_from_update(update, context)

    if is_reset_pending(context.user_data):
        await message.reply_text(
            t(lang, "profile_reset_confirm_prompt"),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=profile_reset_confirm_keyboard(lang),
        )
        return

    trainer_card = None
    if message.from_user and await asyncio.to_thread(
        storage.is_trainer, message.from_user.id
    ):
        if trainer.blocks_video(context.user_data) or is_onboarding_active(
            context.user_data
        ):
            await message.reply_text(
                t(lang, "tr_video_busy"),
                reply_markup=await _trainer_keyboard(message.from_user.id, lang),
            )
            return
        trainer_card = await asyncio.to_thread(
            storage.get_active_trainer_card, message.from_user.id
        )
        if not trainer_card or not await asyncio.to_thread(
            storage.has_profile_record, int(trainer_card["player_id"])
        ):
            await message.reply_text(
                t(lang, "tr_video_need_card"),
                reply_markup=await _trainer_keyboard(message.from_user.id, lang),
            )
            return
        await _touch_user(update, context)
        player_id = int(trainer_card["player_id"])
        context.user_data["user_id"] = player_id
        context.user_data[trainer.SESSION_PLAYER_KEY] = player_id
    else:
        if is_onboarding_active(context.user_data):
            step = get_onboarding_step(context.user_data)
            await message.reply_text(
                t(lang, "ob_in_progress_video"),
                reply_markup=onboarding_keyboard(lang, step),
            )
            return

        player_id = await _touch_user(update, context)
        if player_id is None:
            return

        has_record = await asyncio.to_thread(storage.has_profile_record, player_id)
        if not has_record:
            await _begin_onboarding(context, player_id, is_new_user=True)
            await _send_onboarding_question(
                message, lang, "level", intro=t(lang, "ob_intro")
            )
            return

    plan = await asyncio.to_thread(services.get_plan, player_id)
    if billing.MONETIZATION_ENABLED and plan.analyses_left <= 0:
        await _log_event(player_id, EVENT_PAYWALL_SHOWN)
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
            t(lang, "video_too_long", max_sec=plan.max_video_seconds)
        )
        return

    mime_type = getattr(video, "mime_type", None) or "video/mp4"
    if mime_type not in SUPPORTED_MIME_TYPES:
        await message.reply_text(t(lang, "video_unsupported"))
        return

    user_comment = message.caption
    _clear_new_confirm_pending(context.user_data)
    context.user_data["pending_video"] = {
        "file_id": video.file_id,
        "mime_type": mime_type,
        "comment": user_comment,
        "video_context": None,
        "duration": duration,
        "subject_player_id": player_id,
        "subject_name": (trainer_card or {}).get("name") or "",
    }
    clear_intake_state(context.user_data)
    start_intake_state(context.user_data)
    context.user_data[_CLEANUP_KEY] = []
    await _log_event(player_id, EVENT_VIDEO_SENT)
    await _cabinet_notify(
        context,
        player_id,
        cabinet.format_video_uploaded(
            player_id, duration=int(duration or 0), comment=user_comment or ""
        ),
        user=message.from_user,
    )

    got = f"{t(lang, 'vi_got_video')}\n{t(lang, 'vi_question_stroke')}"
    subject_name = (trainer_card or {}).get("name") or ""
    if subject_name:
        got = f"{subject_name}\n\n{got}"
    prompt = await message.reply_text(
        got,
        reply_markup=intake_keyboard(lang, "stroke"),
    )
    _remember_cleanup(context.user_data, prompt.message_id)


async def _begin_analysis_after_intake(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    lang: str,
    language_code: str,
) -> None:
    message = update.message
    if not message:
        return
    pending = context.user_data.get("pending_video")
    player_id = (pending or {}).get("subject_player_id") or _get_user_id(
        context.user_data
    )
    if player_id is None:
        player_id = await _touch_user(update, context)
    if player_id is None:
        return
    context.user_data["user_id"] = player_id
    answers = get_intake_answers(context.user_data)
    video_context = build_video_context(answers)
    if pending is not None:
        pending["video_context"] = video_context
        sent = await _post_intake_video_to_cabinet(
            context,
            player_id,
            pending,
            video_context,
            user=message.from_user,
        )
        pending["cabinet_video_sent"] = sent
    clear_intake_state(context.user_data)

    _remember_cleanup(context.user_data, message.message_id)
    ack_markup = _main_menu_keyboard(lang)
    if message.from_user and await asyncio.to_thread(
        storage.is_trainer, message.from_user.id
    ):
        ack_markup = await _trainer_keyboard(message.from_user.id, lang)
    ack_text = t(lang, "review_ack")
    subject_name = (pending or {}).get("subject_name") or ""
    if subject_name:
        ack_text = f"{subject_name}\n\n{ack_text}"
    status_message = await message.reply_text(
        ack_text,
        reply_markup=ack_markup,
    )
    _remember_cleanup(context.user_data, status_message.message_id)
    await _run_video_analysis(
        context, message.chat_id, player_id, status_message, lang, language_code
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
    _remember_cleanup(context.user_data, message.message_id)

    if not context.user_data.get("pending_video"):
        clear_intake_state(context.user_data)
        sent = await message.reply_text(
            t(lang, "video_not_found"),
            reply_markup=_main_menu_keyboard(lang),
        )
        _remember_cleanup(context.user_data, sent.message_id)
        return

    if is_intake_skip_text(lang, user_text):
        await _begin_analysis_after_intake(update, context, lang, language_code)
        return

    value = match_intake_answer(lang, step, user_text)
    if not value:
        sent = await message.reply_text(
            t(lang, "vi_invalid"),
            reply_markup=intake_keyboard(lang, step),
        )
        _remember_cleanup(context.user_data, sent.message_id)
        return

    get_intake_answers(context.user_data)[step] = value
    next_step = advance_intake_step(context.user_data)
    if next_step:
        sent = await message.reply_text(
            t(lang, f"vi_question_{next_step}"),
            reply_markup=intake_keyboard(lang, next_step),
        )
        _remember_cleanup(context.user_data, sent.message_id)
        return

    await _begin_analysis_after_intake(update, context, lang, language_code)


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
    text = t(lang, "practice_ask", focus=focus, drill=drill)
    markup = practice.keyboard_ask_practice(lang)
    card = await asyncio.to_thread(storage.get_trainer_card_by_player, user_id)
    if card:
        text = f"{card['name']}\n\n{text}"
        markup = practice.markup_for_player(markup, user_id)
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup,
    )


async def _send_practice_pre_now(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    lang: str,
    plan: dict,
) -> None:
    focus = (plan.get("focus_text") or "").strip() or "—"
    drill = (plan.get("drill_text") or "").strip() or "—"
    player_id = int(plan["user_id"])
    text = t(lang, "practice_pre", focus=focus, drill=drill)
    markup = practice.keyboard_pre_nudge(lang)
    card = await asyncio.to_thread(storage.get_trainer_card_by_player, player_id)
    if card:
        text = f"{card['name']}\n\n{text}"
        markup = practice.markup_for_player(markup, player_id)
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup,
    )
    await asyncio.to_thread(storage.mark_practice_pre_sent, int(plan["id"]))
    await _log_event(player_id, EVENT_PRACTICE_PRE_SENT)


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


async def _send_survey(
    bot,
    user_id: int,
    lang: str,
    survey_type: str,
    *,
    source: str = "auto",
    settings: Optional[Settings] = None,
) -> bool:
    session_payload = (
        await asyncio.to_thread(storage.load_active_session, user_id) or {}
    )
    survey_state = {
        "type": survey_type,
        "selected": [],
        "source": source,
        "step": survey.STEP_SELECT,
    }
    survey.set_survey_state(session_payload, survey_state)
    await asyncio.to_thread(storage.save_active_session, user_id, session_payload)

    intro_key = survey.intro_key_for(survey_type)
    chat_id = _player_chat_id(user_id)
    if chat_id is None:
        logger.warning("survey: нет telegram identity player_id=%s", user_id)
        return False
    try:
        msg = await bot.send_message(
            chat_id=chat_id,
            text=t(lang, intro_key),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=survey.build_survey_keyboard(lang, survey_type, set()),
        )
    except BadRequest:
        msg = await bot.send_message(
            chat_id=chat_id,
            text=t(lang, intro_key),
            reply_markup=survey.build_survey_keyboard(lang, survey_type, set()),
        )
    except Exception:
        logger.exception(
            "Не удалось отправить опрос user_id=%s type=%s", user_id, survey_type
        )
        survey.set_survey_state(session_payload, None)
        await asyncio.to_thread(storage.save_active_session, user_id, session_payload)
        return False

    survey_state["message_id"] = msg.message_id
    survey_state["chat_id"] = msg.chat_id
    survey.set_survey_state(session_payload, survey_state)
    await asyncio.to_thread(storage.save_active_session, user_id, session_payload)

    if source == "auto":
        if survey_type == survey.SURVEY_TYPE_NO_ONBOARDING:
            await asyncio.to_thread(storage.mark_no_onboarding_survey_sent, user_id)
        else:
            await asyncio.to_thread(storage.mark_no_video_survey_sent, user_id)
    await _log_event(user_id, EVENT_SURVEY_SENT, f"{survey_type}:{source}")

    if settings and settings.coach_forum_chat_id:
        await cabinet.notify(
            bot,
            settings.coach_forum_chat_id,
            user_id,
            cabinet.format_survey_sent(user_id, survey_type=survey_type, source=source),
        )
    return True


async def _send_no_video_survey(
    bot,
    user_id: int,
    lang: str,
    *,
    source: str = "auto",
    settings: Optional[Settings] = None,
) -> bool:
    return await _send_survey(
        bot,
        user_id,
        lang,
        survey.SURVEY_TYPE_NO_VIDEO,
        source=source,
        settings=settings,
    )


async def _complete_survey(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    lang: str,
    survey_state: dict,
    selected: list[str],
    other_text: str = "",
) -> None:
    survey_type = survey_state.get("type") or survey.SURVEY_TYPE_NO_VIDEO
    source = survey_state.get("source") or "auto"
    summary = survey.format_selected_summary(lang, survey_type, selected, other_text)
    await asyncio.to_thread(
        storage.save_survey_response,
        user_id,
        survey_type,
        selected,
        other_text=other_text,
        source=source,
    )
    await _log_event(user_id, EVENT_SURVEY_COMPLETED, f"{survey_type}:{source}")

    session_payload = _get_session(context.user_data)
    survey.set_survey_state(session_payload, None)
    _persist_session(context.user_data)

    settings: Settings = context.application.bot_data.get("settings")
    if settings and settings.coach_forum_chat_id:
        await cabinet.notify(
            context.bot,
            settings.coach_forum_chat_id,
            user_id,
            cabinet.format_survey_response(
                user_id, summary, survey_type=survey_type, source=source
            ),
        )

    thanks_key = survey.thanks_key_for(survey_type)
    chat_id = _player_chat_id(user_id)
    if chat_id is not None:
        await context.bot.send_message(chat_id=chat_id, text=t(lang, thanks_key))


async def handle_survey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    lang = _lang_from_update(update, context)
    user_id = query.from_user.id
    context.user_data["user_id"] = user_id
    await _touch_user(update, context)

    session = _get_session(context.user_data)
    survey_state = survey.get_survey_state(session)
    if not survey_state or not survey_state.get("type"):
        await query.answer()
        return

    survey_type = survey_state["type"]
    action = query.data.removeprefix("sv:")
    selected = set(survey_state.get("selected") or [])
    valid_keys = survey.option_keys_for(survey_type)

    if action.startswith("t:"):
        key = action.removeprefix("t:")
        if key not in valid_keys:
            await query.answer()
            return
        if key in selected:
            selected.discard(key)
        else:
            selected.add(key)
        survey_state["selected"] = sorted(selected)
        survey_state["step"] = survey.STEP_SELECT
        survey.set_survey_state(session, survey_state)
        _persist_session(context.user_data)
        await query.answer()
        try:
            await query.edit_message_reply_markup(
                reply_markup=survey.build_survey_keyboard(lang, survey_type, selected)
            )
        except BadRequest:
            pass
        return

    if action != "done":
        await query.answer()
        return

    if not selected:
        await query.answer(t(lang, "survey_pick_one"), show_alert=True)
        return

    await query.answer()
    if "other" in selected:
        survey_state["step"] = survey.STEP_OTHER_TEXT
        survey_state["selected"] = sorted(selected)
        survey.set_survey_state(session, survey_state)
        _persist_session(context.user_data)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=t(lang, "survey_other_prompt"),
        )
        return

    await _complete_survey(
        context,
        user_id,
        lang,
        survey_state,
        sorted(selected),
    )


async def _handle_survey_other_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str
) -> bool:
    session = _get_session(context.user_data)
    survey_state = survey.get_survey_state(session)
    if not survey_state or survey_state.get("step") != survey.STEP_OTHER_TEXT:
        return False

    lang = _lang_from_update(update, context)
    user_id = update.message.from_user.id
    selected = list(survey_state.get("selected") or [])
    await _complete_survey(
        context,
        user_id,
        lang,
        survey_state,
        selected,
        other_text=user_text.strip(),
    )
    return True


async def handle_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    lang = _lang_from_update(update, context)
    language_code = _language_code_from_context(context)
    chat_id = query.message.chat_id
    await _touch_user(update, context)
    user_id = query.from_user.id
    if await asyncio.to_thread(storage.is_trainer, query.from_user.id):
        bound = context.user_data.get(trainer.SESSION_PLAYER_KEY)
        if bound:
            user_id = int(bound)
    context.user_data["user_id"] = user_id

    state = _restore_dialog_from_session(context.user_data, user_id)
    if not state:
        await context.bot.send_message(chat_id=chat_id, text=t(lang, "dialog_stale"))
        return

    action = query.data.removeprefix("d:")
    sections = state.get("sections") or {}
    try:
        await _handle_dialog_action(
            update,
            context,
            lang,
            language_code,
            chat_id,
            state,
            action,
            sections,
            user_id,
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
    user_id: int,
) -> None:
    query = update.callback_query

    if action == "summary":
        state["step"] = "summary"
        await _reply_dialog(
            context,
            chat_id,
            format_summary_message(lang, state),
            keyboard_summary(lang),
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

    if action == "err:next" or action.startswith("obs:next:"):
        total = observation_total(state)
        from_card = action.startswith("obs:next:")
        if from_card:
            try:
                current = int(action.rsplit(":", 1)[-1])
            except ValueError:
                return
        else:
            current = int(state.get("error_index") or 0)
        next_index = current + 1
        shown = int(state.get("shown_count") or 0)
        if next_index >= total or (from_card and next_index < shown):
            if not from_card and next_index >= total:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=t(lang, "dialog_errors_done"),
                    reply_markup=keyboard_finish(lang),
                )
            return
        state["error_index"] = next_index
        state["step"] = "observations"
        state["shown_count"] = max(shown, next_index + 1)
        if from_card and query and query.message:
            try:
                await query.edit_message_reply_markup(
                    reply_markup=keyboard_remark(lang, current)
                )
            except BadRequest:
                pass
        await _reply_dialog(
            context,
            chat_id,
            format_error_card(lang, state),
            keyboard_observation(lang, state, next_index),
        )
        return

    if action == "focus":
        focus = (state.get("focus_text") or "").strip()
        drill = (state.get("drill_text") or "").strip()
        if not focus:
            session = _get_session(context.user_data)
            row = await asyncio.to_thread(
                storage.get_player_focus,
                user_id,
                session.get("stroke"),
            )
            if row:
                focus = (row.get("focus") or "").strip()
        if not drill:
            plan = await asyncio.to_thread(storage.get_active_practice_plan, user_id)
            if plan:
                drill = (plan.get("drill_text") or "").strip()
        await _reply_dialog(
            context,
            chat_id,
            format_focus_message(lang, focus, drill),
            keyboard_after_focus(lang),
        )
        return

    if action == "err:done":
        await context.bot.send_message(
            chat_id=chat_id,
            text=t(lang, "dialog_errors_done"),
            reply_markup=keyboard_finish(lang),
        )
        return

    if action == "err:deep" or action.startswith("err:deep:"):
        if action.startswith("err:deep:"):
            try:
                state["error_index"] = int(action.rsplit(":", 1)[-1])
            except ValueError:
                state["error_index"] = 0
        item = current_error_text(state)
        if not item:
            await context.bot.send_message(
                chat_id=chat_id, text=t(lang, "dialog_no_errors")
            )
            return
        kind = current_remark_kind(state)
        if lang == "ru" and kind == "strength":
            prompt = (
                "Это сильная сторона из разбора. Коротко: как удержать это "
                "на тренировке и одно конкретное упражнение "
                f"(пока без ссылки на видео):\n{item}"
            )
        elif lang == "ru":
            prompt = (
                "Это одно замечание из разбора. Дай короткую рекомендацию: "
                "что изменить на тренировке и одно конкретное упражнение "
                f"(пока без ссылки на видео):\n{item}"
            )
        elif kind == "strength":
            prompt = (
                "This is a strength from the analysis. Briefly: how to keep it "
                f"in practice and one specific drill (no video link yet):\n{item}"
            )
        else:
            prompt = (
                "This is one note from the analysis. Give a short tip: what to "
                "change in practice and one specific drill "
                f"(no video link yet):\n{item}"
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
        await _ask_next_practice(context, chat_id, lang, user_id)
        return

    if action in ("next", "done"):
        await _send_next_video_and_prompt_feedback(context, chat_id, lang, state)
        await _ask_next_practice(context, chat_id, lang, user_id)
        return

    if action == "ask":
        await context.bot.send_message(chat_id=chat_id, text=t(lang, "dialog_ask_hint"))
        return

    if action == "fb":
        await _send_feedback_step(context, chat_id, lang, context.user_data)
        return


async def _ensure_player_forum_topic(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    forum_chat_id: int,
) -> Optional[int]:
    return await cabinet.ensure_player_topic(context.bot, forum_chat_id, user_id)


async def _send_forum_video(
    bot, forum_chat_id: int, thread_id: int, file_id: str
) -> bool:
    if file_id.startswith("ios:"):
        path = file_id[4:]
        try:
            with open(path, "rb") as handle:
                await bot.send_video(
                    chat_id=forum_chat_id,
                    message_thread_id=thread_id,
                    video=handle,
                )
            return True
        except OSError:
            logger.exception("ios video file missing path=%s", path)
        except BadRequest:
            logger.exception("send_video ios file to forum failed")
        return False
    try:
        await bot.send_video(
            chat_id=forum_chat_id,
            message_thread_id=thread_id,
            video=file_id,
        )
        return True
    except BadRequest:
        logger.exception("send_video to forum failed, trying video_note")
    try:
        await bot.send_video_note(
            chat_id=forum_chat_id,
            message_thread_id=thread_id,
            video_note=file_id,
        )
        return True
    except BadRequest:
        logger.exception("send_video_note to forum failed")
        await bot.send_message(
            chat_id=forum_chat_id,
            message_thread_id=thread_id,
            text=(
                "⚠️ Не удалось переслать видео (file_id). "
                "Попросите игрока прислать ещё раз."
            ),
        )
        return False


async def _post_intake_video_to_cabinet(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    pending: dict,
    video_context: Optional[dict],
    *,
    user=None,
) -> bool:
    """Сразу после intake: видео в тему, не дожидаясь AI."""
    settings: Settings = context.application.bot_data.get("settings")
    if not settings or not settings.coach_forum_chat_id:
        return False
    file_id = (pending or {}).get("file_id")
    if not file_id:
        return False
    forum_chat_id = int(settings.coach_forum_chat_id)
    try:
        thread_id = await cabinet.ensure_player_topic(
            context.bot,
            forum_chat_id,
            user_id,
            first_name=getattr(user, "first_name", "") or "",
            username=getattr(user, "username", "") or "",
        )
    except Exception:
        logger.exception("ensure topic for intake video failed user_id=%s", user_id)
        return False
    if thread_id is None:
        return False
    ctx = video_context or {}
    header = cabinet.format_video_intake_ready(
        user_id,
        stroke=intake_value_label("ru", "stroke", ctx.get("stroke")),
        look=intake_value_label("ru", "look", ctx.get("look")),
        duration=int(pending.get("duration") or 0),
        comment=pending.get("comment") or "",
    )
    try:
        await context.bot.send_message(
            chat_id=forum_chat_id,
            message_thread_id=thread_id,
            text=header,
        )
        return await _send_forum_video(context.bot, forum_chat_id, thread_id, file_id)
    except Exception:
        logger.exception("intake video to cabinet failed user_id=%s", user_id)
        return False


async def _post_review_job_to_forum(
    context: ContextTypes.DEFAULT_TYPE,
    job_id: int,
    user_id: int,
    *,
    manual: bool = False,
    skip_video: bool = False,
) -> bool:
    settings: Settings = context.application.bot_data.get("settings")
    if not settings or not settings.coach_forum_chat_id:
        logger.error("COACH_FORUM_CHAT_ID не задан — кабинет недоступен")
        return False

    job = await asyncio.to_thread(storage.get_review_job, job_id)
    if not job:
        return False

    forum_chat_id = int(settings.coach_forum_chat_id)
    logger.info(
        "Posting review job_id=%s user_id=%s to forum chat_id=%s manual=%s",
        job_id,
        user_id,
        forum_chat_id,
        manual,
    )
    try:
        thread_id = await _ensure_player_forum_topic(context, user_id, forum_chat_id)
    except Exception:
        logger.exception("ensure forum topic failed job_id=%s", job_id)
        return False
    if thread_id is None:
        logger.error(
            "create_forum_topic вернул None chat_id=%s — включены Topics? "
            "Бот админ с Manage Topics?",
            forum_chat_id,
        )
        return False

    await asyncio.to_thread(
        storage.update_review_job,
        job_id,
        forum_chat_id=forum_chat_id,
        message_thread_id=thread_id,
        status=review.STATUS_QUEUED,
    )

    acquisition_code = await asyncio.to_thread(storage.get_acquisition_source, user_id)
    channel = cabinet.format_review_origin(
        source_channel=job.get("source_channel") or "",
        acquisition_label=acquisition.source_label(acquisition_code),
    )
    if manual:
        video_hint = (
            "Видео уже в теме — напишите игроку комментарий."
            if skip_video
            else "Видео ниже — напишите игроку комментарий в эту тему."
        )
        header = (
            f"⚠️ Нужен ручной разбор #{job_id}\n"
            f"user_id: {user_id}\n"
            f"{channel}"
            f"Фокус intake: {(job.get('stroke') or '—')}\n"
            f"Статус: AI не смог разобрать\n\n"
            f"{video_hint}"
        )
    else:
        video_hint = "Видео — в теме выше.\n" if skip_video else ""
        header = (
            f"🆕 Разбор #{job_id}\n"
            f"user_id: {user_id}\n"
            f"{channel}"
            f"Фокус: {job.get('focus_text') or '—'}\n"
            f"Упражнение: {job.get('drill_text') or '—'}\n"
            f"Статус: черновик AI уже у игрока. Тренер — главный.\n\n"
            f"{video_hint}"
            f"💬 «Ответить игроку» — текст / голос / кружок. На AI не влияет.\n"
            f"✏️ «Поправить AI» — скопируйте разбор ниже, поправьте "
            f"и отправьте. Сохранится как эталон, игроку не уйдёт.\n"
            f"✅ «ОК» — разбор компетентный, закрепляем."
        )
    try:
        await context.bot.send_message(
            chat_id=forum_chat_id,
            message_thread_id=thread_id,
            text=header,
        )
        if not skip_video:
            await _send_forum_video(
                context.bot,
                forum_chat_id,
                thread_id,
                job["video_file_id"],
            )
        draft = (job.get("draft_text") or "").strip()
        attached_actions = False
        if manual:
            note = draft or "AI не вернул разбор."
            chunks = _split_message(f"⚠️ Сбой AI:\n\n{note}")
        elif draft:
            cabinet_draft = review.strip_cabinet_draft(draft) or draft
            chunks = _split_message(
                f"🤖 Черновик AI (помощник, уже у игрока):\n\n{cabinet_draft}"
            )
        else:
            chunks = []
        if chunks:
            last = len(chunks) - 1
            for i, chunk in enumerate(chunks):
                kwargs = {}
                if i == last:
                    kwargs["reply_markup"] = review.coach_action_keyboard(job_id)
                    attached_actions = True
                await context.bot.send_message(
                    chat_id=forum_chat_id,
                    message_thread_id=thread_id,
                    text=chunk,
                    **kwargs,
                )
        if not attached_actions:
            await context.bot.send_message(
                chat_id=forum_chat_id,
                message_thread_id=thread_id,
                text="Действия по этому разбору:",
                reply_markup=review.coach_action_keyboard(job_id),
            )
        logger.info("Review job_id=%s posted to forum thread_id=%s", job_id, thread_id)
    except Exception:
        logger.exception(
            "post review to forum failed job_id=%s chat_id=%s thread_id=%s",
            job_id,
            forum_chat_id,
            thread_id,
        )
        return False
    return True


class _ApplicationContext:
    def __init__(self, application):
        self.application = application
        self.bot = application.bot


async def post_ios_review_to_forum(application, job_id, player_id, path) -> None:
    """После HTTP enqueue: Forum, затем ai_sent, затем удалить temp. Как у бота."""
    try:
        try:
            posted = await _post_review_job_to_forum(
                _ApplicationContext(application), job_id, player_id
            )
            if not posted:
                logger.error(
                    "Не удалось запостить iOS review job_id=%s в Forum", job_id
                )
        except Exception:
            logger.exception("iOS forum post failed job_id=%s", job_id)
        job = await asyncio.to_thread(storage.get_review_job, job_id)
        text = ""
        if job:
            text = (job.get("final_text") or "").strip() or (
                job.get("draft_text") or ""
            )
        await asyncio.to_thread(
            storage.mark_review_sent,
            job_id,
            status=review.STATUS_AI_SENT,
            final_text=text,
        )
    finally:
        Path(path).unlink(missing_ok=True)


async def _post_failed_analysis_to_cabinet(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    user_id: int,
    video_file_id: str,
    video_mime: str,
    language_code: str,
    video_context: Optional[dict],
    error: Exception,
    skip_video: bool = False,
) -> bool:
    """Черновик сбоя в кабинет; видео уже могло уйти сразу после intake."""
    stroke = ""
    if video_context:
        stroke = (video_context.get("stroke") or "") or ""
    err_text = f"{type(error).__name__}: {error}"[:800]
    job_id = await asyncio.to_thread(
        storage.create_review_job,
        user_id,
        video_file_id=video_file_id,
        video_mime=video_mime,
        language_code=language_code,
        draft_text=err_text,
        focus_text="",
        drill_text="",
        drill_id=None,
        scores={},
        stroke=stroke,
    )
    posted = await _post_review_job_to_forum(
        context, job_id, user_id, manual=True, skip_video=skip_video
    )
    await asyncio.to_thread(
        storage.update_review_job,
        job_id,
        status=review.STATUS_AI_FAILED,
    )
    await _log_event(user_id, EVENT_REVIEW_QUEUED, f"failed:{job_id}")
    return posted


async def _analyze_video_once(
    analyzer: VideoAnalyzer,
    *,
    temp_path: Path,
    user_comment,
    player_history,
    language_code: str,
    player_profile,
    video_context,
    use_model: str,
    active_focus,
    drills_catalog,
    coach_corrections=None,
    prompt_context=None,
):
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
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
                coach_corrections,
                prompt_context,
            ),
            timeout=200,
        )
    except asyncio.TimeoutError as exc:
        raise TimeoutError("Превышено время ожидания ответа AI.") from exc


def _remember_cleanup(user_data: dict, message_id) -> None:
    if not isinstance(message_id, int):
        return
    ids = user_data.setdefault(_CLEANUP_KEY, [])
    if message_id not in ids:
        ids.append(message_id)


async def _delete_tracked_messages(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int
) -> None:
    """Убирает вопросы и статус между видео и разбором."""
    ids = context.user_data.pop(_CLEANUP_KEY, None) or []
    for message_id in reversed(ids):
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except BadRequest:
            continue
        except Exception:
            logger.warning(
                "Не удалось удалить message_id=%s chat_id=%s",
                message_id,
                chat_id,
                exc_info=True,
            )


async def _present_analysis_to_player(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_id: int,
    user_id: int,
    lang: str,
    language_code: str,
    report: str,
    scores: dict,
    stroke: str,
    focus_text: str,
    drill_text: str,
    drill_id: Optional[str],
    preface: Optional[str] = None,
    offer_coach_button: bool = True,
    create_practice: bool = True,
) -> None:
    """Показывает AI-разбор игроку и включает диалог follow-up."""
    state = {
        "step": "summary",
        "language_code": language_code,
        "sections": parse_dialog_sections(report, language_code),
        "visited_categories": [],
        "error_index": 0,
        "focus_text": focus_text or "",
        "drill_text": drill_text or "",
        "shown_count": 0,
    }
    payload = {
        "analysis": report,
        "history": [],
        "stroke": stroke or None,
        "analysis_dialog": state,
    }
    context.user_data[DIALOG_KEY] = state
    context.user_data[SESSION_KEY] = payload
    context.user_data["user_id"] = user_id
    await asyncio.to_thread(storage.save_active_session, user_id, payload)

    if preface:
        await context.bot.send_message(chat_id=chat_id, text=preface)

    total = observation_total(state)
    summary = format_summary_message(lang, state)
    if scores:
        summary = f"{summary}\n\n{format_scores_line(scores, lang)}"
    await _reply_dialog(
        context,
        chat_id,
        summary,
        None if total else keyboard_closing(lang),
    )

    if total:
        await asyncio.sleep(2)
        state["error_index"] = 0
        state["step"] = "observations"
        state["shown_count"] = 1
        await _reply_dialog(
            context,
            chat_id,
            format_error_card(lang, state),
            keyboard_observation(lang, state, 0),
        )
        await asyncio.to_thread(storage.save_active_session, user_id, payload)

    card = await asyncio.to_thread(storage.get_trainer_card_by_player, user_id)
    if card and offer_coach_button:
        await context.bot.send_message(
            chat_id=chat_id,
            text=card["name"],
            reply_markup=review.keyboard_message_coach(lang, player_id=user_id),
        )

    if create_practice:
        await asyncio.to_thread(
            storage.create_practice_plan,
            user_id,
            focus_text,
            drill_text,
            drill_id,
        )


async def _deliver_review_to_player(
    context: ContextTypes.DEFAULT_TYPE,
    job: dict,
    *,
    final_text: str,
    status: str,
    coach_notes: str = "",
) -> None:
    """Доставка для legacy/fallback (когда AI ещё не ушёл игроку)."""
    user_id = int(job["user_id"])
    lang = "ru" if (job.get("language_code") or "").startswith("ru") else "en"
    language_code = job.get("language_code") or lang
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
    preface = (
        t(lang, "review_delivered_coach")
        if status == review.STATUS_SENT_COACH
        else None
    )
    chat_id = _player_chat_id(user_id)
    card = await asyncio.to_thread(storage.get_trainer_card_by_player, user_id)
    if chat_id is None and card:
        chat_id = int(card["trainer_telegram_id"])
        preface = f"{card['name']}\n\n{preface}" if preface else card["name"]
    if chat_id is None:
        logger.warning("deliver: нет telegram identity player_id=%s", user_id)
        return
    await _present_analysis_to_player(
        context,
        chat_id=chat_id,
        user_id=user_id,
        lang=lang,
        language_code=language_code,
        report=final_text,
        scores=scores,
        stroke=stroke,
        focus_text=focus_text,
        drill_text=drill_text,
        drill_id=drill_id,
        preface=preface,
        offer_coach_button=True,
        create_practice=True,
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
    _remember_cleanup(context.user_data, getattr(status_message, "message_id", None))
    pending = context.user_data.get("pending_video")
    if not pending:
        await status_message.edit_text(t(lang, "video_not_found"))
        return

    mime_type = pending["mime_type"]
    user_comment = pending.get("comment")
    video_context = pending.get("video_context")
    video_file_id = pending["file_id"]
    cabinet_video_sent = bool(pending.get("cabinet_video_sent"))

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
        plan = await asyncio.to_thread(services.get_plan, user_id)
        if billing.MONETIZATION_ENABLED and plan.analyses_left <= 0:
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

        stroke = ""
        intake_strokes = None
        if video_context:
            stroke = (video_context.get("stroke") or "") or ""
            intake_strokes = video_context.get("strokes")
        analysis_ctx = await asyncio.to_thread(
            services.load_analysis_context, user_id, stroke, intake_strokes
        )
        if await _followup_scope_on(context, context.user_data):
            analysis_ctx["omit_chat_notes"] = True
        player_history = analysis_ctx["history"]
        player_profile = analysis_ctx["profile"]
        coach_corrections = analysis_ctx["corrections"]
        active_focus = analysis_ctx["focus"]
        drills_catalog = analysis_ctx["drills_catalog"]
        settings: Settings = context.application.bot_data.get("settings")
        if model_override:
            use_model = model_override
        elif settings:
            use_model = settings.model_for(plan.is_pro)
        else:
            use_model = analyzer._model
        fallback_model = (
            settings.gemini_model_free
            if settings and settings.gemini_model_free != use_model
            else None
        )
        # Уже на запасной (ручной retry:simple) — второй раз не прыгаем.
        if settings and model_override and model_override == settings.gemini_model_free:
            fallback_model = None

        used_simple = False
        try:
            result = await _analyze_video_once(
                analyzer,
                temp_path=temp_path,
                user_comment=user_comment,
                player_history=player_history,
                language_code=language_code,
                player_profile=player_profile,
                video_context=video_context,
                use_model=use_model,
                active_focus=active_focus,
                drills_catalog=drills_catalog,
                coach_corrections=coach_corrections,
                prompt_context=analysis_ctx,
            )
        except Exception as primary_exc:
            logger.warning(
                "Основная модель %s упала user_id=%s: %s",
                use_model,
                user_id,
                primary_exc,
            )
            await _cabinet_notify(
                context,
                user_id,
                cabinet.format_analysis_failed(
                    user_id,
                    error=f"{type(primary_exc).__name__}: {primary_exc}",
                ),
            )
            if not fallback_model:
                raise
            await _edit_or_reply_status(
                context,
                chat_id,
                status_message,
                t(lang, "analysis_fallback_status"),
            )
            try:
                result = await _analyze_video_once(
                    analyzer,
                    temp_path=temp_path,
                    user_comment=user_comment,
                    player_history=player_history,
                    language_code=language_code,
                    player_profile=player_profile,
                    video_context=video_context,
                    use_model=fallback_model,
                    active_focus=active_focus,
                    drills_catalog=drills_catalog,
                    coach_corrections=coach_corrections,
                    prompt_context=analysis_ctx,
                )
                used_simple = True
                logger.info(
                    "Запасная модель %s сработала user_id=%s",
                    fallback_model,
                    user_id,
                )
            except Exception as fallback_exc:
                logger.exception(
                    "Запасная модель тоже упала user_id=%s primary=%s fallback=%s",
                    user_id,
                    primary_exc,
                    fallback_exc,
                )
                report_failure(fallback_exc, "AI analysis failed on both models")
                await _log_event(
                    user_id,
                    EVENT_ANALYSIS_FAILED,
                    f"both:{type(fallback_exc).__name__}:{str(fallback_exc)[:160]}",
                )
                await _cabinet_notify(
                    context,
                    user_id,
                    cabinet.format_analysis_failed(
                        user_id,
                        error=(
                            f"primary+fallback: {type(fallback_exc).__name__}: "
                            f"{fallback_exc}"
                        ),
                    ),
                )
                await _post_failed_analysis_to_cabinet(
                    context,
                    user_id=user_id,
                    video_file_id=video_file_id,
                    video_mime=mime_type,
                    language_code=language_code,
                    video_context=video_context,
                    error=fallback_exc,
                    skip_video=cabinet_video_sent,
                )
                await _edit_or_reply_status(
                    context,
                    chat_id,
                    status_message,
                    t(lang, "error_overloaded"),
                    reply_markup=_retry_keyboard(lang, offer_simple=False),
                )
                return

        prepared = services.prepare_report(result, video_context)
        report = prepared.text
        stroke = prepared.stroke or None
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

        focus_text = prepared.focus
        await asyncio.to_thread(
            services.save_analysis_session, user_id, prepared, language_code
        )
        subject_name = (pending.get("subject_name") or "").strip()
        context.user_data.pop("pending_video", None)

        picked = await asyncio.to_thread(
            drills.pick_drills, prepared.drill_ids, None, 2
        )
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

        await _delete_tracked_messages(context, chat_id)
        preface = t(lang, "analysis_used_simple_model") if used_simple else None
        if subject_name:
            preface = f"{subject_name}\n\n{preface}" if preface else subject_name

        # Игрок сразу получает AI-разбор и может общаться с ботом.
        await _present_analysis_to_player(
            context,
            chat_id=chat_id,
            user_id=user_id,
            lang=lang,
            language_code=language_code,
            report=report,
            scores=prepared.scores,
            stroke=stroke or "",
            focus_text=focus_text,
            drill_text=drill_text,
            drill_id=drill_id,
            preface=preface,
            offer_coach_button=True,
            create_practice=True,
        )
        await _log_event(user_id, EVENT_ANALYSIS_SUCCESS)
        if cabinet.same_focus(active_focus, focus_text):
            analyses_count = await asyncio.to_thread(storage.get_session_count, user_id)
            await _cabinet_notify(
                context,
                user_id,
                cabinet.format_same_focus(
                    user_id,
                    focus=focus_text,
                    previous_focus=active_focus or "",
                    stroke=stroke or "",
                    analyses_count=analyses_count,
                ),
            )

        # Тот же разбор — в кабинет тренера; тренер дополняет свободными сообщениями.
        job_id = await asyncio.to_thread(
            services.enqueue_review,
            user_id,
            prepared,
            language_code=language_code,
            video_file_id=video_file_id,
            video_mime=mime_type,
            drill_text=drill_text,
            drill_id=drill_id,
        )
        await _log_event(user_id, EVENT_REVIEW_QUEUED, str(job_id))
        posted = await _post_review_job_to_forum(
            context, job_id, user_id, skip_video=cabinet_video_sent
        )
        await asyncio.to_thread(
            storage.mark_review_sent,
            job_id,
            status=review.STATUS_AI_SENT,
            final_text=report,
        )
        if not posted:
            logger.error(
                "Не удалось запостить review job_id=%s в Forum — "
                "проверьте COACH_FORUM_CHAT_ID и права бота",
                job_id,
            )
            await context.bot.send_message(
                chat_id=chat_id, text=t(lang, "review_forum_failed")
            )
            admin_ids = context.application.bot_data.get("admin_user_ids") or ()
            if admin_ids:
                await alert_admins(
                    context.bot,
                    admin_ids,
                    (
                        f"Forum post failed job_id={job_id} user_id={user_id}. "
                        f"chat_id={getattr(settings, 'coach_forum_chat_id', None)}. "
                        "Проверьте Topics + Manage Topics у бота."
                    ),
                )

    except Exception as exc:
        # Сбой без успешного AI (в т.ч. primary без fallback) — видео всё равно в кабинет.
        logger.exception("Ошибка анализа видео для user_id=%s", user_id)
        report_failure(exc)
        await _log_event(user_id, EVENT_ANALYSIS_FAILED, str(exc)[:200])
        await _cabinet_notify(
            context,
            user_id,
            cabinet.format_analysis_failed(
                user_id, error=f"{type(exc).__name__}: {exc}"
            ),
        )
        if video_file_id:
            try:
                await _post_failed_analysis_to_cabinet(
                    context,
                    user_id=user_id,
                    video_file_id=video_file_id,
                    video_mime=mime_type,
                    language_code=language_code,
                    video_context=video_context,
                    error=exc,
                    skip_video=cabinet_video_sent,
                )
            except Exception:
                logger.exception(
                    "Не удалось отправить failed-video в кабинет user_id=%s", user_id
                )
        if not is_model_overloaded(exc):
            admin_ids = context.application.bot_data.get("admin_user_ids") or ()
            if admin_ids:
                await alert_admins(
                    context.bot,
                    admin_ids,
                    f"Ошибка анализа user_id={user_id}: "
                    f"{type(exc).__name__}: {exc}"[:500],
                )
        await _edit_or_reply_status(
            context,
            chat_id,
            status_message,
            (
                t(lang, "error_overloaded")
                if is_model_overloaded(exc)
                else format_analysis_error(exc, lang)
            ),
            parse_mode=None if is_model_overloaded(exc) else ParseMode.MARKDOWN,
            reply_markup=_retry_keyboard(lang, offer_simple=False),
        )
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


async def _edit_or_reply_status(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    status_message,
    text: str,
    *,
    parse_mode: Optional[str] = None,
    reply_markup=None,
) -> None:
    """edit_text статуса; если нельзя (Message can't be edited) — новое сообщение."""
    try:
        await status_message.edit_text(
            text, parse_mode=parse_mode, reply_markup=reply_markup
        )
    except BadRequest:
        sent = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        _remember_cleanup(context.user_data, sent.message_id)


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    lang = _lang_from_update(update, context)
    key = query.data.removeprefix("fb:")
    event_type = _FEEDBACK_EVENTS.get(key)
    if not event_type:
        return

    user_id = query.from_user.id
    context.user_data["user_id"] = user_id
    await _touch_user(update, context)
    await _log_event(user_id, event_type)
    await _cabinet_notify(
        context,
        user_id,
        cabinet.format_feedback(user_id, kind=key),
        user=query.from_user,
    )

    try:
        await query.edit_message_text(t(lang, "feedback_thanks"))
    except BadRequest:
        await query.message.reply_text(t(lang, "feedback_thanks"))


async def handle_retry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    lang = _lang_from_update(update, context)
    language_code = _language_code_from_context(context)

    player_id = await _touch_user(update, context)
    if player_id is None:
        return

    if not context.user_data.get("pending_video"):
        await query.message.reply_text(
            t(lang, "video_not_found_retry"),
            reply_markup=_main_menu_keyboard(lang),
        )
        return

    use_simple = (query.data or "") == "retry:simple"
    await _cabinet_notify(
        context,
        player_id,
        cabinet.format_analysis_failed(player_id, retry=True, simple=use_simple),
        user=query.from_user,
    )
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
        player_id,
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

    lang = _lang_from_update(update, context)
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    raw = query.data
    if raw.startswith("pc:"):
        pieces = raw.split(":", 2)
        if len(pieces) != 3:
            return
        try:
            bound_id = int(pieces[1])
        except ValueError:
            return
        owner = await asyncio.to_thread(storage.get_trainer_card_by_player, bound_id)
        if not owner or int(owner["trainer_telegram_id"]) != query.from_user.id:
            await query.message.reply_text(t(lang, "tr_not_yours"))
            return
        user_id = bound_id
        raw = "p:" + pieces[2]
    context.user_data["user_id"] = user_id
    await _touch_user(update, context)
    context.user_data["user_id"] = user_id

    parts = raw.split(":")
    if len(parts) < 2:
        return
    kind = parts[1]

    async def _practice_reply(text: str, **kwargs) -> None:
        body = text
        markup = kwargs.get("reply_markup")
        card = await asyncio.to_thread(storage.get_trainer_card_by_player, user_id)
        if card:
            body = f"{card['name']}\n\n{body}"
            if markup is not None:
                kwargs["reply_markup"] = practice.markup_for_player(markup, user_id)
        await query.message.reply_text(body, **kwargs)

    plan = await asyncio.to_thread(storage.get_active_practice_plan, user_id)

    if kind == "mute":
        await asyncio.to_thread(storage.snooze_practice_plan, user_id, 7)
        await _practice_reply(t(lang, "practice_muted"))
        return

    if kind == "date":
        if not plan or plan.get("status") not in ("awaiting_date", "scheduled"):
            await _practice_reply(t(lang, "practice_no_plan"))
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
            await _practice_reply(
                t(lang, "practice_date_unknown"),
                reply_markup=practice.keyboard_after_date_set(lang),
            )
            await _cabinet_notify(
                context,
                user_id,
                cabinet.format_practice_date(
                    user_id,
                    date_label=practice_day.strftime("%d.%m.%Y"),
                    focus=plan.get("focus_text") or "",
                    drill=plan.get("drill_text") or "",
                    unknown=True,
                ),
                user=query.from_user,
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
        await _practice_reply(
            t(lang, "practice_date_saved", date=date_label),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=practice.keyboard_after_date_set(lang),
        )
        await _cabinet_notify(
            context,
            user_id,
            cabinet.format_practice_date(
                user_id,
                date_label=date_label,
                focus=plan.get("focus_text") or "",
                drill=plan.get("drill_text") or "",
            ),
            user=query.from_user,
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
            await _practice_reply(t(lang, "practice_no_plan"))
            return
        action = parts[2] if len(parts) > 2 else ""
        if action == "ok":
            await _practice_reply(t(lang, "practice_pre_ok"))
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
            await _practice_reply(t(lang, "practice_no_plan"))
            return
        answer = parts[2] if len(parts) > 2 else ""
        await asyncio.to_thread(
            storage.set_practice_post_answer, int(plan["id"]), answer
        )
        await _log_event(user_id, EVENT_PRACTICE_POST_ANSWERED, answer)
        await _cabinet_notify(
            context,
            user_id,
            cabinet.format_practice_post(
                user_id,
                answer=answer,
                focus=plan.get("focus_text") or "",
                drill=plan.get("drill_text") or "",
            ),
            user=query.from_user,
        )

        if answer == practice.POST_YES:
            next_video = await asyncio.to_thread(storage.get_latest_next_video, user_id)
            await _practice_reply(
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
            await _practice_reply(
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
            await _practice_reply(t(lang, "practice_post_skip"))
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

    lang = _lang_from_update(update, context)
    language_code = _language_code_from_context(context)
    prompts = _QUICK_PROMPTS.get(lang, _QUICK_PROMPTS["en"])

    key = query.data.removeprefix("q:")
    question = QUICK_QUESTIONS.get(key)
    if not question:
        return

    label_key, prompt_key = question
    label = prompts[label_key]
    prompt = prompts[prompt_key]
    await _touch_user(update, context)
    subject_id = query.from_user.id
    if await asyncio.to_thread(storage.is_trainer, query.from_user.id):
        bound = context.user_data.get(trainer.SESSION_PLAYER_KEY)
        if bound:
            subject_id = int(bound)
    context.user_data["user_id"] = subject_id

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

    # Игрок: написать тренеру (через тему кабинета, без привязки к open job)
    if query.data == "rvp:msg" or query.data.startswith("rvp:msg:"):
        lang = _lang_from_update(update, context)
        target_id = user_id
        card_name = ""
        if query.data.startswith("rvp:msg:"):
            try:
                target_id = int(query.data.split(":", 2)[2])
            except ValueError:
                return
            card = await asyncio.to_thread(
                storage.get_trainer_card_by_player, target_id
            )
            if not card or int(card["trainer_telegram_id"]) != query.from_user.id:
                await query.message.reply_text(t(lang, "tr_not_yours"))
                return
            if int(card["archived"]):
                await query.message.reply_text(t(lang, "tr_need_card"))
                return
            card_name = card["name"]
        forum_chat_id = settings.coach_forum_chat_id if settings else None
        topic = None
        if forum_chat_id:
            topic = await asyncio.to_thread(
                storage.get_player_forum_topic, target_id, int(forum_chat_id)
            )
        if not topic:
            await query.message.reply_text(t(lang, "review_no_topic"))
            return
        context.user_data[review.PLAYER_MSG_PENDING_KEY] = (
            target_id if card_name else True
        )
        if card_name:
            await query.message.reply_text(t(lang, "tr_msg_prompt", name=card_name))
        else:
            await query.message.reply_text(t(lang, "review_message_prompt"))
        return

    if query.data.startswith("rv:"):
        # Старые кнопки send/replace/notes больше не используются.
        await query.message.reply_text(
            "Кнопки устарели. Пишите в тему свободно — сообщение уйдёт игроку."
        )


async def handle_coach_eval_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    settings: Settings = context.application.bot_data.get("settings")
    if not settings or not settings.is_coach(query.from_user.id):
        await query.answer("Это может сделать только тренер.", show_alert=True)
        return

    parts = query.data.split(":")
    if len(parts) != 4 or parts[0] != "ce":
        await query.answer()
        return
    _, kind, job_id_raw, payload = parts
    try:
        job_id = int(job_id_raw)
    except ValueError:
        await query.answer("Некорректная заявка.", show_alert=True)
        return

    job = await asyncio.to_thread(storage.get_review_job, job_id)
    if not job:
        await query.answer("Разбор не найден.", show_alert=True)
        return

    if kind in ("r", "t"):
        await query.answer(
            "Кнопки устарели. Используйте «Ответить игроку», "
            "«Поправить AI» или «ОК».",
            show_alert=True,
        )
        return

    if kind != "a":
        await query.answer()
        return

    if payload == review.ACTION_APPROVE:
        await asyncio.to_thread(
            storage.upsert_coach_evaluation,
            job_id,
            player_id=int(job["user_id"]),
            coach_user_id=int(query.from_user.id),
            rating=review.RATING_OK,
        )
        await asyncio.to_thread(storage.set_pending_coach_action, job_id, None)
        if job.get("status") != review.STATUS_SENT_FALLBACK:
            text = (job.get("final_text") or "").strip() or (
                job.get("draft_text") or ""
            )
            await asyncio.to_thread(
                storage.mark_review_sent,
                job_id,
                status=review.STATUS_SENT_COACH,
                final_text=text,
                coach_notes=job.get("coach_notes") or "",
            )
        await query.answer("Закреплено")
        try:
            await query.edit_message_reply_markup(
                reply_markup=review.coach_action_keyboard(
                    job_id, action=review.ACTION_APPROVE
                )
            )
        except BadRequest:
            pass
        await query.message.reply_text(
            "✅ ОК — черновик AI закреплён как компетентный. "
            "Помощник будет ориентироваться на такие разборы."
        )
        return

    if payload not in review.VALID_COACH_ACTIONS:
        await query.answer()
        return

    await asyncio.to_thread(storage.set_pending_coach_action, job_id, payload)
    if payload == review.ACTION_FIX_AI:
        await query.answer("Режим: поправить AI")
        hint = (
            "Скопируйте черновик AI, поправьте и отправьте. "
            "Игроку не уйдёт — сохранится как эталон для следующих ответов."
        )
    else:
        await query.answer("Режим: ответ игроку")
        hint = "Пишите игроку (текст / голос / кружок). На AI не влияет."
    try:
        await query.edit_message_reply_markup(
            reply_markup=review.coach_action_keyboard(job_id, action=payload)
        )
    except BadRequest:
        pass
    await query.message.reply_text(hint)


def _coach_forum_has_content(message) -> bool:
    """Есть ли в сообщении контент, который можно доставить игроку."""
    return bool(
        message.text
        or message.caption
        or message.photo
        or message.video
        or message.video_note
        or message.audio
        or message.voice
        or message.document
        or message.sticker
        or message.animation
        or message.contact
        or message.location
        or message.venue
        or message.poll
        or message.dice
    )


async def _resolve_coach_forum_player(
    message, settings: Optional[Settings]
) -> Optional[int]:
    """Если это сообщение тренера в теме игрока — вернуть player_id."""
    if not settings or not settings.coach_forum_chat_id:
        return None
    if message.chat_id != settings.coach_forum_chat_id:
        return None
    if not message.from_user or not settings.is_coach(message.from_user.id):
        return None
    thread_id = message.message_thread_id
    if not thread_id:
        return None
    topic = await asyncio.to_thread(
        storage.get_player_by_forum_thread,
        int(settings.coach_forum_chat_id),
        int(thread_id),
    )
    if not topic:
        return None
    return int(topic["user_id"])


async def _handle_coach_forum_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Сообщение тренера в теме: либо игроку, либо эталон для ИИ."""
    message = update.message
    if not message or not _coach_forum_has_content(message):
        return False

    settings: Settings = context.application.bot_data.get("settings")
    player_id = await _resolve_coach_forum_player(message, settings)
    if player_id is None:
        return False

    language_code = await asyncio.to_thread(storage.get_user_language_code, player_id)
    card = await asyncio.to_thread(storage.get_trainer_card_by_player, player_id)
    if not language_code and card:
        language_code = await asyncio.to_thread(
            storage.get_user_language_code, int(card["trainer_telegram_id"])
        )
    lang = "ru" if (language_code or "").startswith("ru") else "en"

    if message.text:
        user_text = message.text.strip()
        if user_text and survey.is_coach_survey_command(user_text):
            ok = await _send_no_video_survey(
                context.bot,
                player_id,
                lang,
                source="manual",
                settings=settings,
            )
            if ok:
                await message.reply_text(t(lang, "survey_coach_sent"))
            else:
                await message.reply_text(t(lang, "survey_coach_failed"))
            return True

    pending_job = await asyncio.to_thread(
        storage.get_pending_review_job_for_thread,
        int(settings.coach_forum_chat_id),
        int(message.message_thread_id),
    )
    pending_action = (pending_job or {}).get("pending_coach_action") or ""
    if pending_action in review.FIX_AI_PENDING:
        return await _store_coach_ai_fix(message, pending_job, player_id)

    chat_id = _player_chat_id(player_id)
    name_prefix = ""
    if chat_id is None and card:
        chat_id = int(card["trainer_telegram_id"])
        name_prefix = f"{card['name']}\n\n"
    if chat_id is None:
        logger.warning("coach message: нет telegram identity player_id=%s", player_id)
        await message.reply_text("⚠️ У игрока нет Telegram — сообщение не доставлено.")
        return True

    try:
        if message.text:
            user_text = message.text.strip()
            if not user_text:
                return False
            body = name_prefix + t(lang, "review_coach_message", text=user_text)
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=body,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except BadRequest:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=body,
                )
        else:
            header = name_prefix + t(lang, "review_coach_media_header")
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=header,
                    parse_mode=ParseMode.MARKDOWN,
                )
            except BadRequest:
                await context.bot.send_message(chat_id=chat_id, text=header)
            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id,
            )
    except Exception:
        logger.exception(
            "Не удалось отправить сообщение тренера игроку user_id=%s", player_id
        )
        await message.reply_text("⚠️ Не удалось доставить игроку. Попробуйте ещё раз.")
        return True

    await message.reply_text("✅ Отправлено игроку.")
    return True


async def _store_coach_ai_fix(message, job: dict, player_id: int) -> bool:
    pending_action = job.get("pending_coach_action") or ""
    if not message.text or not message.text.strip():
        await message.reply_text(
            "В режиме правки AI нужен текст. "
            "Скопируйте разбор, поправьте и отправьте."
        )
        return True
    append = pending_action == review.ACTION_FIX_AI_CONT
    try:
        await asyncio.to_thread(
            storage.save_coach_correction,
            int(job["id"]),
            message.text.strip(),
            player_id=int(player_id),
            coach_user_id=int(message.from_user.id),
            append=append,
        )
        await asyncio.to_thread(
            storage.set_pending_coach_action,
            int(job["id"]),
            review.ACTION_FIX_AI_CONT,
        )
    except Exception:
        logger.exception("Не удалось сохранить эталон правки user_id=%s", player_id)
        await message.reply_text("⚠️ Не удалось сохранить эталон. Попробуйте ещё раз.")
        return True
    if append:
        await message.reply_text("✅ Дописано к эталону. Игроку не отправлено.")
    else:
        await message.reply_text(
            "✅ Эталон сохранён. Игроку не отправлено. "
            "Можно дописать ещё или нажать «Ответить игроку»."
        )
    return True


async def _handle_player_coach_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str
) -> bool:
    pending = context.user_data.get(review.PLAYER_MSG_PENDING_KEY)
    if not pending:
        return False
    message = update.message
    lang = _lang_from_update(update, context)
    user_text_raw = (message.text or "").strip()
    if isinstance(pending, int) and trainer.is_cancel_text(lang, user_text_raw):
        context.user_data.pop(review.PLAYER_MSG_PENDING_KEY, None)
        await message.reply_text(t(lang, "tr_cancelled"))
        await _trainer_show_home(message, lang, message.from_user.id)
        return True
    user_id = message.from_user.id
    context.user_data.pop(review.PLAYER_MSG_PENDING_KEY, None)
    if isinstance(pending, int):
        user_id = pending

    settings: Settings = context.application.bot_data.get("settings")
    forum_chat_id = settings.coach_forum_chat_id if settings else None
    if not forum_chat_id:
        await message.reply_text(t(lang, "review_no_topic"))
        return True
    if isinstance(pending, int):
        player_id = pending
    else:
        player_id = _get_user_id(context.user_data) or user_id
    topic = await asyncio.to_thread(
        storage.get_player_forum_topic, player_id, int(forum_chat_id)
    )
    if not topic:
        await message.reply_text(t(lang, "review_no_topic"))
        return True

    uname = message.from_user.username or message.from_user.first_name or "player"
    await context.bot.send_message(
        chat_id=int(forum_chat_id),
        message_thread_id=int(topic["message_thread_id"]),
        text=(f"💬 Сообщение от игрока (@{uname} / {player_id}):\n\n{user_text}"),
    )
    await message.reply_text(t(lang, "review_message_sent"))
    return True


async def _retitle_trainer_topic(
    context: ContextTypes.DEFAULT_TYPE, player_id: int, player_name: str
) -> None:
    settings: Settings = context.application.bot_data.get("settings")
    if not settings or not settings.coach_forum_chat_id:
        return
    forum_id = int(settings.coach_forum_chat_id)
    topic = await asyncio.to_thread(storage.get_player_forum_topic, player_id, forum_id)
    if not topic:
        return
    card = await asyncio.to_thread(storage.get_trainer_card_by_player, player_id)
    if not card:
        return
    coach = await asyncio.to_thread(
        storage.trainer_label, int(card["trainer_telegram_id"])
    )
    title = trainer.topic_title(player_name, coach)
    try:
        await context.bot.edit_forum_topic(
            chat_id=forum_id,
            message_thread_id=int(topic["message_thread_id"]),
            name=title,
        )
    except Exception:
        logger.exception("Не удалось переименовать тему player_id=%s", player_id)
    await asyncio.to_thread(
        storage.update_player_forum_title, player_id, forum_id, title
    )


def _trainer_bind_session(user_data: dict, player_id: int) -> None:
    user_data["user_id"] = player_id
    if user_data.get(trainer.SESSION_PLAYER_KEY) != player_id:
        user_data.pop(SESSION_KEY, None)
        user_data[trainer.SESSION_PLAYER_KEY] = player_id


async def _trainer_on_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    lang: str,
    language_code: str,
    user_text: str,
) -> None:
    message = update.message
    telegram_id = message.from_user.id
    wiz = trainer.wizard(context.user_data)

    if trainer.is_cancel_text(lang, user_text) and (
        wiz or is_onboarding_active(context.user_data)
    ):
        trainer.clear_wizard(context.user_data)
        clear_onboarding_state(context.user_data)
        await message.reply_text(t(lang, "tr_cancelled"))
        await _trainer_show_home(message, lang, telegram_id)
        return

    if wiz and wiz.get("kind") == "await_name":
        name = trainer.normalize_name(user_text)
        problem = trainer.name_problem(name)
        if problem:
            await message.reply_text(t(lang, problem))
            return
        if await asyncio.to_thread(storage.trainer_name_taken, telegram_id, name):
            await message.reply_text(t(lang, "tr_name_taken"))
            return
        trainer.set_wizard(
            context.user_data, "create", trainer_id=telegram_id, name=name
        )
        start_onboarding_state(context.user_data)
        await _send_onboarding_question(
            message,
            lang,
            "level",
            intro=name,
            user_data=context.user_data,
        )
        return

    if wiz and wiz.get("kind") == "rename":
        name = trainer.normalize_name(user_text)
        problem = trainer.name_problem(name)
        if problem:
            await message.reply_text(t(lang, problem))
            return
        result = await asyncio.to_thread(
            storage.rename_trainer_card, telegram_id, int(wiz["player_id"]), name
        )
        trainer.clear_wizard(context.user_data)
        if result == "taken":
            await message.reply_text(t(lang, "tr_name_taken"))
        elif result != "ok":
            await message.reply_text(t(lang, "tr_need_card"))
        else:
            await _retitle_trainer_topic(context, int(wiz["player_id"]), name)
            await message.reply_text(t(lang, "tr_renamed", name=name))
        await _trainer_show_home(message, lang, telegram_id)
        return

    if wiz and wiz.get("kind") == "archive":
        typed = trainer.normalize_name(user_text)
        if typed.casefold() != (wiz.get("name") or "").casefold():
            trainer.clear_wizard(context.user_data)
            await message.reply_text(t(lang, "tr_archive_mismatch"))
            await _trainer_show_home(message, lang, telegram_id)
            return
        await asyncio.to_thread(
            storage.archive_trainer_card, telegram_id, int(wiz["player_id"])
        )
        trainer.clear_wizard(context.user_data)
        context.user_data.pop(SESSION_KEY, None)
        await message.reply_text(t(lang, "tr_archived", name=wiz.get("name") or ""))
        await _trainer_show_home(message, lang, telegram_id)
        return

    if wiz and wiz.get("kind") == "pick":
        cards = await asyncio.to_thread(storage.list_trainer_cards, telegram_id)
        chosen = None
        for card in cards:
            if card["name"] == user_text:
                chosen = card
                break
        if not chosen:
            await message.reply_text(
                t(lang, "tr_need_card"),
                reply_markup=trainer.pick_keyboard(
                    lang, [card["name"] for card in cards]
                ),
            )
            return
        await asyncio.to_thread(
            storage.set_active_trainer_card, telegram_id, int(chosen["player_id"])
        )
        trainer.clear_wizard(context.user_data)
        _trainer_bind_session(context.user_data, int(chosen["player_id"]))
        await _trainer_show_home(message, lang, telegram_id)
        return

    if is_onboarding_active(context.user_data):
        await _handle_onboarding_text(update, context, lang, user_text)
        return

    if user_text == t(lang, "tr_btn_create"):
        trainer.set_wizard(context.user_data, "await_name", trainer_id=telegram_id)
        await message.reply_text(
            t(lang, "tr_ask_name"),
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton(t(lang, "tr_btn_cancel"))]],
                resize_keyboard=True,
            ),
        )
        return

    if user_text == t(lang, "tr_btn_select"):
        cards = await asyncio.to_thread(storage.list_trainer_cards, telegram_id)
        if not cards:
            await message.reply_text(
                t(lang, "tr_no_students"),
                reply_markup=await _trainer_keyboard(telegram_id, lang),
            )
            return
        trainer.set_wizard(context.user_data, "pick", trainer_id=telegram_id)
        await message.reply_text(
            t(lang, "tr_btn_select"),
            reply_markup=trainer.pick_keyboard(lang, [card["name"] for card in cards]),
        )
        return

    if is_edit_profile_text(user_text):
        card = await asyncio.to_thread(storage.get_active_trainer_card, telegram_id)
        if not card:
            await message.reply_text(t(lang, "tr_need_card"))
            await _trainer_show_home(message, lang, telegram_id)
            return
        trainer.set_wizard(
            context.user_data,
            "edit",
            trainer_id=telegram_id,
            player_id=int(card["player_id"]),
            name=card["name"],
        )
        start_onboarding_state(context.user_data)
        await _send_onboarding_question(
            message,
            lang,
            "level",
            intro=t(lang, "profile_edit_prompt"),
            user_data=context.user_data,
        )
        return

    if user_text == t(lang, "tr_btn_rename"):
        card = await asyncio.to_thread(storage.get_active_trainer_card, telegram_id)
        if not card:
            await message.reply_text(t(lang, "tr_need_card"))
            await _trainer_show_home(message, lang, telegram_id)
            return
        trainer.set_wizard(
            context.user_data,
            "rename",
            trainer_id=telegram_id,
            player_id=int(card["player_id"]),
            name=card["name"],
        )
        await message.reply_text(
            t(lang, "tr_ask_rename", name=card["name"]),
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton(t(lang, "tr_btn_cancel"))]],
                resize_keyboard=True,
            ),
        )
        return

    if user_text == t(lang, "tr_btn_archive"):
        card = await asyncio.to_thread(storage.get_active_trainer_card, telegram_id)
        if not card:
            await message.reply_text(t(lang, "tr_need_card"))
            await _trainer_show_home(message, lang, telegram_id)
            return
        trainer.set_wizard(
            context.user_data,
            "archive",
            trainer_id=telegram_id,
            player_id=int(card["player_id"]),
            name=card["name"],
        )
        await message.reply_text(
            t(lang, "tr_ask_archive", name=card["name"]),
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton(t(lang, "tr_btn_cancel"))]],
                resize_keyboard=True,
            ),
        )
        return

    if is_intake_active(context.user_data):
        pending = context.user_data.get("pending_video") or {}
        subject = pending.get("subject_player_id")
        if subject:
            context.user_data["user_id"] = int(subject)
        await _handle_video_intake_text(update, context, lang, language_code, user_text)
        return

    card = await asyncio.to_thread(storage.get_active_trainer_card, telegram_id)
    if not card:
        await _trainer_show_home(message, lang, telegram_id)
        return
    _trainer_bind_session(context.user_data, int(card["player_id"]))
    session = _get_session(context.user_data)
    if not session.get("analysis"):
        await message.reply_text(
            t(lang, "no_active_analysis"),
            reply_markup=await _trainer_keyboard(telegram_id, lang),
        )
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
        logger.exception("Ошибка диалога тренера user_id=%s", card["player_id"])
        await message.reply_text(
            format_analysis_error(exc, lang),
            parse_mode=ParseMode.MARKDOWN,
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

    await _touch_user(update, context)

    if await _handle_survey_other_text(update, context, user_text):
        return
    if await _handle_coach_forum_message(update, context):
        return
    if await _consume_broadcast_text(update, context):
        return
    if await _handle_player_coach_message(update, context, user_text):
        return

    if message.from_user and await asyncio.to_thread(
        storage.is_trainer, message.from_user.id
    ):
        await _trainer_on_text(update, context, lang, language_code, user_text)
        return

    menu_handler = _MENU_HANDLERS.get(user_text)
    if menu_handler:
        await menu_handler(update, context)
        return

    chosen_lang = language_choice(user_text)
    if chosen_lang:
        await _apply_language(update, context, chosen_lang)
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

    if _new_confirm_pending(context.user_data):
        if await _followup_scope_on(context, context.user_data):
            await _confirm_new_analysis(message, context, lang, user_text)
            return
        _clear_new_confirm_pending(context.user_data)

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
    if await _handle_coach_forum_message(update, context):
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
    if await asyncio.to_thread(storage.is_trainer, user_id):
        card = await asyncio.to_thread(storage.get_active_trainer_card, user_id)
        if not card:
            await _trainer_show_home(message, lang, user_id)
            return
        user_id = int(card["player_id"])
    context.user_data["user_id"] = user_id
    await _touch_user(update, context)
    context.user_data["user_id"] = user_id
    plan = await asyncio.to_thread(services.get_plan, user_id)
    if not billing.MONETIZATION_ENABLED:
        await message.reply_text(
            t(
                lang,
                "plan_status_open",
                used=plan.analyses_used,
                max_sec=plan.max_video_seconds,
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        return
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
    if await asyncio.to_thread(storage.is_trainer, user_id):
        card = await asyncio.to_thread(storage.get_active_trainer_card, user_id)
        if not card:
            await _trainer_show_home(message, lang, user_id)
            return
        user_id = int(card["player_id"])
    context.user_data["user_id"] = user_id
    await _touch_user(update, context)
    context.user_data["user_id"] = user_id
    rows = await asyncio.to_thread(storage.list_player_foci, user_id)
    if not rows:
        await message.reply_text(t(lang, "focus_empty"))
        return
    order = {key: idx for idx, key in enumerate(STROKE_KEYS)}
    rows = sorted(rows, key=lambda row: order.get(row.get("stroke") or "", 99))
    items = []
    for row in rows:
        items.append(
            t(
                lang,
                "focus_status_item",
                focus=row["focus"],
                stroke=intake_value_label(lang, "stroke", row.get("stroke")),
                expires=row.get("expires_at") or "—",
            )
        )
    await message.reply_text(
        t(lang, "focus_status", items="\n".join(items)),
        parse_mode=ParseMode.MARKDOWN,
    )


async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return
    lang = _lang_from_update(update, context)
    user_id = message.from_user.id
    if await asyncio.to_thread(storage.is_trainer, user_id):
        card = await asyncio.to_thread(storage.get_active_trainer_card, user_id)
        if not card:
            await _trainer_show_home(message, lang, user_id)
            return
        user_id = int(card["player_id"])
    context.user_data["user_id"] = user_id
    await _touch_user(update, context)
    context.user_data["user_id"] = user_id
    rows = await asyncio.to_thread(services.progress_scores, user_id, 90)
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
    if not billing.MONETIZATION_ENABLED:
        await context.bot.send_message(
            chat_id=chat.id, text=t(lang, "monetization_off")
        )
        return
    player_id = await _touch_user(update, context)
    if player_id is None:
        return
    payload = billing.stars_payload(player_id)
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
    await _log_event(player_id, EVENT_INVOICE_SENT)


async def handle_pay_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    lang = _lang_from_update(update, context)
    user_id = query.from_user.id
    context.user_data["user_id"] = user_id
    await _touch_user(update, context)
    await send_pro_invoice(update, context, lang, user_id)


async def handle_precheckout(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.pre_checkout_query
    if not query:
        return
    if not billing.MONETIZATION_ENABLED:
        await query.answer(ok=False, error_message="Payments are temporarily disabled")
        return
    payload_player_id = billing.parse_stars_payload(query.invoice_payload or "")
    resolved = identity.player_id_for_telegram(query.from_user.id)
    if payload_player_id is None or resolved is None or payload_player_id != resolved:
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
    player_id = await _touch_user(update, context)
    if player_id is None:
        return
    payment = message.successful_payment
    payment_id = (
        payment.telegram_payment_charge_id or payment.provider_payment_charge_id
    )
    await asyncio.to_thread(
        services.grant_pro,
        player_id,
        1,
        billing.PROVIDER_STARS,
        payment_id,
    )
    await _log_event(player_id, EVENT_PAYMENT_SUCCESS, payment_id or "")
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
        logger.warning(
            "ADMIN_USER_IDS не задан — команды /stats, /grant и /broadcast недоступны"
        )
    if not settings.coach_forum_chat_id:
        logger.warning(
            "COACH_FORUM_CHAT_ID не задан — заявки в кабинет тренера не попадут"
        )
    else:
        logger.info(
            "Coach cabinet: forum_chat_id=%s coach_ids=%s",
            settings.coach_forum_chat_id,
            settings.coach_user_ids or settings.admin_user_ids,
        )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("link", link_command))
    app.add_handler(CommandHandler("plan", plan_command))
    app.add_handler(CommandHandler("focus", focus_command))
    app.add_handler(CommandHandler("progress", progress_command))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CommandHandler("reset", new_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("daly", daly_command))
    app.add_handler(CommandHandler("grant", grant_command))
    app.add_handler(CommandHandler("set_trainer", set_trainer_command))
    app.add_handler(CommandHandler("followup", followup_scope_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CallbackQueryHandler(handle_broadcast_callback, pattern=r"^bc:"))
    app.add_handler(CallbackQueryHandler(handle_feedback, pattern=r"^fb:"))
    app.add_handler(CallbackQueryHandler(handle_practice, pattern=r"^p:"))
    app.add_handler(CallbackQueryHandler(handle_review_callback, pattern=r"^rv"))
    app.add_handler(CallbackQueryHandler(handle_coach_eval_callback, pattern=r"^ce:"))
    app.add_handler(CallbackQueryHandler(handle_survey, pattern=r"^sv:"))
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
