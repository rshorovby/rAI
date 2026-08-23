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
            "video": "Что происходит на видео",
            "categories": "Разбор по категориям",
            "top3": "Топ-3 приоритета для тренировки",
            "next_video": "Следующее видео",
            "limitations": "Ограничения анализа",
        },
        "en": {
            "summary": "Brief summary",
            "video": "What happens in the video",
            "categories": "Breakdown by category",
            "top3": "Top 3 training priorities",
            "next_video": "Next video",
            "limitations": "Analysis limitations",
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
            "Разбираем вашу технику по короткому видео вместе с *реальным тренером* "
            "с большим опытом.\n\n"
            "*Как это работает:*\n"
            "1. AI-помощник за ~1 минуту готовит разбор ударов, ног и баланса\n"
            "2. Опытный тренер смотрит то же видео и может добавить свой фидбек\n"
            "3. Вы задаёте вопросы — бот помнит контекст разбора\n\n"
            "*Что получите:*\n"
            "• ошибки по критичности 🔴🟠🟡\n"
            "• топ-3 приоритета на тренировку\n"
            "• комментарии тренера, когда захочет уточнить или усилить разбор\n\n"
            "*Как начать:* видео 10–30 сек (лучше сбоку или сзади). "
            "Можно подпись: «болит локоть», «это форхенд».\n\n"
            "👇 *Отправьте первое видео прямо сейчас*"
        ),
        "bot_short_description": (
            "🎾 Видео 10–30 сек → AI-разбор + фидбек опытного тренера. Нажмите «Старт»."
        ),
        "bot_description": (
            "🎾 RallyAI — разбор техники с AI и реальным тренером\n\n"
            "Снимите 10–30 секунд игры (лучше сбоку или сзади) и отправьте сюда.\n\n"
            "Сначала AI за минуту разберёт удары, ноги и главные ошибки. "
            "Затем опытный тренер может дополнить разбор своим комментарием.\n\n"
            "После разбора можно задавать вопросы — бот помнит контекст.\n\n"
            "👇 Нажмите «Старт», чтобы начать"
        ),
        "help": (
            "📋 *Справка*\n\n"
            "• Принимаются видео до 20 МБ\n"
            "• Оптимальная длительность: 10–30 секунд\n"
            "• Лучшие ракурсы: сбоку, сзади-сбоку, иногда сверху\n"
            "• На видео должен быть виден игрок и его удары/движение\n"
            "• К видео можно добавить подпись: «это форхенд сверху», «болит локоть» и т.п.\n\n"
            "После видео вы сначала получаете AI-разбор, а опытный тренер может "
            "дополнить его отдельным сообщением. Вопросы пишите обычным текстом — "
            "бот отвечает в контексте последнего видео. Новое видео начинает новый диалог.\n\n"
            "/new — сбросить текущий диалог без отправки видео"
        ),
        "btn_help": "📋 Справка",
        "btn_new": "🔄 Новый разбор",
        "btn_history": "📊 Мои разборы",
        "cmd_start": "Начать работу",
        "cmd_help": "Справка по использованию",
        "cmd_plan": "Статус",
        "cmd_progress": "Мой прогресс",
        "cmd_focus": "Фокус недели",
        "cmd_new": "Новый разбор",
        "cmd_history": "Мои прошлые разборы",
        "btn_upgrade_pro": "⭐ Открыть Pro",
        "paywall_text": (
            "🔒 *Лимит разборов исчерпан*\n\n"
            "В этом месяце использовано {used} из {limit}.\n"
            "Pro даёт больше разборов, память прогресса и фокус недели.\n\n"
            "Оплата через Telegram Stars — одним нажатием."
        ),
        "video_too_long": (
            "Видео длиннее {max_sec} сек. Обрежьте ролик и пришлите снова."
        ),
        "plan_status": (
            "📦 *Тариф: {plan}*\n\n"
            "• Разборы в этом месяце: {used}/{limit} (осталось {left})\n"
            "• Сброс квоты: {reset}\n"
            "• Pro действует до: {expires}"
        ),
        "plan_status_open": (
            "🎾 *Открытая бета*\n\n"
            "Сейчас бот бесплатный для всех — набираем базу игроков.\n\n"
            "• Разборов в этом месяце: {used}\n"
            "• Макс. длина видео: {max_sec} сек"
        ),
        "monetization_off": (
            "Сейчас бот в открытой бете — оплата не нужна. Просто отправьте видео."
        ),
        "focus_empty": (
            "Фокус недели ещё не задан. Сделайте разбор — бот выберет главный фокус."
        ),
        "focus_status": (
            "🎯 *Фокус недели*\n\n"
            "{focus}\n\n"
            "Удар: {stroke}\n"
            "До: {expires}\n\n"
            "Снимите следующее видео с этим фокусом — проверим, стало ли лучше."
        ),
        "progress_empty": (
            "Пока мало данных для прогресса. Сделайте 2–3 разбора одного удара."
        ),
        "progress_header": "📈 *Прогресс за 90 дней*",
        "progress_last_focus": "Последний фокус: {focus}",
        "invoice_title": "RallyMind Pro — 1 месяц",
        "invoice_description": (
            "Больше разборов, фокус недели, память прогресса и упражнения."
        ),
        "payment_success": (
            "✅ *Pro активирован!*\n\n"
            "Лимит разборов увеличен. Отправьте видео — продолжим."
        ),
        "subscription_expiring": (
            "⏳ Pro заканчивается {expires}.\n"
            "Продлите подписку, чтобы не потерять лимит разборов."
        ),
        "subscription_expired": (
            "📭 Pro закончился. Вы снова на Free.\n" "Можно продлить — кнопка ниже."
        ),
        "digest_weekly": (
            "📅 *Недельный дайджест*\n\n"
            "Фокус: {focus}\n"
            "Стрик: {streak} нед. подряд\n"
            "Разборов за неделю: {analyses}\n\n"
            "Снимите короткое видео и проверим прогресс."
        ),
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
        "pose_caption": "🦴 Ваша биомеханика на видео (приблизительно)",
        "pose_unavailable": ("🦴 Не удалось наложить скелет — разбор ниже как обычно."),
        "dialog_ready": "✅ *Готово.* Кратко по видео:",
        "dialog_section_empty": "_В отчёте нет этой секции._",
        "dialog_title_video": "📹 *Подробнее про видео*",
        "dialog_title_cats": ("🔎 *Углублённый анализ*\nВыберите категорию:"),
        "dialog_title_top3": "📋 *Советы на тренировку*",
        "dialog_title_prio": "📌 *Совет {n}*",
        "dialog_title_error": ("🔴 *Ошибка {n} из {total}*\n\n{text}"),
        "dialog_title_finish": (
            "✅ *Завершить разбор*\n\n"
            "Можете взять задание на следующее видео или оценить разбор."
        ),
        "dialog_btn_video": "📹 Подробнее про видео",
        "dialog_btn_errors": "🔴 Разбор ошибок",
        "dialog_btn_cats": "🔎 Углублённый анализ",
        "dialog_btn_top3": "📋 Советы на тренировку",
        "dialog_btn_skeleton": "🦴 Показать скелет",
        "dialog_btn_drills": "🏋️ Упражнения",
        "dialog_btn_next": "📹 Что снять дальше",
        "dialog_btn_finish": "✅ Завершить разбор",
        "dialog_btn_enough": "✅ Достаточно",
        "dialog_btn_back": "↩️ К резюме",
        "dialog_btn_ask": "💬 Задать вопрос текстом",
        "dialog_btn_feedback": "⭐ Оценить разбор",
        "dialog_btn_err_deep": "🔍 Углубиться / рекомендация",
        "dialog_btn_err_next": "➡️ Следующая ошибка",
        "dialog_btn_err_done": "✅ Ошибки закончились",
        "dialog_errors_done": (
            "✅ Все приоритетные ошибки разобрали.\n"
            "Можете вернуться к резюме или завершить разбор."
        ),
        "dialog_no_errors": "В отчёте не нашлось приоритетных ошибок.",
        "dialog_skeleton_explain": (
            "🦴 *Что это такое*\n\n"
            "Это *приблизительная* биомеханика: точки суставов поверх вашего видео.\n\n"
            "*Зачем:* увидеть, где тело в момент удара, и сопоставить это с текстом "
            "разбора. Можно сохранить и показать тренеру.\n\n"
            "Это не Hawk-Eye и не меддиагноз — ориентир для глаз."
        ),
        "dialog_skeleton_working": "🦴 Накладываю скелет — до ~30 сек…",
        "dialog_continue": "Куда дальше?",
        "dialog_ask_hint": "💬 Напишите вопрос текстом — я помню этот разбор.",
        "dialog_stale": "Разбор уже закрыт. Отправьте новое видео или /new.",
        "dialog_no_cats": "В отчёте не нашлось разбивки по категориям.",
        "dialog_no_prio": "Этот пункт приоритета не найден.",
        "dialog_drill_soon": (
            "🏋️ Видео-примеры упражнений появятся в следующей версии — "
            "пока держитесь текстовой рекомендации выше."
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
        "survey_no_video_intro": (
            "Привет! 👋\n\n"
            "Заметили, что вы пока не отправили видео для анализа техники. "
            "Нам очень важно, чтобы бот был удобным и полезным. "
            "Поэтому хотим спросить: *что вас останавливает?*\n\n"
            "Это займёт не больше 10 секунд, но поможет нам улучшить сервис.\n\n"
            "Пожалуйста, выберите один или несколько вариантов."
        ),
        "survey_opt_record": "1️⃣ Сложно записать видео на корте",
        "survey_opt_tech": "2️⃣ Технические проблемы при загрузке",
        "survey_opt_forgot": "3️⃣ Забыл(а) / не было времени",
        "survey_opt_doubt": "4️⃣ Сомневаюсь в пользе анализа",
        "survey_opt_howto": "5️⃣ Не уверен(а), как снять видео",
        "survey_opt_shy": "6️⃣ Стесняюсь показывать технику",
        "survey_opt_other": "7️⃣ Другое",
        "survey_btn_done": "✅ Готово",
        "survey_pick_one": "Выберите хотя бы один вариант.",
        "survey_other_prompt": (
            "Напишите, что ещё мешает отправить видео — одним сообщением."
        ),
        "survey_thanks": (
            "Спасибо! 🙏 Ваш ответ поможет сделать бота удобнее.\n\n"
            "Когда будете готовы — пришлите 10–20 сек видео удара сбоку или сзади."
        ),
        "survey_coach_sent": "✅ Опрос отправлен игроку.",
        "survey_coach_failed": "⚠️ Не удалось отправить опрос игроку.",
        "survey_no_onboarding_intro": (
            "Привет! 👋\n\n"
            "Заметили, что вы нажали /start, но не завершили короткий опрос о себе. "
            "Нам важно сделать бот удобным — *что вас остановило?*\n\n"
            "Это займёт не больше 10 секунд.\n\n"
            "Пожалуйста, выберите один или несколько вариантов."
        ),
        "survey_ob_opt_long": "1️⃣ Слишком много вопросов / долго",
        "survey_ob_opt_unclear": "2️⃣ Не понял(а), зачем это нужно",
        "survey_ob_opt_forgot": "3️⃣ Забыл(а) / не было времени",
        "survey_ob_opt_doubt": "4️⃣ Сомневаюсь, что бот будет полезен",
        "survey_ob_opt_tech": "5️⃣ Технические проблемы с ботом",
        "survey_ob_opt_privacy": "6️⃣ Не хочу делиться личной информацией",
        "survey_ob_opt_other": "7️⃣ Другое",
        "survey_no_onboarding_thanks": (
            "Спасибо! 🙏 Ваш ответ поможет нам улучшить бота.\n\n"
            "Когда будете готовы — нажмите /start и пройдите короткий опрос. "
            "Это займёт минуту."
        ),
        "practice_ask": (
            "🎾 *Когда следующая тренировка?*\n\n"
            "Фокус: {focus}\n"
            "Упражнение: {drill}\n\n"
            "Напомню перед занятием, на что смотреть — и спрошу после, получилось ли."
        ),
        "practice_btn_today": "Сегодня вечером",
        "practice_btn_tomorrow": "Завтра",
        "practice_btn_plus2": "Через 2–3 дня",
        "practice_btn_weekend": "В эти выходные",
        "practice_btn_unknown": "Пока не знаю",
        "practice_btn_mute": "Не беспокоить неделю",
        "practice_date_saved": (
            "✅ Записал: тренировка *{date}*.\n"
            "Перед занятием напомню про фокус и упражнение."
        ),
        "practice_date_unknown": (
            "✅ Ок — напишу завтра вечером и спрошу, получилось ли попробовать упражнение."
        ),
        "practice_muted": "👌 Не буду писать неделю. Можно вернуться в любой момент с видео.",
        "practice_pre": (
            "🎾 *Сегодня на корте*\n\n"
            "Фокус: {focus}\n"
            "Упражнение: {drill}\n\n"
            "Не надо идеально — 10–15 повторов достаточно."
        ),
        "practice_btn_pre_ok": "Понял",
        "practice_btn_pre_move": "Тренировка перенесена",
        "practice_pre_ok": "👍 Отлично. Вечером спрошу, как прошло.",
        "practice_post": ("🎾 Получилось попробовать «{drill}» на тренировке?"),
        "practice_btn_post_yes": "Да, почувствовал разницу",
        "practice_btn_post_hard": "Пробовал, пока не легло",
        "practice_btn_post_skip": "Не успел",
        "practice_post_yes": (
            "🔥 Класс. Снимите 10–20 сек того же удара (сбоку или сзади) — "
            "сравним с прошлым разбором.\n\n"
            "{next_video}"
        ),
        "practice_post_hard": (
            "Ок — упростим. На ближайшей тренировке делайте только одну вещь:\n"
            "*{cue}*\n\n"
            "Другое упражнение: {alt_drill}\n\n"
            "Когда будет готово — пришлите короткое видео."
        ),
        "practice_post_skip": ("Ничего страшного. Когда будет следующая тренировка?"),
        "practice_no_plan": "Цепочка уже закрыта. Отправьте новое видео или /new.",
        "review_ack": (
            "🎾 Видео получил.\n\n"
            "Сейчас AI-помощник подготовит разбор — обычно до минуты. "
            "Параллельно видео увидит опытный тренер и сможет добавить свой фидбек."
        ),
        "review_received": (
            "🎾 Видео получил.\n\n"
            "Сейчас AI-помощник подготовит разбор — обычно до минуты. "
            "Параллельно видео увидит опытный тренер и сможет добавить свой фидбек."
        ),
        "review_preparing": ("⏳ Анализирую технику — это может занять до минуты..."),
        "review_forum_failed": (
            "⚠️ Разбор готов, но не удалось отправить его в кабинет тренера. "
            "Мы уже видим ошибку в логах — при необходимости напишите нам."
        ),
        "review_btn_message_coach": "✉️ Написать тренеру",
        "review_message_prompt": ("Напишите сообщение тренеру — перешлю в кабинет."),
        "review_message_sent": "✅ Передал тренеру.",
        "review_no_open_job": "Сначала отправьте видео — после разбора можно писать тренеру.",
        "review_no_topic": "Сначала отправьте видео — после разбора можно писать тренеру.",
        "review_coach_hint": (
            "Опытный тренер может дополнить AI-разбор своим комментарием. "
            "Если хотите что-то уточнить у тренера — кнопка ниже."
        ),
        "review_coach_message": "💬 *Сообщение от тренера:*\n\n{text}",
        "review_coach_media_header": "💬 *Сообщение от тренера:*",
        "review_fallback_banner": (
            "⚠️ *Это предварительный разбор AI:* тренер не успел проверить вручную. "
            "Можно опираться на него на тренировке; при следующем видео тренер "
            "посмотрит приоритетнее."
        ),
        "review_coach_notes_block": "*Замечания тренера:*\n{notes}",
        "review_delivered_coach": "✅ Тренер отправил разбор.",
        "retry_status": "⏳ Повторяю разбор — это может занять до минуты...",
        "retry_button": "🔄 Попробовать ещё раз",
        "retry_simple_button": "⚡ Разобрать проще",
        "retry_simple_status": (
            "⏳ Разбираю на запасной модели — обычно отвечает быстрее..."
        ),
        "analysis_used_simple_model": (
            "ℹ️ Разбор сделан на запасной модели: основная сейчас была перегружена."
        ),
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
            "⏳ Сейчас не получается разобрать видео — ИИ-модели перегружены.\n\n"
            "С вашим роликом всё в порядке: видео уже у тренера, он сможет дать "
            "разбор вручную.\n\n"
            "Можно также нажать «Повторить» чуть позже."
        ),
        "error_internal": (
            "⏳ Временный сбой сервиса анализа. Попробуйте ещё раз через минуту."
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
        "analysis_fallback_status": (
            "⏳ Основная модель не ответила — пробую запасную…"
        ),
        "cmd_profile": "Мой профиль",
        "ob_intro": (
            "👋 *Давайте познакомимся — это займёт 30 секунд*\n\n"
            "Ответы помогут AI и тренеру точнее разобрать вашу технику: "
            "подстроят глубину критики, приоритеты и упражнения под ваш уровень.\n\n"
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
        "ob_reset_profile": "🔄 Начать с нуля",
        "profile_reset_confirm_prompt": (
            "⚠️ *Сбросить профиль и все разборы?*\n\n"
            "Будут удалены:\n"
            "• ваш профиль (уровень, цели, травмы)\n"
            "• история всех прошлых разборов\n"
            "• текущий активный разбор\n\n"
            "После сброса вы пройдёте настройку заново — как при первом входе.\n\n"
            "Подтвердите действие:"
        ),
        "profile_reset_confirm_yes": "✅ Да, сбросить всё",
        "profile_reset_confirm_no": "❌ Отмена",
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
            "«Изменить профиль» — обновить данные.\n"
            "«Начать с нуля» — удалить профиль и историю и пройти настройку заново."
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
            "We review your technique from a short video with a *real coach* "
            "who has years of experience.\n\n"
            "*How it works:*\n"
            "1. An AI assistant prepares a stroke, footwork, and balance review in ~1 minute\n"
            "2. An experienced coach watches the same clip and may add personal feedback\n"
            "3. Ask follow-up questions — the bot remembers your review context\n\n"
            "*What you get:*\n"
            "• mistakes ranked by severity 🔴🟠🟡\n"
            "• top 3 training priorities\n"
            "• coach comments when they want to sharpen or expand the review\n\n"
            "*To start:* send a 10–30 sec video (side or rear angle works best). "
            'Add a caption if you like: "elbow hurts", "this is my forehand".\n\n'
            "👇 *Send your first video now*"
        ),
        "bot_short_description": (
            "🎾 10–30 sec video → AI review + feedback from an experienced coach. Tap Start."
        ),
        "bot_description": (
            "🎾 RallyAI — tennis technique review with AI and a real coach\n\n"
            "Record 10–30 seconds of your game (side or rear angle works best) and send "
            "it here.\n\n"
            "First, AI breaks down strokes, footwork, and key mistakes in about a minute. "
            "Then an experienced coach may add their own comment.\n\n"
            "After the review, ask follow-up questions — the bot remembers the context.\n\n"
            "👇 Tap Start to begin"
        ),
        "help": (
            "📋 *Help*\n\n"
            "• Videos up to 20 MB are accepted\n"
            "• Optimal length: 10–30 seconds\n"
            "• Best angles: side, rear-side, sometimes overhead\n"
            "• The player and their strokes/movement must be visible\n"
            '• You can add a caption: "overhead forehand", "elbow hurts", etc.\n\n'
            "After you send a video you get an AI review first; an experienced coach "
            "may add a separate comment. Send text questions anytime — the bot replies "
            "in context of the last video. A new video starts a new dialog.\n\n"
            "/new — reset the current dialog without sending a video"
        ),
        "btn_help": "📋 Help",
        "btn_new": "🔄 New analysis",
        "btn_history": "📊 My analyses",
        "cmd_start": "Get started",
        "cmd_help": "Usage help",
        "cmd_plan": "Status",
        "cmd_progress": "My progress",
        "cmd_focus": "Weekly focus",
        "cmd_new": "New analysis",
        "cmd_history": "My past analyses",
        "btn_upgrade_pro": "⭐ Unlock Pro",
        "paywall_text": (
            "🔒 *Analysis limit reached*\n\n"
            "This month you used {used} of {limit}.\n"
            "Pro unlocks more analyses, weekly focus, and progress memory.\n\n"
            "Pay with Telegram Stars in one tap."
        ),
        "video_too_long": ("Video is longer than {max_sec}s. Trim it and send again."),
        "plan_status": (
            "📦 *Plan: {plan}*\n\n"
            "• Analyses this month: {used}/{limit} ({left} left)\n"
            "• Quota resets: {reset}\n"
            "• Pro valid until: {expires}"
        ),
        "plan_status_open": (
            "🎾 *Open beta*\n\n"
            "The bot is free for everyone while we grow the player base.\n\n"
            "• Analyses this month: {used}\n"
            "• Max video length: {max_sec}s"
        ),
        "monetization_off": (
            "The bot is in open beta — no payment needed. Just send a video."
        ),
        "focus_empty": ("No weekly focus yet. Send a video — the coach will set one."),
        "focus_status": (
            "🎯 *Weekly focus*\n\n"
            "{focus}\n\n"
            "Stroke: {stroke}\n"
            "Until: {expires}\n\n"
            "Film your next clip with this focus — we'll check if it improved."
        ),
        "progress_empty": (
            "Not enough data yet. Send 2–3 analyses of the same stroke."
        ),
        "progress_header": "📈 *Progress (90 days)*",
        "progress_last_focus": "Latest focus: {focus}",
        "invoice_title": "RallyMind Pro — 1 month",
        "invoice_description": (
            "More analyses, weekly focus, progress memory, and drills."
        ),
        "payment_success": (
            "✅ *Pro activated!*\n\n"
            "Your analysis limit is higher. Send a video to continue."
        ),
        "subscription_expiring": (
            "⏳ Pro ends on {expires}.\n" "Renew to keep your higher analysis limit."
        ),
        "subscription_expired": (
            "📭 Pro ended. You're back on Free.\n" "Renew anytime — button below."
        ),
        "digest_weekly": (
            "📅 *Weekly digest*\n\n"
            "Focus: {focus}\n"
            "Streak: {streak} weeks\n"
            "Analyses this week: {analyses}\n\n"
            "Film a short clip and we'll check your progress."
        ),
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
        "pose_caption": "🦴 Your biomechanics on video (approximate)",
        "pose_unavailable": (
            "🦴 Could not overlay the skeleton — analysis below as usual."
        ),
        "dialog_ready": "✅ *Done.* Brief take on the video:",
        "dialog_section_empty": "_This section is missing from the report._",
        "dialog_title_video": "📹 *More about the video*",
        "dialog_title_cats": "🔎 *Deep dive*\nPick a category:",
        "dialog_title_top3": "📋 *Practice tips*",
        "dialog_title_prio": "📌 *Tip {n}*",
        "dialog_title_error": "🔴 *Error {n} of {total}*\n\n{text}",
        "dialog_title_finish": (
            "✅ *Finish analysis*\n\n" "Get a next-video task or rate this analysis."
        ),
        "dialog_btn_video": "📹 More about the video",
        "dialog_btn_errors": "🔴 Error walkthrough",
        "dialog_btn_cats": "🔎 Deep dive",
        "dialog_btn_top3": "📋 Practice tips",
        "dialog_btn_skeleton": "🦴 Show skeleton",
        "dialog_btn_drills": "🏋️ Drills",
        "dialog_btn_next": "📹 What to film next",
        "dialog_btn_finish": "✅ Finish analysis",
        "dialog_btn_enough": "✅ Enough",
        "dialog_btn_back": "↩️ Back to summary",
        "dialog_btn_ask": "💬 Ask in text",
        "dialog_btn_feedback": "⭐ Rate the analysis",
        "dialog_btn_err_deep": "🔍 Go deeper / tip",
        "dialog_btn_err_next": "➡️ Next error",
        "dialog_btn_err_done": "✅ Errors done",
        "dialog_errors_done": (
            "✅ All priority errors covered.\n"
            "You can go back to the summary or finish."
        ),
        "dialog_no_errors": "No priority errors found in the report.",
        "dialog_skeleton_explain": (
            "🦴 *What this is*\n\n"
            "Approximate biomechanics: joint points overlaid on your video.\n\n"
            "*Why:* see where the body is at contact and match it with the written "
            "analysis. You can save it and show your coach.\n\n"
            "Not Hawk-Eye and not a medical diagnosis — a visual guide."
        ),
        "dialog_skeleton_working": "🦴 Building skeleton overlay — up to ~30 sec…",
        "dialog_continue": "Where next?",
        "dialog_ask_hint": "💬 Type your question — I still have this analysis.",
        "dialog_stale": "This analysis is closed. Send a new video or /new.",
        "dialog_no_cats": "No category breakdown found in the report.",
        "dialog_no_prio": "That priority item was not found.",
        "dialog_drill_soon": (
            "🏋️ Video drill examples will arrive in a later version — "
            "use the written tip above for now."
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
        "survey_no_video_intro": (
            "Hi! 👋\n\n"
            "We noticed you haven't sent a video for technique analysis yet. "
            "We want RallyMind to be useful and easy — "
            "*what's stopping you?*\n\n"
            "This takes less than 10 seconds and helps us improve.\n\n"
            "Please pick one or more options."
        ),
        "survey_opt_record": "1️⃣ Hard to record on court",
        "survey_opt_tech": "2️⃣ Upload issues (format, length)",
        "survey_opt_forgot": "3️⃣ Forgot / no time",
        "survey_opt_doubt": "4️⃣ Doubt the analysis will help",
        "survey_opt_howto": "5️⃣ Not sure how to film",
        "survey_opt_shy": "6️⃣ Shy about showing my technique",
        "survey_opt_other": "7️⃣ Other",
        "survey_btn_done": "✅ Done",
        "survey_pick_one": "Pick at least one option.",
        "survey_other_prompt": "Tell us what else is stopping you — in one message.",
        "survey_thanks": (
            "Thanks! 🙏 Your answer helps us improve.\n\n"
            "When you're ready — send a 10–20 sec side or back view clip."
        ),
        "survey_coach_sent": "✅ Survey sent to the player.",
        "survey_coach_failed": "⚠️ Couldn't send the survey to the player.",
        "survey_no_onboarding_intro": (
            "Hi! 👋\n\n"
            "We noticed you tapped /start but didn't finish the short profile quiz. "
            "We want RallyMind to be easy — *what stopped you?*\n\n"
            "This takes less than 10 seconds.\n\n"
            "Please pick one or more options."
        ),
        "survey_ob_opt_long": "1️⃣ Too many questions / takes too long",
        "survey_ob_opt_unclear": "2️⃣ Didn't understand why it's needed",
        "survey_ob_opt_forgot": "3️⃣ Forgot / no time",
        "survey_ob_opt_doubt": "4️⃣ Doubt the bot will be useful",
        "survey_ob_opt_tech": "5️⃣ Technical issues with the bot",
        "survey_ob_opt_privacy": "6️⃣ Don't want to share personal info",
        "survey_ob_opt_other": "7️⃣ Other",
        "survey_no_onboarding_thanks": (
            "Thanks! 🙏 Your answer helps us improve.\n\n"
            "When you're ready — tap /start and complete the short profile quiz. "
            "It takes about a minute."
        ),
        "practice_ask": (
            "🎾 *When is your next practice?*\n\n"
            "Focus: {focus}\n"
            "Drill: {drill}\n\n"
            "I'll remind you what to work on before practice — and check in after."
        ),
        "practice_btn_today": "Tonight",
        "practice_btn_tomorrow": "Tomorrow",
        "practice_btn_plus2": "In 2–3 days",
        "practice_btn_weekend": "This weekend",
        "practice_btn_unknown": "Not sure yet",
        "practice_btn_mute": "Don't ping for a week",
        "practice_date_saved": (
            "✅ Noted: practice on *{date}*.\n"
            "I'll remind you about the focus and drill beforehand."
        ),
        "practice_date_unknown": (
            "✅ Got it — I'll check in tomorrow evening and ask if you tried the drill."
        ),
        "practice_muted": "👌 I won't message for a week. Send a video anytime to continue.",
        "practice_pre": (
            "🎾 *On court today*\n\n"
            "Focus: {focus}\n"
            "Drill: {drill}\n\n"
            "Don't aim for perfect — 10–15 reps is enough."
        ),
        "practice_btn_pre_ok": "Got it",
        "practice_btn_pre_move": "Practice was moved",
        "practice_pre_ok": "👍 Great. I'll ask how it went this evening.",
        "practice_post": ("🎾 Did you get to try “{drill}” at practice?"),
        "practice_btn_post_yes": "Yes — felt a difference",
        "practice_btn_post_hard": "Tried it, not clicking yet",
        "practice_btn_post_skip": "Didn't have time",
        "practice_post_yes": (
            "🔥 Nice. Film 10–20 sec of the same stroke (side or back) — "
            "we'll compare with the last analysis.\n\n"
            "{next_video}"
        ),
        "practice_post_hard": (
            "OK — simplify. On the next practice do just one thing:\n"
            "*{cue}*\n\n"
            "Alt drill: {alt_drill}\n\n"
            "When ready — send a short video."
        ),
        "practice_post_skip": ("No worries. When is your next practice?"),
        "practice_no_plan": "That chain is closed. Send a new video or /new.",
        "review_ack": (
            "🎾 Got your video.\n\n"
            "The AI assistant will prepare a review — usually within a minute. "
            "At the same time an experienced coach will see the clip and may add feedback."
        ),
        "review_received": (
            "🎾 Got your video.\n\n"
            "The AI assistant will prepare a review — usually within a minute. "
            "At the same time an experienced coach will see the clip and may add feedback."
        ),
        "review_preparing": (
            "⏳ Analyzing technique — this may take up to a minute..."
        ),
        "review_forum_failed": (
            "⚠️ The review is ready, but I couldn't post it to the coach cabinet. "
            "Please contact us if needed."
        ),
        "review_btn_message_coach": "✉️ Message the coach",
        "review_message_prompt": (
            "Write a message for the coach — I'll forward it to the cabinet."
        ),
        "review_message_sent": "✅ Sent to the coach.",
        "review_no_open_job": "Send a video first — then you can message the coach.",
        "review_no_topic": "Send a video first — then you can message the coach.",
        "review_coach_hint": (
            "An experienced coach may add their own comment on the AI review. "
            "To ask the coach something — use the button below."
        ),
        "review_coach_message": "💬 *Message from the coach:*\n\n{text}",
        "review_coach_media_header": "💬 *Message from the coach:*",
        "review_fallback_banner": (
            "⚠️ *This is a preliminary AI review:* a coach didn't check it manually. "
            "You can still use it at practice; the next video will be prioritized."
        ),
        "review_coach_notes_block": "*Coach notes:*\n{notes}",
        "review_delivered_coach": "✅ The coach sent your review.",
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
        "retry_button": "🔄 Try again",
        "retry_simple_button": "⚡ Use simpler model",
        "retry_simple_status": (
            "⏳ Analyzing with a backup model — usually responds faster..."
        ),
        "analysis_used_simple_model": (
            "ℹ️ Analysis used a backup model because the main one was overloaded."
        ),
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
            "⏳ Can't analyze the video right now — AI models are overloaded.\n\n"
            "Your clip is fine: it was already sent to the coach, who can review it "
            "manually.\n\n"
            "You can also tap Retry a bit later."
        ),
        "error_internal": (
            "⏳ Temporary analysis service glitch. Try again in about a minute."
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
            "If it keeps failing — check the Gemini key in `.env`."
        ),
        "analysis_fallback_status": (
            "⏳ Primary model didn't respond — trying the backup model…"
        ),
        "cmd_profile": "My profile",
        "ob_intro": (
            "👋 *Let's get acquainted — takes 30 seconds*\n\n"
            "Your answers help the AI and coach review your technique more accurately: "
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
        "ob_reset_profile": "🔄 Start over",
        "profile_reset_confirm_prompt": (
            "⚠️ *Reset profile and all analyses?*\n\n"
            "This will delete:\n"
            "• your profile (level, goals, injuries)\n"
            "• history of all past analyses\n"
            "• the current active analysis\n\n"
            "After reset you'll go through setup again — like your first visit.\n\n"
            "Confirm:"
        ),
        "profile_reset_confirm_yes": "✅ Yes, reset everything",
        "profile_reset_confirm_no": "❌ Cancel",
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
            "Edit profile — update your details.\n"
            "Start over — delete profile and history and set up again."
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
