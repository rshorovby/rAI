import os
from datetime import date, datetime
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
2. Evaluate stroke technique: grip (not on serve), preparation, body rotation, weight transfer, contact point, follow-through.
3. Evaluate footwork: split step, movement to the ball, recovery after the hit, balance, body position relative to the ball.
4. If multiple angles are shown — compare observations and note what each angle reveals best.
5. Do not invent what is not visible. If an angle does not allow assessment — write "insufficient data" (in the response language).
6. Separate facts (what is visible) from hypotheses (likely but not obvious).
7. Give specific, actionable recommendations — not vague phrases like "work on your technique".
8. Explain terms clearly for amateurs on first use.
9. If the video is a serve: do not assess grip and do not name waiter's tray / «поднос официанта». Short clips do not show serve racket orientation reliably; those calls are often false even on a sound serve. Focus on toss, trophy, legs, contact height, landing.
"""

SYSTEM_PROMPT_V2 = """\
You are an AI tennis-technique assistant. A human staff coach is in charge; \
you prepare a draft they may approve, rewrite, or ignore. Never speak as the player's \
coach and never write in first person as a coach (no "as your coach", "on my lesson", \
"я как тренер"). Do not imply the review comes from a human. Write as an assistant's \
technical notes. Use the knowledge of an experienced tennis coach with 15+ years \
working with recreational and semi-professional players.

Your task is to provide a technical breakdown of a video up to 60 seconds \
showing a player from one or more angles.

Analysis rules:
1. Identify visible strokes/actions (serve, forehand, backhand, volley, smash, movement without a hit).
2. Evaluate stroke technique: grip (not on serve), preparation, body rotation, weight transfer, contact point, follow-through.
3. Evaluate footwork: split step, movement to the ball, recovery after the hit, balance, body position relative to the ball.
4. If multiple angles are shown — compare observations and note what each angle reveals best.
5. Do not invent what is not visible. If an angle does not allow assessment, set certainty to insufficient and do not state a judgement.
6. Mark what is visible as seen and what is likely but not obvious as likely.
7. Give specific, actionable recommendations — not vague phrases like "work on your technique".
"""


def structured_analysis_v2_enabled() -> bool:
    raw = os.getenv("STRUCTURED_ANALYSIS_V2", "")
    return raw.strip().lower() in ("1", "true", "yes", "on")


def use_structured_analysis_v2(language_code: str) -> bool:
    """Новый промпт только по-русски и только при включённом флаге."""
    return (
        structured_analysis_v2_enabled()
        and normalize_language_code(language_code) == "ru"
    )


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
Ровно три пункта, от самого важного к менее важному. Каждый пункт — строго две строки:
1. **Действие:** одно конкретное действие на корте
**Зачем:** одно предложение, почему это видно на этом видео
Метки **Действие:** и **Зачем:** обязательны. Не склеивай пункт в одно предложение и не подставляй вместо метки длинное тире или двоеточие.

## Следующее видео
Обязательная секция (только для внутреннего использования — игроку покажут отдельным сообщением). 2–4 предложения: какой удар снять, с какого ракурса (сбоку / сзади-сбоку), длительность 10–20 сек, на что обратить внимание при съёмке, чтобы проверить прогресс по главному приоритету.

## Метаданные (служебно)
В самом конце ответа добавь JSON-блок в тройных backticks с типом json.
Оцени навыки по шкале 0–10 (только по видимому на видео):
- footwork — работа ног
- contact — точка контакта
- preparation — подготовка
- follow_through — проводка
Поле focus — один короткий фокус недели для удара с этого видео (одно действие). Не переноси фокус с другого удара.
Поле drills — массив id упражнений из списка в системном промпте (0–2 штуки).
Поле focus_checks — проверки активных фокусов, чей удар виден на видео. Элемент: stroke (ключ удара), status (improved, same, worse или not_visible). Если фокус не стал лучше, в поле focus повтори его прежний текст.
Поле issue_tags — 0–3 slug из списка в системном промпте. Только то, что видно на этом видео.
Поле findings — массив из 1–3 пунктов для игрока. Каждый пункт: problem (что не так, одно-два предложения), recommendation (как закрыть на корзине, одно-два предложения), detail (почему это видно на этом клипе, 2–4 предложения), practice (как исправлять на корте, отдельный текст), drill_ids (0–3 id из каталога). Не пиши категории техника/ноги/баланс и не пиши URL в findings. Markdown секций выше не убирай — это черновик для Forum.
Поле primary_segment — один ключ удара, который реально доминирует на видео: forehand, backhand, serve, volley, footwork, rally.
Поле detected_segments — массив всех видимых сегментов из того же списка (без general). Всегда заполняй детект по факту видео, даже если игрок выбрал другой удар или ничего не выбрал.
Пример:
```json
{"scores":{"footwork":6,"contact":5,"preparation":7,"follow_through":6},"focus":"Повернуться до отскока","focus_checks":[{"stroke":"forehand","status":"same"}],"issue_tags":["unit-turn"],"drills":["count-for-more-time"],"findings":[{"problem":"Подготовка начинается после отскока — ракетка опаздывает.","recommendation":"До отскока разверните плечи и отведите ракетку назад.","detail":"На клипе замах начинается после отскока, поэтому контакт опаздывает.","practice":"На корзине три медленных форхенда: пауза с ракеткой сзади до отскока, затем обычный темп.","drill_ids":["count-for-more-time"]}],"primary_segment":"forehand","detected_segments":["forehand","footwork"]}
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
Exactly three items, most important first. Each item is exactly two lines:
1. **Action:** one concrete on-court action
**Why:** one sentence on why this shows in this video
The labels **Action:** and **Why:** are required. Do not collapse an item into one sentence and do not replace a label with an em dash or a colon.

## Next video
Required section (for internal use only — the player sees it in a separate message). 2–4 sentences: which stroke to film, camera angle (side / back-side), 10–20 seconds, what to focus on when filming to check progress on the main priority.

## Metadata (internal)
At the very end, add a JSON block in triple backticks with type json.
Score skills 0–10 based only on what is visible:
- footwork
- contact
- preparation
- follow_through
Field focus — one short weekly focus for the stroke on this video (one action). Do not carry a focus from another stroke.
Field drills — array of drill ids from the system prompt catalog (0–2 items).
Field focus_checks — checks of active foci whose stroke is visible. Each item: stroke, status (improved, same, worse, or not_visible). If a focus did not improve, repeat its previous text in focus.
Field issue_tags — 0–3 slugs from the system prompt list. Only what is visible on this video.
Field findings — array of 1–3 player-facing items. Each item: problem (what is wrong, one or two sentences), recommendation (how to close it in the basket, one or two sentences), detail (why this shows on this clip, 2–4 sentences), practice (how to fix it on court, a separate paragraph), drill_ids (0–3 catalog ids). Do not put technique/footwork/balance categories or URLs in findings. Keep the markdown sections above — they are the Forum draft.
Field primary_segment — the one stroke key that actually dominates the video: forehand, backhand, serve, volley, footwork, rally.
Field detected_segments — array of every visible segment from that same list (no general). Always fill detect from the footage, even if the player selected a different stroke or selected none.
Example:
```json
{"scores":{"footwork":6,"contact":5,"preparation":7,"follow_through":6},"focus":"Turn before the bounce","focus_checks":[{"stroke":"forehand","status":"same"}],"issue_tags":["unit-turn"],"drills":["count-for-more-time"],"findings":[{"problem":"Preparation starts after the bounce — the racket is late.","recommendation":"Turn the shoulders and take the racket back before the bounce.","detail":"On this clip the swing starts after the bounce, so contact is late.","practice":"At the basket, three slow forehands: pause with the racket back until the bounce, then normal pace.","drill_ids":["count-for-more-time"]}],"primary_segment":"forehand","detected_segments":["forehand","footwork"]}
```

Important: if the video shows no tennis actions or content is unsuitable — say so politely instead of inventing an analysis.
"""

FOLLOW_UP_OUT_OF_SCOPE = "OUT_OF_SCOPE"

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

FOLLOW_UP_SYSTEM_PROMPT_SCOPED = f"""\
You are the same AI tennis-technique assistant who prepared the draft \
the player already received. A human staff coach is in charge. Never speak as \
the player's coach and never write in first person as a coach. The user is asking \
follow-up questions in chat.

Rules:
1. The video is not available. Rely on the report, this chat, and tennis knowledge. \
Past reports in the prompt stay available. This chat is only about the current analysis.
2. In scope: this analysis, and tennis in general — technique, tactics, rules, \
equipment, drills, and terminology.
3. Out of scope: any other topic, another sport as the main subject, betting, and \
medical diagnosis or treatment. If the message has no in-scope part, reply with \
exactly {FOLLOW_UP_OUT_OF_SCOPE} and nothing else.
4. If the message mixes an in-scope part with something else, answer only the \
in-scope part. Do not develop the rest. Do not use {FOLLOW_UP_OUT_OF_SCOPE} when \
an in-scope part exists.
5. A general tennis question gets a direct answer. Mention this report only when \
the link is obvious: the same stroke or the same error. Do not retell the report.
6. Short acknowledgements such as "ok" or "thanks" get a short reply that invites \
a question about this analysis. Do not answer them with {FOLLOW_UP_OUT_OF_SCOPE}.
7. Pain or injury: no diagnosis and no treatment plan. One sentence to see a doctor. \
Technical changes that reduce load on that stroke are in scope.
8. Suggest what to film next (stroke, angle, 10–20 sec) only on the first follow-up \
that is about this analysis, and only if the report has no "Next video" / \
"Следующее видео" section. Do not add that suggestion to a general tennis answer, \
an acknowledgement, or an out-of-scope reply.
9. If the question concerns a detail not in the analysis, say so honestly and give \
a cautious hypothesis or ask for another angle.
10. Explain terms in plain language. Suggest specific drills and training focuses \
when that helps.
11. Be concise: 1–4 paragraphs, without repeating the entire report.
"""


def follow_up_player_text(model_text: str, refusal: str) -> str:
    raw = (model_text or "").strip()
    if FOLLOW_UP_OUT_OF_SCOPE not in raw:
        return raw
    remainder = raw.replace(FOLLOW_UP_OUT_OF_SCOPE, "").strip(" \t\n.!?…")
    if not remainder:
        return refusal
    return raw.replace(FOLLOW_UP_OUT_OF_SCOPE, "").strip()


_USER_PROMPTS = {
    "ru": USER_PROMPT_RU,
    "en": USER_PROMPT_EN,
}


def _backhand_rule(language_code: str, backhand: Optional[str]) -> str:
    from onboarding import profile_value_label

    ui_lang = "ru" if normalize_language_code(language_code) == "ru" else "en"
    label = profile_value_label(ui_lang, "backhand", backhand)
    if backhand in ("one_handed", "two_handed"):
        if ui_lang == "ru":
            return (
                f"Бэкхенд игрока — {label}. Удар слева с отскока разбирай только "
                "по этому варианту и не смешивай чеклисты одноручного и двуручного. "
                "Резаный удар слева оценивай как slice. Если на видео явно другой "
                "вариант — доверяй видео и отметь расхождение."
            )
        return (
            f"The player's backhand is {label}. Review the drive against that "
            "variant only and do not mix one-handed and two-handed checklists. "
            "Review a slice as a slice. If the video clearly shows the other "
            "variant, trust the video and note the mismatch."
        )
    if ui_lang == "ru":
        return (
            "Вариант бэкхенда в профиле не указан: определи одноручный или "
            "двуручный по видео и разбирай удар слева с отскока по нему."
        )
    return (
        "Backhand variant is not in the profile: identify one-handed or "
        "two-handed from the video and review the drive against that variant."
    )


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
        backhand_l = "Бэкхенд"
        injuries_l = "Травмы/ограничения"
        none_l = "нет"
        rules = [
            "Используй профиль для приоритизации разбора и рекомендаций.",
            "Главная цель всегда «Всё понемногу»: полноценная оценка всех видимых частей техники, без сужения до одной темы.",
            "Учитывай частоту игры и стаж: подстраивай глубину критики и объём домашних заданий.",
            "Учитывай формат занятий с тренером в тоне и характере рекомендаций.",
            "Если видео противоречит профилю — доверяй видео, но отметь расхождение.",
            "Учитывай травмы: не рекомендуй упражнения, которые могут усугубить дискомфорт.",
            _backhand_rule("ru", profile.get("backhand")),
        ]
    else:
        header = "PLAYER PROFILE (self-reported):"
        level_l = "Level"
        hand_l = "Dominant hand"
        frequency_l = "Play frequency"
        experience_l = "Experience"
        coaching_l = "Coaching"
        focus_l = "Primary goal"
        backhand_l = "Backhand"
        injuries_l = "Injuries/limitations"
        none_l = "none"
        rules = [
            "Use the profile to prioritize the analysis and recommendations.",
            "The primary goal is always a full review: assess every visible part of the technique and do not narrow it to one theme.",
            "Factor in play frequency and experience when setting critique depth and homework volume.",
            "Adjust recommendation tone to the player's coaching setup.",
            "If the video contradicts the profile — trust the video, but note the mismatch.",
            "Respect injuries: do not recommend drills that may worsen discomfort.",
            _backhand_rule("en", profile.get("backhand")),
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
        f"• {backhand_l}: {profile_value_label(ui_lang, 'backhand', profile.get('backhand'))}",
        f"• {frequency_l}: {profile_value_label(ui_lang, 'frequency', profile.get('frequency'))}",
        f"• {experience_l}: {profile_value_label(ui_lang, 'experience', profile.get('experience'))}",
        f"• {coaching_l}: {profile_value_label(ui_lang, 'coaching', profile.get('coaching'))}",
        f"• {focus_l}: {profile_value_label(ui_lang, 'focus', 'all')}",
        f"• {injuries_l}: {injuries}",
        "",
    ]
    lines.extend(rules)
    lines.append("─────────────────────────────────────────")
    return "\n".join(lines)


def _issue_tag_line() -> str:
    from wiki_context import issue_tag_slugs

    slugs = issue_tag_slugs()
    if not slugs:
        return ""
    return "Issue tags (pick 0–3 slugs that are visible on this video): " + ", ".join(
        slugs
    )


def _append_personal(
    parts: list,
    language_code: str,
    player_history: Optional[list],
    active_focus: Optional[str],
    prompt_context: Optional[dict],
    include_status_rules: bool = True,
    include_stroke_key: bool = False,
    label_serve_leg_drive: bool = False,
) -> None:
    ctx = prompt_context or {}
    history = player_history or []
    coach_ctx = build_coach_context(
        history,
        language_code,
        today=ctx.get("today"),
        session_count=ctx.get("session_count"),
    )
    if coach_ctx:
        parts.append(coach_ctx)
    foci_ctx = build_foci_block(
        ctx.get("foci") or [],
        language_code,
        include_status_rules=include_status_rules,
        include_stroke_key=include_stroke_key,
    )
    parts.append(
        "Weekly focus is per stroke. If an active focus is provided, verify only that "
        "on this video. If none is provided, set a new focus for the stroke on this "
        "video; do not reuse a focus from another stroke."
    )
    if foci_ctx:
        parts.append(foci_ctx)
    elif active_focus:
        lines = [
            "Active weekly focus for this stroke to verify on this video:",
            f'"{active_focus}"',
        ]
        if include_status_rules:
            lines.append(
                "In the summary, explicitly say whether it improved, stayed the same, "
                "or got worse."
            )
        lines.append("Do not judge a different stroke against this focus.")
        parts.append("\n".join(lines))
    scores_ctx = build_scores_block(
        history,
        language_code,
        label_serve_leg_drive=label_serve_leg_drive,
    )
    if scores_ctx:
        parts.append(scores_ctx)
    practice_ctx = build_practice_block(ctx.get("practice") or [], language_code)
    if practice_ctx:
        parts.append(practice_ctx)
    if not ctx.get("omit_chat_notes"):
        notes_ctx = build_notes_block(ctx.get("notes") or [], language_code)
        if notes_ctx:
            parts.append(notes_ctx)
    path_ctx = build_path_block(ctx.get("path"), language_code)
    if path_ctx:
        parts.append(path_ctx)


def build_system_prompt(
    language_code: str,
    player_history: Optional[list] = None,
    player_profile: Optional[dict] = None,
    stroke: Optional[str] = None,
    active_focus: Optional[str] = None,
    drills_catalog: Optional[str] = None,
    coach_corrections: Optional[list] = None,
    strokes: Optional[list] = None,
    prompt_context: Optional[dict] = None,
    experiment_v2: bool = False,
) -> str:
    if use_structured_analysis_v2(language_code):
        return _build_system_prompt_v2(
            language_code,
            player_history,
            player_profile,
            stroke,
            active_focus,
            drills_catalog,
            strokes,
            prompt_context,
        )
    from wiki_context import build_knowledge_block

    ctx = prompt_context or {}
    player_ctx = build_player_context(player_profile, language_code)
    knowledge_ctx = build_knowledge_block(
        stroke,
        language_code,
        strokes=strokes,
        chronic_tags=ctx.get("chronic_tags"),
    )
    lang_rule = language_instruction(language_code)
    parts = [SYSTEM_PROMPT_BASE.strip(), lang_rule]
    if player_ctx:
        parts.append(player_ctx)
    if knowledge_ctx:
        parts.append(knowledge_ctx)
    if drills_catalog:
        parts.append(
            "Available drills (pick 0–2 ids for the metadata JSON):\n" + drills_catalog
        )
    tag_line = _issue_tag_line()
    if tag_line:
        parts.append(tag_line)
    _append_personal(parts, language_code, player_history, active_focus, ctx)
    return "\n\n".join(parts)


def _build_system_prompt_v2(
    language_code: str,
    player_history: Optional[list],
    player_profile: Optional[dict],
    stroke: Optional[str],
    active_focus: Optional[str],
    drills_catalog: Optional[str],
    strokes: Optional[list],
    prompt_context: Optional[dict],
) -> str:
    from stroke_blocks import load_general_rules, load_stroke_blocks
    from wiki_context import build_knowledge_block

    ctx = prompt_context or {}
    parts = [
        SYSTEM_PROMPT_V2.strip(),
        language_instruction(language_code),
        load_general_rules(),
        load_stroke_blocks(),
    ]
    knowledge_ctx = build_knowledge_block(
        stroke,
        language_code,
        strokes=strokes,
        chronic_tags=ctx.get("chronic_tags"),
        sanitize=True,
        omit_serve_page=True,
    )
    if knowledge_ctx:
        parts.append(knowledge_ctx)
    if drills_catalog:
        parts.append(
            "Available drills (pick 0–2 ids for the metadata JSON):\n" + drills_catalog
        )
    tag_line = _issue_tag_line()
    if tag_line:
        parts.append(tag_line)
    player_ctx = build_player_context(player_profile, language_code)
    if player_ctx:
        parts.append(player_ctx)
    _append_personal(
        parts,
        language_code,
        player_history,
        active_focus,
        ctx,
        include_status_rules=False,
        include_stroke_key=True,
        label_serve_leg_drive=True,
    )
    return "\n\n".join(parts)


def build_follow_up_system_prompt(
    language_code: str,
    player_history: Optional[list] = None,
    player_profile: Optional[dict] = None,
    stroke: Optional[str] = None,
    coach_corrections: Optional[list] = None,
    strokes: Optional[list] = None,
    prompt_context: Optional[dict] = None,
    scoped: bool = False,
) -> str:
    from wiki_context import build_knowledge_block

    ctx = dict(prompt_context or {})
    if scoped:
        ctx["omit_chat_notes"] = True
    player_ctx = build_player_context(player_profile, language_code)
    knowledge_ctx = build_knowledge_block(
        stroke,
        language_code,
        strokes=strokes,
        chronic_tags=ctx.get("chronic_tags"),
    )
    lang_rule = language_instruction(language_code)
    base = FOLLOW_UP_SYSTEM_PROMPT_SCOPED if scoped else FOLLOW_UP_SYSTEM_PROMPT_BASE
    parts = [base.strip(), lang_rule]
    if player_ctx:
        parts.append(player_ctx)
    if knowledge_ctx:
        parts.append(knowledge_ctx)
    _append_personal(parts, language_code, player_history, None, ctx)
    return "\n\n".join(parts)


USER_PROMPT_V2_RU = """\
Проанализируй прикреплённое видео теннисиста и подготовь структурированный отчёт.
Пиши как AI-помощник, не от лица тренера. Тренер — человек и главный; ты готовишь черновик.

Ответ — только JSON по схеме. Свободный текст вне JSON не пиши.

Если на видео нет теннисных действий или контент не подходит для разбора — вежливо объясни это в summary и оставь остальные массивы пустыми.
"""


def get_user_prompt_body(language_code: str, structured: bool = False) -> str:
    base = normalize_language_code(language_code)
    if structured and base == "ru":
        return USER_PROMPT_V2_RU
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
        "Backhand checklist: use the player's backhand from the profile when set "
        "(one-handed or two-handed). Review the drive against that variant only; "
        "do not mix 1HBH and 2HBH checklists. Review a slice as a slice. "
        "If the video clearly shows the other variant, trust the video and note "
        "the mismatch. If the profile has no variant, identify it from the video. "
        "1H: unit turn, contact ahead, stable wrist, no flick. "
        "2H: unit turn without big arm pull; non-dom as motor; hip rotation; "
        "compact path; Eastern top grip default (SW top ok if already working). "
        "Contact height/point; extension; recovery."
    ),
    "serve": (
        "Serve checklist: toss consistency and placement; trophy position; "
        "knee bend and upward drive; contact height; landing and balance "
        "into the court. Do not assess grip. Do not mention waiter's tray "
        "or «поднос официанта» — the clip does not show serve racket "
        "orientation reliably."
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
    experiment_v2: bool = False,
) -> str:
    if not video_context:
        return ""
    stroke = video_context.get("stroke")
    look = video_context.get("look")
    raw_strokes = video_context.get("strokes")
    has_strokes_key = "strokes" in video_context
    if not stroke and not look and not has_strokes_key:
        return ""

    intake_keys = []
    if isinstance(raw_strokes, list):
        intake_keys = [str(s).strip() for s in raw_strokes if str(s).strip()]
    elif stroke and stroke not in ("", "general"):
        intake_keys = [stroke]

    base = normalize_language_code(language_code)
    if base == "ru":
        header = "УТОЧНЕНИЕ ОТ ИГРОКА ПЕРЕД РАЗБОРОМ:"
        stroke_l = "Удар для фокуса (со слов игрока)"
        look_l = "Смотреть в первую очередь"
        general_l = "Игрок не выбрал сегмент — сделай общий обзор техники по тому, что видно. Заполни primary_segment и detected_segments."
        multi_l = "Игрок отметил несколько сегментов — разбор точечный по ним, но детект всё равно по факту видео."
        rules = [
            "Выбор игрока — только ориентир приоритизации, не истина о содержимом ролика.",
            "Сначала по видео определи, что реально видно (удар, серия ударов, розыгрыш, движение без удара).",
            "Если на видео явно другой удар или формат, чем указал игрок — в разделе «Что происходит на видео» явно напиши: что видно на самом деле; что указал игрок; что расхождение есть. Не разбирай указанный удар, если его нет на видео — строй анализ по факту.",
            "Если игрок указал «серия ударов / розыгрыш», а на ролике один удар — назови реальный удар и разбери его.",
            "Если игрок указал один удар, а на ролике розыгрыш — назови это и разбери розыгрыш (или главный удар в серии).",
        ]
    else:
        header = "PLAYER CLARIFICATION BEFORE ANALYSIS:"
        stroke_l = "Stroke to focus on (player said)"
        look_l = "Look at first"
        general_l = "The player selected no segment — write a general technique overview from what is visible. Fill primary_segment and detected_segments."
        multi_l = "The player marked several segments — target those, but detect still follows the footage."
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
        ]

    if look:
        rules.append(
            "В «Топ-3» пункт №1 — по тому, что реально на видео, с учётом выбранного акцента."
            if base == "ru"
            else "Top-3 item #1 must reflect what is actually on the video, weighted by the chosen focus."
        )
    else:
        rules.append(
            "Акцент игрок не выбирал. Разбери все видимые составные части выбранного удара, не сужай разбор до одной темы."
            if base == "ru"
            else "The player did not pick a focus. Cover every visible part of the selected stroke; do not narrow the review to one theme."
        )

    from video_intake import intake_value_label

    ui_lang = "ru" if base == "ru" else "en"
    lines = [
        "─────────────────────────────────────────",
        header,
        "",
    ]
    if has_strokes_key and not intake_keys:
        lines.append(f"• {general_l}")
    elif len(intake_keys) > 1:
        labels = [
            (
                intake_value_label(ui_lang, "stroke", key)
                if key
                in ("forehand", "backhand", "serve", "volley", "footwork", "rally")
                else key
            )
            for key in intake_keys
        ]
        lines.append(f"• {stroke_l}: " + ", ".join(labels))
        lines.append(f"• {multi_l}")
    elif stroke and stroke not in ("", "general"):
        lines.append(f"• {stroke_l}: {intake_value_label(ui_lang, 'stroke', stroke)}")
    if look:
        lines.append(f"• {look_l}: {intake_value_label(ui_lang, 'look', look)}")
    lines.append("")

    rubric_key = intake_keys[0] if len(intake_keys) == 1 else (stroke or "")
    v2 = use_structured_analysis_v2(language_code) and not experiment_v2
    rubric = _STROKE_RUBRICS.get(rubric_key or "")
    if v2 and rubric_key == "serve":
        rubric = None
    if rubric:
        lines.append(f"Rubric: {rubric}")
        lines.append("")
    look_rule = _LOOK_INSTRUCTIONS.get(look or "")
    if v2 and look == "technique" and intake_keys == ["serve"]:
        look_rule = ""
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
    experiment_v2: bool = False,
) -> str:
    parts: list[str] = []
    ctx = build_video_context_block(
        video_context, language_code, experiment_v2=experiment_v2
    )
    if ctx:
        parts.append(ctx)

    if user_comment and user_comment.strip():
        comment_label = (
            "Player comment on the video (consider in the analysis)"
            if normalize_language_code(language_code) != "ru"
            else "Комментарий игрока к видео (учти при разборе)"
        )
        parts.append(f'{comment_label}:\n"{user_comment.strip()}"')

    structured = use_structured_analysis_v2(language_code) and not experiment_v2
    parts.append(get_user_prompt_body(language_code, structured=structured))
    return "\n\n".join(parts)


_MAX_CORRECTION_CHARS = 1100
_MAX_GLOBAL_CORRECTIONS = 2
_MAX_PLAYER_CORRECTIONS = 2
_MAX_APPROVED_CORRECTIONS = 2


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
        if global_items or approved_items:
            instructions.append(
                "Запрет переносить факты относится к глобальным примерам и чужим роликам."
            )
        if player_items:
            instructions.append(
                "Блок «по этому игроку» — факты об этом игроке. Их можно и нужно использовать в разборе."
            )
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
        if global_items or approved_items:
            instructions.append(
                "The ban on carrying facts applies to global examples and other players' clips."
            )
        if player_items:
            instructions.append(
                "The block for this player is facts about this player. Use them in the review."
            )

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


_STROKE_LABELS = {
    "ru": {
        "forehand": "форхенд",
        "backhand": "бэкхенд",
        "serve": "подача",
        "volley": "волей",
        "footwork": "ноги",
        "rally": "розыгрыш",
    },
    "en": {
        "forehand": "forehand",
        "backhand": "backhand",
        "serve": "serve",
        "volley": "volley",
        "footwork": "footwork",
        "rally": "rally",
    },
}

_FOCUS_STATUS_LABELS = {
    "ru": {
        "improved": "стало лучше",
        "same": "так же",
        "worse": "стало хуже",
        "not_visible": "не видно",
    },
    "en": {
        "improved": "improved",
        "same": "same",
        "worse": "worse",
        "not_visible": "not visible",
    },
}

_PRACTICE_ANSWERS = {
    "ru": {
        "yes": "тренировался",
        "hard": "было трудно",
        "skip": "пропустил",
    },
    "en": {
        "yes": "practiced",
        "hard": "it was hard",
        "skip": "skipped",
    },
}


def _ui_lang(language_code: str) -> str:
    return "ru" if normalize_language_code(language_code) == "ru" else "en"


def _stroke_label(language_code: str, stroke: Optional[str]) -> str:
    key = (stroke or "").strip()
    labels = _STROKE_LABELS[_ui_lang(language_code)]
    return labels.get(key, key or "?")


def _parse_day(created_at: str) -> Optional[date]:
    raw = (created_at or "").strip()[:10]
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _when_label(created_at: str, today: date, language_code: str) -> str:
    created = _parse_day(created_at)
    if created is None:
        return created_at or "?"
    days = max(0, (today - created).days)
    ui = _ui_lang(language_code)
    if ui == "ru":
        if days == 0:
            relative = "сегодня"
        elif days == 1:
            relative = "вчера"
        else:
            relative = f"{days} дн. назад"
    else:
        if days == 0:
            relative = "today"
        elif days == 1:
            relative = "yesterday"
        else:
            relative = f"{days} days ago"
    return f"{relative} · {created.isoformat()}"


def build_coach_context(
    history: list[dict],
    language_code: str = "en",
    today: Optional[str] = None,
    session_count: Optional[int] = None,
) -> str:
    """Формирует блок «заметки тренера» из прошлых сессий для вставки в system prompt."""
    if not history and session_count is None:
        return ""

    ui = _ui_lang(language_code)
    day = _parse_day(today or "") or date.today()
    if ui == "ru":
        header = "ЗАМЕТКИ О ИГРОКЕ (предыдущие сессии):"
        session_label = "Сессия"
        top3_label = "Топ-3 тогда:"
        focus_label = "Фокус тогда:"
        check_label = "Проверка фокуса:"
        drills_label = "Выдано:"
        instructions = [
            "При разборе нового видео:",
            "• Сравнивай сессии того же удара. Чужой удар — только фон, не эталон прогресса.",
            "• Если проблема повторяется — отметь это явно («как и в прошлый раз…»).",
            "• Если виден прогресс — похвали конкретно.",
        ]
    else:
        header = "PLAYER NOTES (previous sessions):"
        session_label = "Session"
        top3_label = "Top 3 then:"
        focus_label = "Focus then:"
        check_label = "Focus check:"
        drills_label = "Drills given:"
        instructions = [
            "When analyzing the new video:",
            "• Compare sessions of the same stroke. Another stroke is background, not a progress baseline.",
            '• If an issue repeats — note it explicitly (e.g. "as before…").',
            "• If progress is visible — praise specifically.",
        ]

    lines = [
        "─────────────────────────────────────────",
        header,
        "",
        f"{'Сегодня' if ui == 'ru' else 'Today'}: {day.isoformat()}.",
    ]
    if session_count is not None:
        number = int(session_count) + 1
        if ui == "ru":
            if int(session_count) <= 0:
                lines.append("Это первое видео игрока.")
            else:
                lines.append(
                    f"Это видео №{number}. Раньше разобрано {int(session_count)}."
                )
        else:
            if int(session_count) <= 0:
                lines.append("This is the player's first video.")
            else:
                lines.append(
                    f"This is video #{number}. {int(session_count)} reviewed before."
                )
    lines.append("")
    status_labels = _FOCUS_STATUS_LABELS[ui]
    if not history:
        lines.append("Прошлых сессий нет." if ui == "ru" else "No previous sessions.")
        lines.append("─────────────────────────────────────────")
        return "\n".join(lines)
    from analysis_checks import redact_racket_orientation
    from focus_strokes import stroke_key

    for i, s in enumerate(history, 1):
        when = _when_label(str(s.get("created_at") or ""), day, language_code)
        serve = stroke_key(s.get("stroke")) == "serve"
        stroke = _stroke_label(language_code, s.get("stroke"))
        lines.append(f"{session_label} {i} · {stroke} · {when}:")
        summary = redact_racket_orientation(s.get("summary") or "", serve=serve)
        lines.append(f"  {summary}")
        focus = redact_racket_orientation(s.get("focus") or "", serve=serve)
        if focus:
            lines.append(f"  {focus_label} {focus}")
        checks = s.get("focus_checks") or []
        if checks:
            bits = []
            for item in checks:
                if not isinstance(item, dict):
                    continue
                status = status_labels.get(
                    item.get("status") or "", item.get("status") or ""
                )
                bits.append(
                    f"{_stroke_label(language_code, item.get('stroke'))}: {status}"
                )
            if bits:
                lines.append(f"  {check_label} " + "; ".join(bits))
        top3 = redact_racket_orientation(s.get("top3") or "", serve=serve)
        if top3:
            top3_oneline = " | ".join(
                ln.strip() for ln in top3.splitlines() if ln.strip()
            )
            if top3_oneline:
                lines.append(f"  {top3_label} {top3_oneline}")
        drills = [
            str(item).strip()
            for item in (s.get("drill_ids") or [])
            if str(item).strip()
        ]
        if drills:
            lines.append(f"  {drills_label} " + ", ".join(drills))
        lines.append("")

    lines += instructions
    lines.append("─────────────────────────────────────────")
    return "\n".join(lines)


def build_scores_block(
    history: list, language_code: str = "en", label_serve_leg_drive: bool = False
) -> str:
    grouped: dict = {}
    order: list = []
    for session in history or []:
        scores = session.get("scores") or {}
        if not scores:
            continue
        stroke = (session.get("stroke") or "").strip() or "?"
        if stroke not in grouped:
            order.append(stroke)
            grouped[stroke] = []
        grouped[stroke].append((session.get("created_at") or "?", scores))
    if not grouped:
        return ""
    ui = _ui_lang(language_code)
    if ui == "ru":
        header = "ОЦЕНКИ НАВЫКОВ (для непрерывности, по ударам):"
        rules = [
            "Сравнивай оценки только внутри одного удара.",
            "Ставь балл по этому видео. Не подгоняй его под прошлые.",
            "Если балл изменился больше чем на 1 — объясни, что изменилось на видео.",
        ]
    else:
        header = "SKILL SCORES (for continuity, by stroke):"
        rules = [
            "Compare scores only within the same stroke.",
            "Score this video. Do not fit the number to past scores.",
            "If a score moves by more than 1 point, explain what changed on the video.",
        ]
    lines = ["─────────────────────────────────────────", header, ""]
    for stroke in order:
        lines.append(_stroke_label(language_code, stroke) + ":")
        for created_at, scores in grouped[stroke]:
            lines.append(
                f"- {created_at}: {_scores_for_prompt(stroke, scores, label_serve_leg_drive)}"
            )
    lines.append("")
    lines.extend(rules)
    lines.append("─────────────────────────────────────────")
    return "\n".join(lines)


def _scores_for_prompt(stroke: str, scores: dict, label_serve_leg_drive: bool) -> dict:
    """Для подачи в истории leg_drive лежит в footwork. В промпт v2 показываем leg_drive."""
    from focus_strokes import stroke_key

    shown = dict(scores)
    if (
        label_serve_leg_drive
        and stroke_key(stroke) == "serve"
        and "footwork" in shown
        and "leg_drive" not in shown
    ):
        shown["leg_drive"] = shown.pop("footwork")
    return shown


def build_foci_block(
    foci: list,
    language_code: str = "en",
    include_status_rules: bool = True,
    include_stroke_key: bool = False,
) -> str:
    rows = []
    for item in foci or []:
        text = (item.get("focus") or "").strip()
        stroke = (item.get("stroke") or "").strip()
        if not text or not stroke:
            continue
        rows.append((stroke, text))
    if not rows:
        return ""
    ui = _ui_lang(language_code)
    if ui == "ru":
        header = "АКТИВНЫЕ ФОКУСЫ ИГРОКА (по ударам):"
        rules = [
            "Проверь на этом видео только те фокусы, чей удар реально виден.",
            "В focus_checks поставь improved, same, worse или not_visible.",
            "Если фокус не стал лучше — в поле focus повтори его прежний текст. Новый не придумывай.",
            "Если видимого фокуса нет — focus можно задать заново, для удара этого видео.",
        ]
    else:
        header = "ACTIVE PLAYER FOCI (per stroke):"
        rules = [
            "Verify only the foci whose stroke is actually visible on this video.",
            "Set focus_checks to improved, same, worse, or not_visible.",
            "If a focus did not improve, repeat its previous text in focus. Do not invent a new one.",
            "If no visible focus applies, you may set a new focus for the stroke on this video.",
        ]
    if not include_status_rules:
        rules = [rules[0], rules[3]]
    from analysis_checks import redact_racket_orientation
    from focus_strokes import stroke_key

    body = []
    for stroke, text in rows:
        serve = stroke_key(stroke) == "serve"
        shown = redact_racket_orientation(text, serve=serve)
        if not shown:
            continue
        body.append(f'- {_stroke_label(language_code, stroke)}: "{shown}"')
        if include_stroke_key:
            key = stroke_key(stroke)
            if key:
                body.append(f"  ключ: {key}")
    if not body:
        return ""
    lines = ["─────────────────────────────────────────", header, "", *body, ""]
    lines.extend(rules)
    lines.append("─────────────────────────────────────────")
    return "\n".join(lines)


def build_practice_block(plans: list, language_code: str = "en") -> str:
    rows = [item for item in (plans or []) if (item.get("post_answer") or "").strip()]
    if not rows:
        return ""
    ui = _ui_lang(language_code)
    labels = _PRACTICE_ANSWERS[ui]
    if ui == "ru":
        header = "ТРЕНИРОВКИ ПОСЛЕ ПРОШЛЫХ РАЗБОРОВ:"
        rules = [
            "Упражнение, после которого игрок ответил «было трудно» или «пропустил», не повторяй тем же id.",
            "То, что игрок тренировал, развивай следующим шагом, а не заменяй другой темой.",
        ]
    else:
        header = "PRACTICE AFTER PREVIOUS REVIEWS:"
        rules = [
            "Do not repeat a drill id the player found hard or skipped.",
            "Build on what the player actually practiced. Do not swap it for another topic.",
        ]
    lines = ["─────────────────────────────────────────", header, ""]
    for item in rows:
        answer = labels.get(
            item.get("post_answer") or "", item.get("post_answer") or ""
        )
        drill = (item.get("drill_id") or "").strip() or (
            item.get("drill_text") or ""
        ).strip()
        focus = (item.get("focus_text") or "").strip()
        if ui == "ru":
            lines.append(f"- {answer}: фокус «{focus}»; упражнение {drill}")
        else:
            lines.append(f'- {answer}: focus "{focus}"; drill {drill}')
    lines.append("")
    lines.extend(rules)
    lines.append("─────────────────────────────────────────")
    return "\n".join(lines)


def build_notes_block(notes: list, language_code: str = "en") -> str:
    rows = [item for item in (notes or []) if (item.get("text") or "").strip()]
    if not rows:
        return ""
    ui = _ui_lang(language_code)
    header = "ИГРОК ПИСАЛ:" if ui == "ru" else "THE PLAYER WROTE:"
    rule = (
        "Учитывай жалобы, ограничения и то, что игрок не понял. "
        "Не выдумывай, чего в заметках нет."
        if ui == "ru"
        else "Use complaints, limits, and what the player did not understand. "
        "Do not invent beyond the notes."
    )
    lines = ["─────────────────────────────────────────", header, ""]
    for item in rows:
        lines.append(f"- {item.get('created_at') or '?'}: {item['text'].strip()}")
    lines.append("")
    lines.append(rule)
    lines.append("─────────────────────────────────────────")
    return "\n".join(lines)


def build_path_block(path: Optional[dict], language_code: str = "en") -> str:
    if not path or not path.get("session_count"):
        return ""
    ui = _ui_lang(language_code)
    chronic = path.get("chronic") or []
    strokes = path.get("stroke_counts") or {}
    if ui == "ru":
        header = "ПУТЬ ИГРОКА:"
        lines = [
            "─────────────────────────────────────────",
            header,
            "",
            f"Всего видео: {int(path['session_count'])}. Первое: {path.get('first_at') or '—'}.",
            "Закрыто фокусов (стало лучше): "
            + str(int(path.get("closed_focuses") or 0))
            + ".",
        ]
        if strokes:
            bits = [
                f"{_stroke_label(language_code, key)} {count}"
                for key, count in strokes.items()
            ]
            lines.append("Удары: " + ", ".join(bits) + ".")
        if chronic:
            lines.append("Хронические проблемы (2+ раза за последние видео):")
            for item in chronic:
                lines.append(
                    f"- {_stroke_label(language_code, item.get('stroke'))} / "
                    f"{item.get('tag')}: {item.get('count')} раз, последний {item.get('last_at') or '?'}"
                )
        lines.append(
            "Повтор называй явно. Прогресс по хронической проблеме хвали конкретно."
        )
    else:
        lines = [
            "─────────────────────────────────────────",
            "PLAYER PATH:",
            "",
            f"Videos: {int(path['session_count'])}. First: {path.get('first_at') or '—'}.",
            "Foci closed (improved): "
            + str(int(path.get("closed_focuses") or 0))
            + ".",
        ]
        if strokes:
            bits = [
                f"{_stroke_label(language_code, key)} {count}"
                for key, count in strokes.items()
            ]
            lines.append("Strokes: " + ", ".join(bits) + ".")
        if chronic:
            lines.append("Chronic issues (2+ times in recent videos):")
            for item in chronic:
                lines.append(
                    f"- {_stroke_label(language_code, item.get('stroke'))} / "
                    f"{item.get('tag')}: {item.get('count')}, last {item.get('last_at') or '?'}"
                )
        lines.append(
            "Name a repeat explicitly. Praise progress on a chronic issue specifically."
        )
    lines.append("─────────────────────────────────────────")
    return "\n".join(lines)


# Обратная совместимость для тестов
USER_PROMPT = USER_PROMPT_RU
