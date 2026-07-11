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
            "next_video": "Следующее видео",
        },
        "en": {
            "summary": "Brief summary",
            "top3": "Top 3 training priorities",
            "next_video": "Next video",
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
        "btn_help": "📋 Справка",
        "btn_new": "🔄 Новый разбор",
        "btn_history": "📊 Мои разборы",
        "cmd_start": "Начать работу",
        "cmd_help": "Справка по использованию",
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
        "followup_hint_next": (
            "📹 *Следующее видео:*\n{next_video}\n\n"
            "💬 Можете задавать уточняющие вопросы текстом."
        ),
        "feedback_prompt": "Разбор был полезен?",
        "feedback_useful": "👍 Полезно",
        "feedback_not_useful": "👎 Не помогло",
        "feedback_actionable": "✅ Понятно, что делать на тренировке",
        "feedback_thanks": "Спасибо за отзыв — это помогает улучшить разборы.",
        "vi_got_video": (
            "📹 Видео получил. Два коротких вопроса — так разбор будет точнее."
        ),
        "vi_question_stroke": "На какой удар обращать внимание в первую очередь?",
        "vi_question_look": "На что смотреть в первую очередь?",
        "vi_skip": "⏭ Пропустить — разбери как есть",
        "vi_invalid": "Выберите вариант на кнопках или нажмите «Пропустить».",
        "vi_in_progress": (
            "Сначала ответьте на вопрос выше — или нажмите «Пропустить»."
        ),
        "vi_opt_stroke_forehand": "🎾 Форхенд",
        "vi_opt_stroke_backhand": "🤚 Бэкхенд",
        "vi_opt_stroke_serve": "🚀 Подача",
        "vi_opt_stroke_volley": "🏓 У сетки / волей",
        "vi_opt_stroke_footwork": "👟 Ноги / передвижение",
        "vi_opt_stroke_rally": "🔄 Серия ударов / розыгрыш",
        "vi_opt_look_technique": "Техника удара",
        "vi_opt_look_footwork": "Ноги и баланс",
        "vi_opt_look_contact": "Точка удара / тайминг",
        "vi_opt_look_general": "Общий разбор",
        "vi_val_stroke_forehand": "форхенд",
        "vi_val_stroke_backhand": "бэкхенд",
        "vi_val_stroke_serve": "подача",
        "vi_val_stroke_volley": "волей / игра у сетки",
        "vi_val_stroke_footwork": "ноги и передвижение",
        "vi_val_stroke_rally": "серия ударов / розыгрыш",
        "vi_val_look_technique": "техника удара",
        "vi_val_look_footwork": "ноги и баланс",
        "vi_val_look_contact": "точка удара и тайминг",
        "vi_val_look_general": "общий разбор",
        "reminder_with_task": (
            "🎾 Давно не виделись!\n\n"
            "Домашнее задание было:\n{task}\n\n"
            "Снимите 10–20 сек сбоку или сзади и пришлите видео — посмотрим прогресс."
        ),
        "reminder_generic": (
            "🎾 Давно не виделись!\n\n"
            "Снимите 10–20 сек своего удара (сбоку или сзади) и пришлите — "
            "разберём, что изменилось."
        ),
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
        "cmd_profile": "Мой профиль",
        "ob_intro": (
            "👋 *Давайте познакомимся — это займёт 30 секунд*\n\n"
            "Ответы помогут ИИ точнее разбирать вашу технику: подстроит глубину "
            "критики, приоритеты и упражнения под ваш уровень.\n\n"
            "Вопрос 1 из 4:"
        ),
        "ob_question_level": "Какой у вас уровень игры?",
        "ob_question_focus": "Что хотите улучшить в первую очередь?",
        "ob_question_hand": "Какая у вас доминирующая рука?",
        "ob_question_injuries": (
            "Есть травмы или дискомфорт при игре?\n"
            "Опишите текстом или нажмите «Нет»."
        ),
        "ob_skip": "⏭ Пропустить настройку",
        "ob_skip_warning": (
            "Хорошо, настройку пропустили.\n\n"
            "⚠️ Без профиля разбор будет более общим — ИИ не знает ваш уровень "
            "и цели. Вы всегда можете заполнить профиль через /profile.\n\n"
            "👇 Отправьте видео 10–30 сек, чтобы начать."
        ),
        "ob_complete": (
            "✅ *Профиль сохранён!*\n\n"
            "Теперь разборы будут точнее — с учётом вашего уровня и целей.\n\n"
            "👇 *Отправьте первое видео* (10–30 сек, лучше сбоку или сзади)."
        ),
        "ob_injuries_none": "Нет",
        "ob_edit_profile": "✏️ Изменить профиль",
        "ob_in_progress_video": (
            "Сначала завершите настройку профиля — ответьте на вопрос выше "
            "или нажмите «Пропустить настройку»."
        ),
        "ob_invalid_answer": "Выберите вариант на кнопках или нажмите «Пропустить настройку».",
        "profile_not_set": (
            "Профиль ещё не настроен.\n\n"
            "Нажмите «Изменить профиль», чтобы пройти короткую настройку."
        ),
        "profile_skipped": (
            "Профиль не заполнен (настройка была пропущена).\n\n"
            "Разборы идут в общем режиме. Нажмите «Изменить профиль», "
            "чтобы сделать их точнее."
        ),
        "profile_view": (
            "👤 *Ваш профиль*\n\n"
            "• Уровень: {level}\n"
            "• Фокус: {focus}\n"
            "• Рука: {hand}\n"
            "• Травмы/ограничения: {injuries}\n"
            "• Обновлён: {updated_at}\n\n"
            "Нажмите «Изменить профиль», чтобы обновить данные."
        ),
        "profile_edit_prompt": "Давайте обновим профиль. Вопрос 1 из 4:",
        "ob_opt_level_beginner": "🌱 Начинающий",
        "ob_opt_level_recreational": "🎾 Любитель",
        "ob_opt_level_advanced": "💪 Продвинутый",
        "ob_opt_level_competitive": "🏆 Играю турниры",
        "ob_opt_focus_strokes": "Удары",
        "ob_opt_focus_serve": "Подача",
        "ob_opt_focus_footwork": "Ноги и передвижение",
        "ob_opt_focus_all": "Всё понемногу",
        "ob_opt_hand_right": "Правая",
        "ob_opt_hand_left": "Левая",
        "ob_val_level_beginner": "Начинающий",
        "ob_val_level_recreational": "Любитель",
        "ob_val_level_advanced": "Продвинутый",
        "ob_val_level_competitive": "Соревнующийся",
        "ob_val_focus_strokes": "Удары",
        "ob_val_focus_serve": "Подача",
        "ob_val_focus_footwork": "Ноги и передвижение",
        "ob_val_focus_all": "Всё понемногу",
        "ob_val_hand_right": "Правая",
        "ob_val_hand_left": "Левая",
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
        "btn_help": "📋 Help",
        "btn_new": "🔄 New analysis",
        "btn_history": "📊 My analyses",
        "cmd_start": "Get started",
        "cmd_help": "Usage help",
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
        "followup_hint_next": (
            "📹 *Next video:*\n{next_video}\n\n"
            "💬 You can ask follow-up questions in text."
        ),
        "reminder_with_task": (
            "🎾 Long time no see!\n\n"
            "Your homework was:\n{task}\n\n"
            "Film 10–20 sec from the side or back and send the video — let's check progress."
        ),
        "reminder_generic": (
            "🎾 Long time no see!\n\n"
            "Film 10–20 sec of your stroke (side or back angle) and send it — "
            "we'll see what changed."
        ),
        "feedback_prompt": "Was this analysis useful?",
        "feedback_useful": "👍 Useful",
        "feedback_not_useful": "👎 Not helpful",
        "feedback_actionable": "✅ I know what to do at practice",
        "feedback_thanks": "Thanks for the feedback — it helps improve the analyses.",
        "vi_got_video": (
            "📹 Got the video. Two quick questions — so the analysis is more precise."
        ),
        "vi_question_stroke": "Which stroke should I focus on first?",
        "vi_question_look": "What should I look at first?",
        "vi_skip": "⏭ Skip — analyze as-is",
        "vi_invalid": "Choose a button option or tap Skip.",
        "vi_in_progress": ("Please answer the question above — or tap Skip."),
        "vi_opt_stroke_forehand": "🎾 Forehand",
        "vi_opt_stroke_backhand": "🤚 Backhand",
        "vi_opt_stroke_serve": "🚀 Serve",
        "vi_opt_stroke_volley": "🏓 Net / volley",
        "vi_opt_stroke_footwork": "👟 Footwork / movement",
        "vi_opt_stroke_rally": "🔄 Rally / point",
        "vi_opt_look_technique": "Stroke technique",
        "vi_opt_look_footwork": "Feet and balance",
        "vi_opt_look_contact": "Contact point / timing",
        "vi_opt_look_general": "General review",
        "vi_val_stroke_forehand": "forehand",
        "vi_val_stroke_backhand": "backhand",
        "vi_val_stroke_serve": "serve",
        "vi_val_stroke_volley": "volley / net play",
        "vi_val_stroke_footwork": "footwork and movement",
        "vi_val_stroke_rally": "rally / point",
        "vi_val_look_technique": "stroke technique",
        "vi_val_look_footwork": "feet and balance",
        "vi_val_look_contact": "contact point and timing",
        "vi_val_look_general": "general review",
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
        "cmd_profile": "My profile",
        "ob_intro": (
            "👋 *Let's get acquainted — takes 30 seconds*\n\n"
            "Your answers help the AI analyze your technique more accurately: "
            "depth of critique, priorities, and drills tailored to your level.\n\n"
            "Question 1 of 4:"
        ),
        "ob_question_level": "What's your skill level?",
        "ob_question_focus": "What do you want to improve first?",
        "ob_question_hand": "What's your dominant hand?",
        "ob_question_injuries": (
            "Any injuries or discomfort while playing?\n" "Describe in text or tap No."
        ),
        "ob_skip": "⏭ Skip setup",
        "ob_skip_warning": (
            "OK, setup skipped.\n\n"
            "⚠️ Without a profile, analysis will be more generic — the AI doesn't "
            "know your level or goals. You can always fill your profile via /profile.\n\n"
            "👇 Send a 10–30 sec video to get started."
        ),
        "ob_complete": (
            "✅ *Profile saved!*\n\n"
            "Analyses will now be more accurate — tailored to your level and goals.\n\n"
            "👇 *Send your first video* (10–30 sec, side or rear angle works best)."
        ),
        "ob_injuries_none": "No",
        "ob_edit_profile": "✏️ Edit profile",
        "ob_in_progress_video": (
            "Please finish profile setup first — answer the question above "
            "or tap Skip setup."
        ),
        "ob_invalid_answer": "Pick an option from the buttons or tap Skip setup.",
        "profile_not_set": (
            "Profile not set up yet.\n\n" "Tap Edit profile to complete a short setup."
        ),
        "profile_skipped": (
            "Profile not filled in (setup was skipped).\n\n"
            "Analyses run in generic mode. Tap Edit profile to make them more accurate."
        ),
        "profile_view": (
            "👤 *Your profile*\n\n"
            "• Level: {level}\n"
            "• Focus: {focus}\n"
            "• Hand: {hand}\n"
            "• Injuries/limitations: {injuries}\n"
            "• Updated: {updated_at}\n\n"
            "Tap Edit profile to update."
        ),
        "profile_edit_prompt": "Let's update your profile. Question 1 of 4:",
        "ob_opt_level_beginner": "🌱 Beginner",
        "ob_opt_level_recreational": "🎾 Recreational",
        "ob_opt_level_advanced": "💪 Advanced",
        "ob_opt_level_competitive": "🏆 Competitive",
        "ob_opt_focus_strokes": "Strokes",
        "ob_opt_focus_serve": "Serve",
        "ob_opt_focus_footwork": "Footwork",
        "ob_opt_focus_all": "A bit of everything",
        "ob_opt_hand_right": "Right",
        "ob_opt_hand_left": "Left",
        "ob_val_level_beginner": "Beginner",
        "ob_val_level_recreational": "Recreational",
        "ob_val_level_advanced": "Advanced",
        "ob_val_level_competitive": "Competitive",
        "ob_val_focus_strokes": "Strokes",
        "ob_val_focus_serve": "Serve",
        "ob_val_focus_footwork": "Footwork",
        "ob_val_focus_all": "A bit of everything",
        "ob_val_hand_right": "Right",
        "ob_val_hand_left": "Left",
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
