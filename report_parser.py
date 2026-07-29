"""Парсинг структурированного блока из отчёта Gemini."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

SKILL_KEYS = ("footwork", "contact", "preparation", "follow_through")

# RU/EN aliases → canonical
SKILL_ALIASES = {
    "footwork": "footwork",
    "работа ног": "footwork",
    "ноги": "footwork",
    "contact": "contact",
    "точка контакта": "contact",
    "контакт": "contact",
    "preparation": "preparation",
    "подготовка": "preparation",
    "follow_through": "follow_through",
    "follow-through": "follow_through",
    "проводка": "follow_through",
}


@dataclass
class ParsedReport:
    text: str
    scores: dict[str, float] = field(default_factory=dict)
    focus: str = ""
    drill_ids: list[str] = field(default_factory=list)
    raw_meta: dict = field(default_factory=dict)


_JSON_BLOCK_RE = re.compile(
    r"```(?:json)?\s*(\{.*?\})\s*```",
    re.DOTALL | re.IGNORECASE,
)
_BARE_JSON_RE = re.compile(
    r"(\{\s*\"(?:scores|focus|drills|skills).*?\})",
    re.DOTALL | re.IGNORECASE,
)


def _normalize_scores(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, float] = {}
    for key, value in raw.items():
        canon = SKILL_ALIASES.get(str(key).strip().lower())
        if not canon:
            continue
        try:
            score = float(value)
        except (TypeError, ValueError):
            continue
        result[canon] = max(0.0, min(10.0, score))
    return result


def _extract_json_candidates(text: str) -> list[dict]:
    candidates: list[dict] = []
    for pattern in (_JSON_BLOCK_RE, _BARE_JSON_RE):
        for match in pattern.finditer(text):
            blob = match.group(1)
            try:
                data = json.loads(blob)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                candidates.append(data)
    return candidates


def parse_report(text: str) -> ParsedReport:
    """Достаёт scores/focus/drills; при отсутствии блока возвращает чистый текст."""
    if not text:
        return ParsedReport(text="")

    candidates = _extract_json_candidates(text)
    meta: dict = {}
    for data in candidates:
        if any(k in data for k in ("scores", "skills", "focus", "drills", "drill_ids")):
            meta = data
            break

    scores = _normalize_scores(meta.get("scores") or meta.get("skills") or {})
    focus = str(meta.get("focus") or "").strip()
    drills_raw = meta.get("drills") or meta.get("drill_ids") or []
    drill_ids: list[str] = []
    if isinstance(drills_raw, list):
        for item in drills_raw:
            if isinstance(item, str) and item.strip():
                drill_ids.append(item.strip())
            elif isinstance(item, dict) and item.get("id"):
                drill_ids.append(str(item["id"]).strip())

    cleaned = text
    for match in _JSON_BLOCK_RE.finditer(text):
        cleaned = cleaned.replace(match.group(0), "")
    cleaned = cleaned.strip()

    return ParsedReport(
        text=cleaned or text.strip(),
        scores=scores,
        focus=focus,
        drill_ids=drill_ids,
        raw_meta=meta,
    )


def format_scores_line(scores: dict[str, float], lang: str = "ru") -> str:
    labels = {
        "ru": {
            "footwork": "Ноги",
            "contact": "Контакт",
            "preparation": "Подготовка",
            "follow_through": "Проводка",
        },
        "en": {
            "footwork": "Feet",
            "contact": "Contact",
            "preparation": "Prep",
            "follow_through": "Follow",
        },
    }[lang if lang in ("ru", "en") else "en"]
    parts = []
    for key in SKILL_KEYS:
        if key in scores:
            parts.append(f"{labels[key]} {scores[key]:.0f}/10")
    return " · ".join(parts)


def sparkline(values: list[float]) -> str:
    if not values:
        return "—"
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(values), max(values)
    if hi <= lo:
        return blocks[0] * len(values)
    chars = []
    for v in values:
        idx = int(round((v - lo) / (hi - lo) * (len(blocks) - 1)))
        chars.append(blocks[idx])
    return "".join(chars)
