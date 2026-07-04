"""Локализация UI и определение языка ответа модели."""

from typing import Any, Optional

LANG_KEY = "lang"
DEFAULT_LANG = "en"
UI_LANGS = ("ru", "en")

_LANGUAGE_NAMES = {
    "ru": "Russian",
    "en": "English",
    "uk": "Ukrainian",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "pl": "Polish",
    "tr": "Turkish",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "he": "Hebrew",
    "nl": "Dutch",
    "sv": "Swedish",
    "cs": "Czech",
    "ro": "Romanian",
    "hu": "Hungarian",
    "fi": "Finnish",
    "da": "Danish",
    "no": "Norwegian",
    "id": "Indonesian",
    "vi": "Vietnamese",
    "th": "Thai",
    "hi": "Hindi",
    "bn": "Bengali",
    "fa": "Persian",
    "el": "Greek",
    "bg": "Bulgarian",
    "sr": "Serbian",
    "hr": "Croatian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "et": "Estonian",
    "ka": "Georgian",
    "az": "Azerbaijani",
    "kk": "Kazakh",
    "uz": "Uzbek",
}


def normalize_language_code(language_code: Optional[str]) -> str:
    if not language_code:
        return DEFAULT_LANG
    return language_code.lower().split("-")[0]


def resolve_ui_lang(language_code: Optional[str]) -> str:
    """Язык кнопок и системных сообщений бота (ru или en)."""
    if normalize_language_code(language_code) == "ru":
        return "ru"
    return DEFAULT_LANG


def language_name_for_model(language_code: str) -> str:
    base = normalize_language_code(language_code)
    return _LANGUAGE_NAMES.get(
        base,
        f"the language with ISO 639-1 code '{base}'",
    )


def language_instruction(language_code: str) -> str:
    name = language_name_for_model(language_code)
    return (
        f"Write your entire response in {name}. "
        "All section headers, labels, and body text must be in that language."
    )


def report_section_headers(language_code: str) -> dict[str, str]:
    base = normalize_language_code(language_code)
    headers = {
        "ru": {
            "summary": "Краткое резюме",
            "top3": "Топ-3 приоритета для тренировки",
        },
        "en": {
            "summary": "Brief summary",
            "top3": "Top 3 training priorities",
        },
    }
    return headers.get(base, headers["en"])


def t(lang: str, key: str, **kwargs: Any) -> str:
    ui_lang = lang if lang in UI_LANGS else DEFAULT_LANG
    template = _MESSAGES[ui_lang][key]
    return template.format(**kwargs) if kwargs else template


_MESSAGES: dict[str, dict[str, str]] = {
    "ru": {
        "welcome": (
            "🎾 *Добро пожаловать в RallyAI!*\n\n"
            "Я разбираю вашу технику тенниса по короткому видео — как тренер после просмотра "
            "записи с корта.\n\n"
            "*Что вы получите за ~1 минуту:*\n"
            "• разбор ударов, ног и баланса\n"
            "• ошибки по критичности 🔴🟠🟡\n"
            "• топ-3 приоритета на тренировку\n\n"
            "*Как начать:* отправьте видео 10–30 сек (сбоку или сзади — идеально). "
            "Можно добавить подпись: «болит локоть», «это форхенд».\n\n"
            "После разбора задавайте вопросы текстом — я помню контекст.\n\n"
            "👇 *Отправьте первое видео прямо сейчас*"
        ),
        "bot_short_description": (
            "🎾 10–30 сек видео → разбор техники, ошибок и упражнений от ИИ-тренера. "
            "Нажмите «Старт»."
        ),
        "bot_description": (
            "🎾 RallyAI — ИИ-тренер по теннису\n\n"
            "Снимите 10–30 секунд своей игры (лучше сбоку или сзади) и отправьте сюда. "
            "Через минуту получите разбор:\n"
            "• техника ударов и работа ног\n"
            "• главные ошибки по критичности\n"
            "• 3 приоритета на тренировку\n\n"
            "После разбора можно задавать уточняющие вопросы — бот помнит ваш последний "
            "разбор.\n\n"
            "👇 Нажмите «Старт», чтобы начать"
        ),
        "help": (
            "📋 *Справка*\n\n"
            "• Принимаются видео до 20 МБ\n"
            "• Оптимальная длительность: 10–30 секунд\n"
            "• Лучшие ракурсы: сбоку, сзади-сбоку, иногда сверху\n"
            "• На видео должен быть виден игрок и его удары/движение\n"
            "• К видео можно добавить подпись: «это форхенд сверху», «болит локоть» и т.п.\n\n"
            "После разбора пишите вопросы обычным сообщением — бот ответит в контексте "
            "последнего видео. Новое видео автоматически начинает новый диалог.\n\n"
            "/new — сбросить текущий диалог без отправки видео"
        ),
        "about": (
            "ℹ️ *О RallyAI*\n\n"
            "Бот использует Google Gemini для анализа видео. "
            "ИИ оценивает технику ударов, передвижение и баланс, "
            "выделяет ошибки по критичности и предлагает упражнения.\n\n"
            "⚠️ Это не замена живого тренера, а вспомогательный инструмент "
            "для самоанализа и подготовки к тренировке."
        ),
        "btn_help": "📋 Справка",
        "btn_about": "ℹ️ О сервисе",
        "btn_new": "🔄 Новый разбор",
        "btn_history": "📊 Мои разборы",
        "cmd_start": "Начать работу",
        "cmd_help": "Справка по использованию",
        "cmd_about": "О сервисе",
        "cmd_new": "Новый разбор",
        "cmd_history": "Мои прошлые разборы",
        "new_reset": "Диалог сброшен. Отправьте новое видео для разбора.",
        "history_empty": (
            "У вас пока нет сохранённых разборов. Отправьте видео — и я его запомню."
        ),
        "history_header": "📊 *Ваши разборы* (всего {count})\n",
        "history_priorities": "_Приоритеты:_ {top3}",
        "video_too_large": "Видео слишком большое. Максимум — {max_mb} МБ.",
        "video_unsupported": (
            "Формат видео не поддерживается. Отправьте MP4, MOV или WebM."
        ),
        "status_analyzing": (
            "⏳ Видео получено. Анализирую технику — это может занять до минуты..."
        ),
        "status_analyzing_comment": (
            "⏳ Видео и комментарий получены. Анализирую — это может занять до минуты..."
        ),
        "video_not_found": "Видео не найдено. Отправьте его заново.",
        "video_not_found_retry": "Видео не найдено — отправьте его заново.",
        "followup_hint": "💬 Можете задавать уточняющие вопросы текстом.",
        "retry_status": "⏳ Повторяю разбор — это может занять до минуты...",
        "retry_button": "🔄 Повторить разбор",
        "no_active_analysis": (
            "Сначала отправьте видео для разбора — после этого можно задавать "
            "вопросы и просить разъяснения. К видео можно добавить подпись с контекстом."
        ),
        "context_lost": (
            "Контекст разбора потерян (возможно, бот перезапускался). "
            "Отправьте видео заново — и кнопки снова заработают."
        ),
        "quick_question_failed": (
            "⚠️ Не удалось получить ответ от ИИ. Попробуйте ещё раз "
            "или задайте вопрос текстом."
        ),
        "unsupported": (
            "Отправьте видео с теннисистом (10–30 сек) или задайте текстовый вопрос "
            "после разбора. Документы и фото пока не поддерживаются."
        ),
        "no_session_internal": "Нет активного разбора. Отправьте видео.",
        "chat_ack": "Понял. Готов ответить на вопросы и уточнения по этому разбору.",
        "error_quota": (
            "⚠️ *Исчерпана квота Gemini API*\n\n"
            "Бесплатный лимит запросов закончился или для вашего ключа квота = 0.\n\n"
            "Что сделать:\n"
            "1. Проверьте лимиты: https://ai.dev/rate-limit\n"
            "2. Создайте новый ключ на https://aistudio.google.com/apikey\n"
            "   (должен начинаться с `AIzaSy...`)\n"
            "3. Подождите до сброса дневного лимита\n"
            "4. Или подключите платный тариф в Google AI Studio"
        ),
        "error_overloaded": (
            "⚠️ *Gemini сейчас перегружен*\n\n"
            "Это временно: на стороне Google всплеск нагрузки на модель. "
            "С вашим видео и ключом всё в порядке.\n\n"
            "Отправьте видео ещё раз через минуту."
        ),
        "error_internal": (
            "⚠️ *Внутренняя ошибка Gemini*\n\n"
            "Временный сбой на стороне Google. Отправьте видео ещё раз через минуту."
        ),
        "error_region": (
            "⚠️ *Gemini недоступен в вашем регионе*\n\n"
            "Запустите бота через VPN или на сервере за рубежом (VPS в EU/US)."
        ),
        "error_api_key": (
            "⚠️ *Неверный API-ключ Gemini*\n\n"
            "Создайте ключ на https://aistudio.google.com/apikey "
            "и вставьте его в файл `.env` как `GEMINI_API_KEY`."
        ),
        "error_timeout": (
            "⏱ Не успел обработать видео вовремя. "
            "Попробуйте короче ролик или повторите позже."
        ),
        "error_generic": (
            "❌ Не удалось проанализировать видео.\n\n"
            "Попробуйте ещё раз или отправьте другой ракурс. "
            "Если ошибка повторяется — проверьте ключ Gemini в `.env`."
        ),
    },
    "en": {
        "welcome": (
            "🎾 *Welcome to RallyAI!*\n\n"
            "I break down your tennis technique from a short video — like a coach "
            "reviewing court footage.\n\n"
            "*What you get in ~1 minute:*\n"
            "• stroke, footwork, and balance analysis\n"
            "• mistakes ranked by severity 🔴🟠🟡\n"
            "• top 3 training priorities\n\n"
            "*To start:* send a 10–30 sec video (side or rear angle works best). "
            'Add a caption if you like: "elbow hurts", "this is my forehand".\n\n'
            "After the analysis, ask follow-up questions — I remember the context.\n\n"
            "👇 *Send your first video now*"
        ),
        "bot_short_description": (
            "🎾 10–30 sec video → AI coaching on technique, mistakes & drills. Tap Start."
        ),
        "bot_description": (
            "🎾 RallyAI — AI tennis coach\n\n"
            "Record 10–30 seconds of your game (side or rear angle works best) and send "
            "it here. In about a minute you'll get:\n"
            "• stroke technique and footwork breakdown\n"
            "• main mistakes ranked by severity\n"
            "• 3 training priorities\n\n"
            "After the analysis, ask follow-up questions — the bot remembers your last "
            "session.\n\n"
            "👇 Tap Start to begin"
        ),
        "help": (
            "📋 *Help*\n\n"
            "• Videos up to 20 MB are accepted\n"
            "• Optimal length: 10–30 seconds\n"
            "• Best angles: side, rear-side, sometimes overhead\n"
            "• The player and their strokes/movement must be visible\n"
            '• You can add a caption: "overhead forehand", "elbow hurts", etc.\n\n'
            "After the analysis, send text questions — the bot replies in context "
            "of the last video. A new video starts a new dialog automatically.\n\n"
            "/new — reset the current dialog without sending a video"
        ),
        "about": (
            "ℹ️ *About RallyAI*\n\n"
            "The bot uses Google Gemini to analyze video. "
            "The AI evaluates stroke technique, movement, and balance, "
            "ranks issues by severity, and suggests drills.\n\n"
            "⚠️ This is not a replacement for a live coach — "
            "it's a tool for self-review and training prep."
        ),
        "btn_help": "📋 Help",
        "btn_about": "ℹ️ About",
        "btn_new": "🔄 New analysis",
        "btn_history": "📊 My analyses",
        "cmd_start": "Get started",
        "cmd_help": "Usage help",
        "cmd_about": "About the service",
        "cmd_new": "New analysis",
        "cmd_history": "My past analyses",
        "new_reset": "Dialog reset. Send a new video for analysis.",
        "history_empty": (
            "You don't have any saved analyses yet. Send a video — I'll remember it."
        ),
        "history_header": "📊 *Your analyses* ({count} total)\n",
        "history_priorities": "_Priorities:_ {top3}",
        "video_too_large": "Video is too large. Maximum size is {max_mb} MB.",
        "video_unsupported": (
            "Video format not supported. Please send MP4, MOV, or WebM."
        ),
        "status_analyzing": (
            "⏳ Video received. Analyzing technique — this may take up to a minute..."
        ),
        "status_analyzing_comment": (
            "⏳ Video and caption received. Analyzing — this may take up to a minute..."
        ),
        "video_not_found": "Video not found. Please send it again.",
        "video_not_found_retry": "Video not found — please send it again.",
        "followup_hint": "💬 You can ask follow-up questions in text.",
        "retry_status": "⏳ Retrying analysis — this may take up to a minute...",
        "retry_button": "🔄 Retry analysis",
        "no_active_analysis": (
            "Send a video for analysis first — then you can ask questions "
            "and request clarifications. You can add a caption with context."
        ),
        "context_lost": (
            "Analysis context was lost (the bot may have restarted). "
            "Send the video again to continue."
        ),
        "quick_question_failed": (
            "⚠️ Could not get a response from the AI. Try again "
            "or ask your question in text."
        ),
        "unsupported": (
            "Send a video of a tennis player (10–30 sec) or ask a text question "
            "after an analysis. Documents and photos are not supported yet."
        ),
        "no_session_internal": "No active analysis. Send a video.",
        "chat_ack": ("Got it. I'm ready to answer questions about this analysis."),
        "error_quota": (
            "⚠️ *Gemini API quota exhausted*\n\n"
            "The free request limit is used up or your key has zero quota.\n\n"
            "What to do:\n"
            "1. Check limits: https://ai.dev/rate-limit\n"
            "2. Create a new key at https://aistudio.google.com/apikey\n"
            "   (should start with `AIzaSy...`)\n"
            "3. Wait for the daily limit to reset\n"
            "4. Or enable a paid plan in Google AI Studio"
        ),
        "error_overloaded": (
            "⚠️ *Gemini is overloaded right now*\n\n"
            "This is temporary — Google is seeing high demand on the model. "
            "Your video and API key are fine.\n\n"
            "Send the video again in about a minute."
        ),
        "error_internal": (
            "⚠️ *Gemini internal error*\n\n"
            "Temporary failure on Google's side. Send the video again in about a minute."
        ),
        "error_region": (
            "⚠️ *Gemini is not available in your region*\n\n"
            "Run the bot via VPN or on a server abroad (VPS in EU/US)."
        ),
        "error_api_key": (
            "⚠️ *Invalid Gemini API key*\n\n"
            "Create a key at https://aistudio.google.com/apikey "
            "and set it in `.env` as `GEMINI_API_KEY`."
        ),
        "error_timeout": (
            "⏱ Could not process the video in time. "
            "Try a shorter clip or retry later."
        ),
        "error_generic": (
            "❌ Could not analyze the video.\n\n"
            "Try again or send a different angle. "
            "If the error persists — check your Gemini key in `.env`."
        ),
    },
}


def sync_user_lang(context_user_data: dict, language_code: Optional[str]) -> str:
    """Сохраняет язык UI в user_data и возвращает его."""
    lang = resolve_ui_lang(language_code)
    context_user_data[LANG_KEY] = lang
    context_user_data["language_code"] = normalize_language_code(language_code)
    return lang


def get_stored_lang(context_user_data: dict) -> str:
    return context_user_data.get(LANG_KEY, DEFAULT_LANG)


def get_stored_language_code(context_user_data: dict) -> str:
    return context_user_data.get("language_code", DEFAULT_LANG)
