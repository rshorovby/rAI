from typing import Optional

from i18n import language_instruction, normalize_language_code

SYSTEM_PROMPT_BASE = """\
You are an experienced tennis coach with 15+ years working with recreational \
and semi-professional players. Your task is to provide a technical breakdown of \
a short video (10–30 seconds) showing a player from one or more angles.

Analysis rules:
1. Identify visible strokes/actions (serve, forehand, backhand, volley, smash, movement without a hit).
2. Evaluate stroke technique: grip, preparation, body rotation, weight transfer, contact point, follow-through.
3. Evaluate footwork: split step, movement to the ball, recovery after the hit, balance, body position relative to the ball.
4. If multiple angles are shown — compare observations and note what each angle reveals best.
5. Do not invent what is not visible. If an angle does not allow assessment — write "insufficient data" (in the response language).
6. Separate facts (what is visible) from hypotheses (likely but not obvious).
7. Give specific, actionable recommendations — not vague phrases like "work on your technique".
8. Explain terms clearly for amateurs on first use.
"""

USER_PROMPT_RU = """\
Проанализируй прикреплённое видео теннисиста и подготовь структурированный отчёт.

Формат ответа (строго придерживайся этой структуры):

## Краткое резюме
2–3 предложения: общий уровень техники, главная сильная сторона и главная зона роста.

## Что происходит на видео
- Длительность и ракурсы (если можно определить)
- Какие удары/действия выполняет игрок
- Уровень игры (любитель / продвинутый любитель / соревновательный — по видимым признакам)

## Разбор по категориям

### Техника удара
Для каждого замечания укажи:
- **Наблюдение:** что именно видно
- **Проблема / плюс:** почему это важно
- **Критичность:** 🔴 Критично | 🟠 Важно | 🟡 Незначительно | 🟢 Сильная сторона
- **Рекомендация:** одно конкретное упражнение или фокус на тренировке

### Передвижение и работа ног
(тот же формат: Наблюдение → Проблема/плюс → Критичность → Рекомендация)

### Позиционирование и баланс
(тот же формат)

## Топ-3 приоритета для тренировки
Нумерованный список от самого важного к менее важному. Каждый пункт — одно предложение с конкретным действием.

## Ограничения анализа
Что невозможно оценить из-за ракурса, длительности или качества видео.

Важно: если на видео нет теннисных действий или контент не подходит для разбора — вежливо сообщи об этом вместо выдуманного анализа.
"""

USER_PROMPT_EN = """\
Analyze the attached tennis video and prepare a structured report.

Response format (strictly follow this structure):

## Brief summary
2–3 sentences: overall technique level, main strength, and main area for growth.

## What happens in the video
- Duration and camera angles (if determinable)
- Which strokes/actions the player performs
- Skill level (recreational / advanced recreational / competitive — based on visible cues)

## Breakdown by category

### Stroke technique
For each observation include:
- **Observation:** what is specifically visible
- **Issue / plus:** why it matters
- **Severity:** 🔴 Critical | 🟠 Important | 🟡 Minor | 🟢 Strength
- **Recommendation:** one specific drill or training focus

### Movement and footwork
(same format: Observation → Issue/plus → Severity → Recommendation)

### Positioning and balance
(same format)

## Top 3 training priorities
Numbered list from most to least important. Each item — one sentence with a concrete action.

## Analysis limitations
What cannot be assessed due to angle, duration, or video quality.

Important: if the video shows no tennis actions or content is unsuitable — say so politely instead of inventing an analysis.
"""

FOLLOW_UP_SYSTEM_PROMPT_BASE = """\
You are the same tennis coach who already analyzed the player's video. \
The user received the report and is asking follow-up questions in chat.

Rules:
1. Answer in the context of the given analysis. The video is not available now — rely on the report and tennis knowledge.
2. If the question concerns a detail not in the analysis, say so honestly and give a cautious hypothesis or ask for another angle.
3. Explain terms in plain language, suggest specific drills and training focuses.
4. Be concise: 1–4 paragraphs, without repeating the entire report.
"""

_USER_PROMPTS = {
    "ru": USER_PROMPT_RU,
    "en": USER_PROMPT_EN,
}


def build_player_context(profile: Optional[dict], language_code: str = "en") -> str:
    if not profile or profile.get("skipped"):
        return ""

    base = normalize_language_code(language_code)
    if base == "ru":
        header = "ПРОФИЛЬ ИГРОКА (со слов игрока):"
        level_l = "Уровень"
        focus_l = "Фокус улучшения"
        hand_l = "Доминирующая рука"
        injuries_l = "Травмы/ограничения"
        none_l = "нет"
        rules = [
            "Используй профиль для приоритизации разбора и рекомендаций.",
            "Если видео противоречит профилю — доверяй видео, но отметь расхождение.",
            "Учитывай травмы: не рекомендуй упражнения, которые могут усугубить дискомфорт.",
        ]
    else:
        header = "PLAYER PROFILE (self-reported):"
        level_l = "Level"
        focus_l = "Improvement focus"
        hand_l = "Dominant hand"
        injuries_l = "Injuries/limitations"
        none_l = "none"
        rules = [
            "Use the profile to prioritize the analysis and recommendations.",
            "If the video contradicts the profile — trust the video, but note the mismatch.",
            "Respect injuries: do not recommend drills that may worsen discomfort.",
        ]

    from onboarding import profile_value_label

    ui_lang = "ru" if base == "ru" else "en"
    injuries = (profile.get("injuries") or "").strip() or none_l

    lines = [
        "─────────────────────────────────────────",
        header,
        "",
        f"• {level_l}: {profile_value_label(ui_lang, 'level', profile.get('level'))}",
        f"• {focus_l}: {profile_value_label(ui_lang, 'focus', profile.get('focus'))}",
        f"• {hand_l}: {profile_value_label(ui_lang, 'hand', profile.get('hand'))}",
        f"• {injuries_l}: {injuries}",
        "",
    ]
    lines.extend(rules)
    lines.append("─────────────────────────────────────────")
    return "\n".join(lines)


def build_system_prompt(
    language_code: str,
    player_history: Optional[list] = None,
    player_profile: Optional[dict] = None,
) -> str:
    coach_ctx = build_coach_context(player_history or [], language_code)
    player_ctx = build_player_context(player_profile, language_code)
    lang_rule = language_instruction(language_code)
    parts = [SYSTEM_PROMPT_BASE.strip(), lang_rule]
    if player_ctx:
        parts.append(player_ctx)
    if coach_ctx:
        parts.append(coach_ctx)
    return "\n\n".join(parts)


def build_follow_up_system_prompt(
    language_code: str,
    player_history: Optional[list] = None,
    player_profile: Optional[dict] = None,
) -> str:
    coach_ctx = build_coach_context(player_history or [], language_code)
    player_ctx = build_player_context(player_profile, language_code)
    lang_rule = language_instruction(language_code)
    parts = [FOLLOW_UP_SYSTEM_PROMPT_BASE.strip(), lang_rule]
    if player_ctx:
        parts.append(player_ctx)
    if coach_ctx:
        parts.append(coach_ctx)
    return "\n\n".join(parts)


def get_user_prompt_body(language_code: str) -> str:
    base = normalize_language_code(language_code)
    if base in _USER_PROMPTS:
        return _USER_PROMPTS[base]
    extra = language_instruction(language_code)
    return f"{USER_PROMPT_EN}\n\n{extra}"


def build_analysis_prompt(
    language_code: str = "en",
    user_comment: Optional[str] = None,
) -> str:
    body = get_user_prompt_body(language_code)
    if user_comment and user_comment.strip():
        comment_label = (
            "Player comment on the video (consider in the analysis)"
            if normalize_language_code(language_code) != "ru"
            else "Комментарий игрока к видео (учти при разборе)"
        )
        return f'{comment_label}:\n"{user_comment.strip()}"\n\n' f"{body}"
    return body


def build_coach_context(history: list[dict], language_code: str = "en") -> str:
    """Формирует блок «заметки тренера» из прошлых сессий для вставки в system prompt."""
    if not history:
        return ""

    base = normalize_language_code(language_code)
    if base == "ru":
        header = "ЗАМЕТКИ О ИГРОКЕ (предыдущие сессии):"
        session_label = "Сессия"
        top3_label = "Топ-3 тогда:"
        instructions = [
            "При разборе нового видео:",
            "• Сравни с предыдущими сессиями — что изменилось, что улучшилось, что осталось.",
            "• Если проблема повторяется — отметь это явно («как и в прошлый раз…»).",
            "• Если виден прогресс — похвали конкретно.",
        ]
    else:
        header = "PLAYER NOTES (previous sessions):"
        session_label = "Session"
        top3_label = "Top 3 then:"
        instructions = [
            "When analyzing the new video:",
            "• Compare with previous sessions — what changed, improved, or persisted.",
            '• If an issue repeats — note it explicitly (e.g. "as before…").',
            "• If progress is visible — praise specifically.",
        ]

    lines = [
        "─────────────────────────────────────────",
        header,
        "",
    ]
    for i, s in enumerate(history, 1):
        lines.append(f"{session_label} {i} · {s['created_at']}:")
        lines.append(f"  {s['summary']}")
        if s["top3"]:
            top3_oneline = " | ".join(
                ln.strip() for ln in s["top3"].splitlines() if ln.strip()
            )
            lines.append(f"  {top3_label} {top3_oneline}")
        lines.append("")

    lines += instructions
    lines.append("─────────────────────────────────────────")
    return "\n".join(lines)


# Обратная совместимость для тестов
USER_PROMPT = USER_PROMPT_RU
