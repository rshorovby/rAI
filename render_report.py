"""JSON structured output → markdown, который уже умеет разбирать бот."""

import json

# Для подачи история хранит leg_drive под ключом footwork.
_LEGACY_AXIS = {
    "serve": {
        "footwork": "leg_drive",
        "contact": "contact",
        "preparation": "preparation",
        "follow_through": "follow_through",
    },
    "volley": {
        "footwork": "footwork",
        "contact": "contact",
        "preparation": "preparation",
    },
    "footwork": {
        "footwork": "footwork",
        "preparation": "preparation",
    },
}
_DEFAULT_AXIS = {
    "footwork": "footwork",
    "contact": "contact",
    "preparation": "preparation",
    "follow_through": "follow_through",
}
_LEGACY_ORDER = ("footwork", "contact", "preparation", "follow_through")

_ANGLES = {
    "side": "сбоку",
    "back": "сзади",
    "back_side": "сзади-сбоку",
    "front": "спереди",
    "other": "другой",
    "unknown": "не определён",
}
_CONTENT = {
    "single_stroke": "один удар",
    "stroke_series": "серия ударов",
    "rally": "розыгрыш",
    "movement_only": "движение без удара",
    "not_tennis": "нет тенниса",
}
_LEVELS = {
    "beginner": "начинающий",
    "intermediate": "любитель",
    "advanced": "продвинутый любитель",
    "competitive": "соревновательный",
    "unknown": "не определён",
}
_SEVERITY = {
    "critical": "🔴 Критично",
    "important": "🟠 Важно",
    "minor": "🟡 Незначительно",
    "strength": "🟢 Сильная сторона",
}
_CATEGORIES = (
    ("technique", "Техника удара"),
    ("movement", "Передвижение и работа ног"),
    ("balance", "Позиционирование и баланс"),
)


def render_report(data: dict) -> str:
    video = data.get("video") or {}
    if video.get("visible_content") == "not_tennis":
        return "## Краткое резюме\n" + (data.get("summary") or "").strip() + "\n"

    parts = [
        "## Краткое резюме\n" + (data.get("summary") or "").strip(),
        "## Что происходит на видео\n" + _video_section(data),
        "## Разбор по категориям\n" + _categories(data.get("remarks") or []),
        "## Топ-3 приоритета для тренировки\n" + _top3(data.get("findings") or []),
        "## Следующее видео\n" + (data.get("next_video") or "").strip(),
        "## Метаданные (служебно)\n```json\n"
        + json.dumps(legacy_metadata(data), ensure_ascii=False, indent=2)
        + "\n```",
    ]
    return "\n\n".join(parts) + "\n"


def legacy_metadata(data: dict) -> dict:
    primary = data.get("primary_segment")
    return {
        "scores": legacy_scores(primary, data.get("scores") or []),
        "focus": data.get("focus") or "",
        "issue_tags": list(data.get("issue_tags") or []),
        "drills": list(data.get("drills") or []),
        "detected_segments": list(data.get("detected_segments") or []),
        "focus_checks": [
            {"stroke": item.get("stroke"), "status": item.get("status")}
            for item in (data.get("focus_checks") or [])
            if isinstance(item, dict)
        ],
        "findings": [
            {
                "problem": item.get("problem") or "",
                "recommendation": item.get("recommendation") or "",
                "detail": item.get("detail") or "",
                "practice": item.get("practice") or "",
                "drill_ids": list(item.get("drill_ids") or []),
            }
            for item in (data.get("findings") or [])
            if isinstance(item, dict)
        ],
        "primary_segment": None if primary in (None, "", "none") else primary,
    }


def legacy_scores(primary: str, scores: list) -> dict:
    by_axis = {}
    for item in scores:
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        if value is None:
            continue
        by_axis[item.get("axis")] = value
    mapping = _LEGACY_AXIS.get(primary or "", _DEFAULT_AXIS)
    out = {}
    for key in _LEGACY_ORDER:
        axis = mapping.get(key)
        if axis and axis in by_axis:
            out[key] = by_axis[axis]
    return out


def _video_section(data: dict) -> str:
    video = data.get("video") or {}
    lines = []
    duration = video.get("duration_sec_approx")
    if duration is not None:
        lines.append(f"- Длительность: ~{duration} с")
    angles = [_ANGLES.get(item, item) for item in (video.get("angles") or [])]
    if angles:
        lines.append("- Ракурсы: " + ", ".join(angles))
    content = video.get("visible_content")
    if content:
        lines.append("- Что видно: " + _CONTENT.get(content, content))
    if video.get("stroke_repetitions") is not None:
        lines.append(f"- Повторы основного удара: {video['stroke_repetitions']}")
    level = video.get("level_estimate")
    if level:
        lines.append("- Уровень: " + _LEVELS.get(level, level))
    if video.get("mismatch_with_player_choice") and video.get("mismatch_note"):
        lines.append("- Расхождение: " + str(video["mismatch_note"]).strip())
    for item in data.get("observations") or []:
        lines.append(f"- {item.get('t')}: {item.get('what_is_seen')}")
    return "\n".join(lines)


def _categories(remarks: list) -> str:
    blocks = []
    for key, title in _CATEGORIES:
        rows = [item for item in remarks if item.get("category") == key]
        body = (
            "\n\n".join(_remark(item) for item in rows)
            if rows
            else "В этом разборе не в приоритете"
        )
        blocks.append(f"### {title}\n{body}")
    return "\n\n".join(blocks)


def _remark(item: dict) -> str:
    if item.get("certainty") == "insufficient":
        text = (item.get("observation") or item.get("why_it_matters") or "").strip()
        return f"{item.get('t')}\nНедостаточно данных: {text}"
    lines = [str(item.get("t") or "")]
    observation = (item.get("observation") or "").strip()
    if item.get("certainty") == "likely":
        observation = f"{observation} (гипотеза)"
    lines.append(f"**Наблюдение:** {observation}")
    lines.append(f"**Проблема / плюс:** {(item.get('why_it_matters') or '').strip()}")
    severity = _SEVERITY.get(item.get("severity") or "")
    if severity:
        lines.append(f"**Критичность:** {severity}")
    recommendation = item.get("recommendation")
    if recommendation:
        lines.append(f"**Рекомендация:** {recommendation.strip()}")
    return "\n".join(lines)


def _top3(findings: list) -> str:
    chunks = []
    for index, item in enumerate(findings, 1):
        chunks.append(
            f"{index}. **Действие:** {(item.get('recommendation') or '').strip()}\n"
            f"**Зачем:** {(item.get('problem') or '').strip()}"
        )
    return "\n\n".join(chunks)
