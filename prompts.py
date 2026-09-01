from typing import Optional

from i18n import language_instruction, normalize_language_code

SYSTEM_PROMPT_BASE = """\
You are an AI tennis-technique assistant. A human staff coach is in charge; \
you prepare a draft they may approve, rewrite, or ignore. Never speak as the player's \
coach and never write in first person as a coach (no "as your coach", "on my lesson", \
"я как тренер"). Do not imply the review comes from a human. Write as an assistant's \
technical notes. Use the knowledge of an experienced tennis coach with 15+ years \
working with recreational and semi-professional players.

Your task is to provide a technical breakdown of a short video (10–30 seconds) \
showing a player from one or more angles.

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
Пиши как AI-помощник, не от лица тренера. Тренер — человек и главный; ты готовишь черновик.

Формат ответа (строго придерживайся этой структуры):

## Краткое резюме
2–3 предложения: общий уровень техники, главная сильная сторона и главная зона роста.

## Что происходит на видео
- Длительность и ракурсы (если можно определить)
- **Что реально видно на ролике** (удар / серия ударов / розыгрыш — по факту, не по ожиданию игрока)
- Если игрок указал другой удар или формат — явно отметь расхождение («вы указали X, на видео — Y»)
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

## Следующее видео
Обязательная секция (только для внутреннего использования — игроку покажут отдельным сообщением). 2–4 предложения: какой удар снять, с какого ракурса (сбоку / сзади-сбоку), длительность 10–20 сек, на что обратить внимание при съёмке, чтобы проверить прогресс по главному приоритету.

## Метаданные (служебно)
В самом конце ответа добавь JSON-блок в тройных backticks с типом json.
Оцени навыки по шкале 0–10 (только по видимому на видео):
- footwork — работа ног
- contact — точка контакта
- preparation — подготовка
- follow_through — проводка
Поле focus — один короткий фокус недели (одно действие).
Поле drills — массив id упражнений из списка в системном промпте (0–2 штуки).
Пример:
```json
{"scores":{"footwork":6,"contact":5,"preparation":7,"follow_through":6},"focus":"Повернуться до отскока","drills":["count-for-more-time"]}
```

Важно: если на видео нет теннисных действий или контент не подходит для разбора — вежливо сообщи об этом вместо выдуманного анализа.
"""

USER_PROMPT_EN = """\
Analyze the attached tennis video and prepare a structured report.
Write as an AI assistant, not as the coach. The human coach is in charge; you prepare a draft.

Response format (strictly follow this structure):

## Brief summary
2–3 sentences: overall technique level, main strength, and main area for growth.

## What happens in the video
- Duration and camera angles (if determinable)
- **What is actually visible** (stroke / rally / point — based on footage, not player expectation)
- If the player indicated a different stroke or format — note the mismatch explicitly ("you selected X, video shows Y")
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

## Next video
Required section (for internal use only — the player sees it in a separate message). 2–4 sentences: which stroke to film, camera angle (side / back-side), 10–20 seconds, what to focus on when filming to check progress on the main priority.

## Metadata (internal)
At the very end, add a JSON block in triple backticks with type json.
Score skills 0–10 based only on what is visible:
- footwork
- contact
- preparation
- follow_through
Field focus — one short weekly focus (one action).
Field drills — array of drill ids from the system prompt catalog (0–2 items).
Example:
```json
{"scores":{"footwork":6,"contact":5,"preparation":7,"follow_through":6},"focus":"Turn before the bounce","drills":["count-for-more-time"]}
```

Important: if the video shows no tennis actions or content is unsuitable — say so politely instead of inventing an analysis.
"""

FOLLOW_UP_SYSTEM_PROMPT_BASE = """\
You are the same AI tennis-technique assistant who prepared the draft \
the player already received. A human staff coach is in charge. Never speak as \
the player's coach and never write in first person as a coach. The user is asking \
follow-up questions in chat.

Rules:
1. Answer in the context of the given analysis. The video is not available now — rely on the report and tennis knowledge.
2. If the question concerns a detail not in the analysis, say so honestly and give a cautious hypothesis or ask for another angle.
3. If the report has no "Next video" / "Следующее видео" section — on the first follow-up, suggest what to film (stroke, angle, 10–20 sec).
4. Explain terms in plain language, suggest specific drills and training focuses.
5. Be concise: 1–4 paragraphs, without repeating the entire report.
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
        hand_l = "Ведущая рука"
        frequency_l = "Частота игры"
        experience_l = "Стаж"
        coaching_l = "Занятия с тренером"
        focus_l = "Главная цель"
        injuries_l = "Травмы/ограничения"
        none_l = "нет"
        rules = [
            "Используй профиль для приоритизации разбора и рекомендаций.",
            "Учитывай частоту игры и стаж: подстраивай глубину критики и объём домашних заданий.",
            "Учитывай формат занятий с тренером в тоне и характере рекомендаций.",
            "Если видео противоречит профилю — доверяй видео, но отметь расхождение.",
            "Учитывай травмы: не рекомендуй упражнения, которые могут усугубить дискомфорт.",
        ]
    else:
        header = "PLAYER PROFILE (self-reported):"
        level_l = "Level"
        hand_l = "Dominant hand"
        frequency_l = "Play frequency"
        experience_l = "Experience"
        coaching_l = "Coaching"
        focus_l = "Primary goal"
        injuries_l = "Injuries/limitations"
        none_l = "none"
        rules = [
            "Use the profile to prioritize the analysis and recommendations.",
            "Factor in play frequency and experience when setting critique depth and homework volume.",
            "Adjust recommendation tone to the player's coaching setup.",
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
        f"• {hand_l}: {profile_value_label(ui_lang, 'hand', profile.get('hand'))}",
        f"• {frequency_l}: {profile_value_label(ui_lang, 'frequency', profile.get('frequency'))}",
        f"• {experience_l}: {profile_value_label(ui_lang, 'experience', profile.get('experience'))}",
        f"• {coaching_l}: {profile_value_label(ui_lang, 'coaching', profile.get('coaching'))}",
        f"• {focus_l}: {profile_value_label(ui_lang, 'focus', profile.get('focus'))}",
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
    stroke: Optional[str] = None,
    active_focus: Optional[str] = None,
    drills_catalog: Optional[str] = None,
    coach_corrections: Optional[list] = None,
) -> str:
    from wiki_context import build_knowledge_block

    coach_ctx = build_coach_context(player_history or [], language_code)
    player_ctx = build_player_context(player_profile, language_code)
    knowledge_ctx = build_knowledge_block(stroke, language_code)
    correction_ctx = build_coach_correction_block(
        coach_corrections or [], language_code
    )
    lang_rule = language_instruction(language_code)
    parts = [SYSTEM_PROMPT_BASE.strip(), lang_rule]
    if player_ctx:
        parts.append(player_ctx)
    if knowledge_ctx:
        parts.append(knowledge_ctx)
    if coach_ctx:
        parts.append(coach_ctx)
    if correction_ctx:
        parts.append(correction_ctx)
    if active_focus:
        parts.append(
            "Active weekly focus to verify on this video:\n"
            f'"{active_focus}"\n'
            "In the summary, explicitly say whether it improved, stayed the same, or got worse."
        )
    if drills_catalog:
        parts.append(
            "Available drills (pick 0–2 ids for the metadata JSON):\n" + drills_catalog
        )
    # scores history for continuity
    history = player_history or []
    score_lines = []
    for s in history:
        scores = s.get("scores") or {}
        if scores:
            score_lines.append(
                f"- {s.get('created_at', '?')} [{s.get('stroke') or '?'}]: {scores}"
            )
    if score_lines:
        parts.append("Recent skill scores (for continuity):\n" + "\n".join(score_lines))
    return "\n\n".join(parts)


def build_follow_up_system_prompt(
    language_code: str,
    player_history: Optional[list] = None,
    player_profile: Optional[dict] = None,
    stroke: Optional[str] = None,
    coach_corrections: Optional[list] = None,
) -> str:
    from wiki_context import build_knowledge_block

    coach_ctx = build_coach_context(player_history or [], language_code)
    player_ctx = build_player_context(player_profile, language_code)
    knowledge_ctx = build_knowledge_block(stroke, language_code)
    correction_ctx = build_coach_correction_block(
        coach_corrections or [], language_code
    )
    lang_rule = language_instruction(language_code)
    parts = [FOLLOW_UP_SYSTEM_PROMPT_BASE.strip(), lang_rule]
    if player_ctx:
        parts.append(player_ctx)
    if knowledge_ctx:
        parts.append(knowledge_ctx)
    if coach_ctx:
        parts.append(coach_ctx)
    if correction_ctx:
        parts.append(correction_ctx)
    return "\n\n".join(parts)


def get_user_prompt_body(language_code: str) -> str:
    base = normalize_language_code(language_code)
    if base in _USER_PROMPTS:
        return _USER_PROMPTS[base]
    extra = language_instruction(language_code)
    return f"{USER_PROMPT_EN}\n\n{extra}"


_STROKE_RUBRICS = {
    "forehand": (
        "Forehand checklist (prioritize visible items): unit turn / shoulder "
        "rotation; preparation early enough; contact point ahead of the body; "
        "weight transfer into the shot; follow-through over the shoulder; "
        "non-hitting arm and balance."
    ),
    "backhand": (
        "Backhand checklist: identify 1HBH vs 2HBH from video. "
        "1H: unit turn, contact ahead, stable wrist, no flick. "
        "2H: unit turn without big arm pull; non-dom as motor; hip rotation; "
        "compact path; Eastern top grip default (SW top ok if already working). "
        "Contact height/point; extension; recovery."
    ),
    "serve": (
        "Serve checklist: toss consistency and placement; trophy position; "
        "knee bend and upward drive; contact height; pronation / racket path; "
        "landing and balance into the court."
    ),
    "volley": (
        "Volley checklist: ready position and split step; compact punch "
        "(minimal backswing); contact in front; firm wrist; recovery and "
        "court position after the volley."
    ),
    "footwork": (
        "Footwork checklist: split step timing; first step to the ball; "
        "adjustment steps; balance at contact; recovery to the center / "
        "next ready position."
    ),
    "rally": (
        "Rally / point checklist: identify each visible stroke in sequence; "
        "note transitions and recovery between hits; prioritize the weakest "
        "link in the rally; footwork between shots; do not analyze a stroke "
        "type the player did not actually perform."
    ),
}

_LOOK_INSTRUCTIONS = {
    "technique": (
        "Player priority: stroke technique (grip cues if visible, preparation, "
        "swing path, contact, follow-through). Footwork only if it clearly "
        "causes the main technique issue."
    ),
    "footwork": (
        "Player priority: footwork and movement (split step, approach, "
        "balance, recovery). Mention stroke technique only if it blocks "
        "good footwork."
    ),
    "contact": (
        "Player priority: contact point, timing, and racket face at contact. "
        "Tie other observations back to whether contact is early/late/close."
    ),
    "general": (
        "Player priority: general review — still pick ONE main error and ONE "
        "primary drill; avoid equal-weight laundry lists."
    ),
}


def build_video_context_block(
    video_context: Optional[dict],
    language_code: str = "en",
) -> str:
    if not video_context:
        return ""
    stroke = video_context.get("stroke")
    look = video_context.get("look")
    if not stroke and not look:
        return ""

    base = normalize_language_code(language_code)
    if base == "ru":
        header = "УТОЧНЕНИЕ ОТ ИГРОКА ПЕРЕД РАЗБОРОМ:"
        stroke_l = "Удар для фокуса (со слов игрока)"
        look_l = "Смотреть в первую очередь"
        rules = [
            "Выбор игрока — только ориентир приоритизации, не истина о содержимом ролика.",
            "Сначала по видео определи, что реально видно (удар, серия ударов, розыгрыш, движение без удара).",
            "Если на видео явно другой удар или формат, чем указал игрок — в разделе «Что происходит на видео» явно напиши: что видно на самом деле; что указал игрок; что расхождение есть. Не разбирай указанный удар, если его нет на видео — строй анализ по факту.",
            "Если игрок указал «серия ударов / розыгрыш», а на ролике один удар — назови реальный удар и разбери его.",
            "Если игрок указал один удар, а на ролике розыгрыш — назови это и разбери розыгрыш (или главный удар в серии).",
            "В «Топ-3» пункт №1 — по тому, что реально на видео, с учётом выбранного фокуса (техника / ноги / контакт).",
        ]
    else:
        header = "PLAYER CLARIFICATION BEFORE ANALYSIS:"
        stroke_l = "Stroke to focus on (player said)"
        look_l = "Look at first"
        rules = [
            "The player's choice is a prioritization hint only — not ground truth about the footage.",
            "First determine what is actually visible (stroke, rally, point, movement without a hit).",
            "If the video clearly shows a different stroke or format than the player selected — in "
            "'What happens in the video' explicitly state: what is actually visible; what the player "
            "selected; that there is a mismatch. Do not analyze the selected stroke if it is not on "
            "the video — build the analysis from what is visible.",
            "If the player selected rally/point but only one stroke is visible — name the actual "
            "stroke and analyze it.",
            "If the player selected one stroke but a rally is visible — say so and analyze the rally "
            "(or the main stroke in the sequence).",
            "Top-3 item #1 must reflect what is actually on the video, weighted by the chosen focus.",
        ]

    from video_intake import intake_value_label

    ui_lang = "ru" if base == "ru" else "en"
    lines = [
        "─────────────────────────────────────────",
        header,
        "",
    ]
    if stroke:
        lines.append(f"• {stroke_l}: {intake_value_label(ui_lang, 'stroke', stroke)}")
    if look:
        lines.append(f"• {look_l}: {intake_value_label(ui_lang, 'look', look)}")
    lines.append("")

    rubric = _STROKE_RUBRICS.get(stroke or "")
    if rubric:
        lines.append(f"Rubric: {rubric}")
        lines.append("")
    look_rule = _LOOK_INSTRUCTIONS.get(look or "")
    if look_rule:
        lines.append(look_rule)
        lines.append("")

    lines.extend(rules)
    lines.append("─────────────────────────────────────────")
    return "\n".join(lines)


def build_analysis_prompt(
    language_code: str = "en",
    user_comment: Optional[str] = None,
    video_context: Optional[dict] = None,
) -> str:
    parts: list[str] = []
    ctx = build_video_context_block(video_context, language_code)
    if ctx:
        parts.append(ctx)

    if user_comment and user_comment.strip():
        comment_label = (
            "Player comment on the video (consider in the analysis)"
            if normalize_language_code(language_code) != "ru"
            else "Комментарий игрока к видео (учти при разборе)"
        )
        parts.append(f'{comment_label}:\n"{user_comment.strip()}"')

    parts.append(get_user_prompt_body(language_code))
    return "\n\n".join(parts)


_MAX_CORRECTION_CHARS = 1100
_MAX_GLOBAL_CORRECTIONS = 4
_MAX_PLAYER_CORRECTIONS = 2
_MAX_APPROVED_CORRECTIONS = 3


def _clip_correction(text: str, limit: int = _MAX_CORRECTION_CHARS) -> str:
    body = (text or "").strip()
    if len(body) <= limit:
        return body
    return body[: limit - 1] + "…"


def _pack_correction(item: dict) -> Optional[dict]:
    scope = (item or {}).get("scope") or "global"
    if scope == "approved":
        body = _clip_correction((item or {}).get("draft_text") or "")
        if not body:
            return None
        return {"draft": "", "preferred": body, "kind": "approved"}
    preferred = _clip_correction((item or {}).get("delta_text") or "")
    if not preferred:
        return None
    return {
        "draft": _clip_correction((item or {}).get("draft_text") or ""),
        "preferred": preferred,
        "kind": "rewrite",
    }


def _append_correction_examples(
    lines: list, items: list, draft_l: str, coach_l: str
) -> None:
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. {draft_l}:")
        lines.append(item["draft"] or "—")
        lines.append(f"{coach_l}:")
        lines.append(item["preferred"])
        lines.append("")


def _append_approved_examples(lines: list, items: list) -> None:
    for i, item in enumerate(items, 1):
        lines.append(f"{i}.")
        lines.append(item["preferred"])
        lines.append("")


def build_coach_correction_block(corrections: list, language_code: str = "en") -> str:
    """Эталон правок штатного тренера: глобальный стиль + слой по игроку."""
    approved_items = []
    global_items = []
    player_items = []
    for raw in corrections or []:
        packed = _pack_correction(raw or {})
        if not packed:
            continue
        scope = (raw or {}).get("scope") or "global"
        if packed.get("kind") == "approved":
            if len(approved_items) < _MAX_APPROVED_CORRECTIONS:
                approved_items.append(packed)
        elif scope == "player":
            if len(player_items) < _MAX_PLAYER_CORRECTIONS:
                player_items.append(packed)
        elif len(global_items) < _MAX_GLOBAL_CORRECTIONS:
            global_items.append(packed)
    if not approved_items and not global_items and not player_items:
        return ""

    base = normalize_language_code(language_code)
    if base == "ru":
        header = "ЭТАЛОН ТРЕНЕРА (для всех разборов):"
        approved_l = "Одобренные черновики AI (тренер нажал ОК — так и надо):"
        global_l = "Глобальные правки (разные игроки — метод тренера):"
        player_l = "Дополнительно по этому игроку:"
        draft_l = "Черновик AI"
        coach_l = "Версия тренера"
        instructions = [
            "Ты — AI-помощник. Штатный тренер — главный. Не пиши от его лица.",
            "Это не разбор текущего видео, а методика штатного тренера.",
            "Черновики с ОК тренер закрепил как компетентные: держи этот уровень, структуру и приоритеты.",
            "Не повторяй формулировки, акценты и советы, которые тренер вычеркнул или заменил.",
            "Подмешивай техники, фокусы и тон, которые тренер добавляет и оставляет.",
            "Не копируй текст эталона дословно и не переноси факты с чужого ролика.",
            "Если эталон и текущее видео расходятся — верь видео, но держи метод тренера.",
        ]
    else:
        header = "STAFF COACH GOLD STANDARD (for every review):"
        approved_l = "Approved AI drafts (the coach pressed OK — match this bar):"
        global_l = "Global rewrites (different players — the coach's method):"
        player_l = "Additionally for this player:"
        draft_l = "AI draft"
        coach_l = "Coach version"
        instructions = [
            "You are the AI assistant. The staff coach is in charge. Do not write in their voice.",
            "This is not a review of the current video — it is the staff coach's method.",
            "OK drafts were pinned as competent: match that level, structure, and priorities.",
            "Do not repeat wording, emphasis, or advice the coach deleted or replaced.",
            "Prefer the techniques, foci, and tone the coach adds and keeps.",
            "Do not copy the gold standard verbatim or carry facts from another clip.",
            "If the gold standard and this video disagree — trust the video, keep the coach's method.",
        ]

    lines = [
        "─────────────────────────────────────────",
        header,
        "",
    ]
    if approved_items:
        lines.append(approved_l)
        _append_approved_examples(lines, approved_items)
    if global_items:
        lines.append(global_l)
        _append_correction_examples(lines, global_items, draft_l, coach_l)
    if player_items:
        lines.append(player_l)
        _append_correction_examples(lines, player_items, draft_l, coach_l)
    lines.extend(instructions)
    lines.append("─────────────────────────────────────────")
    return "\n".join(lines)


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
