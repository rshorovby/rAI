"""Парсинг структурированного блока из отчёта Gemini."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from i18n import report_section_headers

SKILL_KEYS = ("footwork", "contact", "preparation", "follow_through")
FINDINGS_LIMIT = 3

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
    findings: list[dict] = field(default_factory=list)
    summary: str = ""
    next_video: str = ""
    raw_meta: dict = field(default_factory=dict)


_JSON_BLOCK_RE = re.compile(
    r"```(?:json)?\s*(\{.*?\})\s*```",
    re.DOTALL | re.IGNORECASE,
)
_BARE_JSON_RE = re.compile(
    r"(\{\s*\"(?:scores|focus|drills|skills|findings).*?\})",
    re.DOTALL | re.IGNORECASE,
)
_SECTION_RE_TEMPLATE = r"##\s*{header}\s*\n(.*?)(?=\n##\s|\Z)"


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


def _extract_section(text: str, header: str) -> str:
    pattern = _SECTION_RE_TEMPLATE.format(header=re.escape(header))
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def _player_section(text: str, key: str) -> str:
    for lang in ("ru", "en"):
        value = _extract_section(text, report_section_headers(lang)[key])
        if value:
            return value
    return ""


def _normalize_drill_ids(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    ids: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            ids.append(item.strip())
        elif isinstance(item, dict) and item.get("id"):
            ids.append(str(item["id"]).strip())
    return ids


def _normalize_findings(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    findings: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        problem = str(item.get("problem") or "").strip()
        recommendation = str(item.get("recommendation") or "").strip()
        if not problem or not recommendation:
            continue
        findings.append(
            {
                "problem": problem,
                "recommendation": recommendation,
                "drill_ids": _normalize_drill_ids(item.get("drill_ids") or item.get("drills") or []),
            }
        )
        if len(findings) >= FINDINGS_LIMIT:
            break
    return findings


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


_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_DRILL_ID_RE = re.compile(r"\(id:\s*([a-z0-9\-]+)\)", re.IGNORECASE)
_TOP3_ITEM_RE = re.compile(r"^\s*\d+\.\s+(.+)$", re.MULTILINE)
_OBS_START_RE = re.compile(
    r"-\s*\*\*(?:Наблюдение|Observation):\*\*",
    re.IGNORECASE,
)


def _plain(text: str) -> str:
    return _BOLD_RE.sub(r"\1", text).strip()


def _split_label_value(raw: str) -> tuple[str, str]:
    raw = raw.strip()
    match = re.match(r"\*\*(.+?)\*\*\s*:?\s*(.*)$", raw, re.DOTALL)
    if match:
        return match.group(1).strip().rstrip(":"), match.group(2).strip()
    if ":" in raw:
        title, rest = raw.split(":", 1)
        return title.strip(" *").rstrip(":"), rest.strip()
    return raw.strip(" *"), ""


def _drill_ids_in(text: str) -> tuple[str, list[str]]:
    ids = [match.group(1) for match in _DRILL_ID_RE.finditer(text)]
    cleaned = _DRILL_ID_RE.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, ids


def _labeled(block: str, *names: str) -> str:
    for name in names:
        match = re.search(
            rf"\*\*{re.escape(name)}:\*\*\s*(.+?)(?=\n\s*-\s*\*\*|\Z)",
            block,
            re.DOTALL | re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
    return ""


def _is_strength(severity: str) -> bool:
    lowered = severity.lower()
    return "🟢" in severity or "сильн" in lowered or "strength" in lowered


def _severity_rank(severity: str) -> int:
    if "🔴" in severity:
        return 0
    if "🟠" in severity:
        return 1
    if "🟡" in severity:
        return 2
    return 3


def _finding(problem: str, recommendation: str, drill_ids: list[str] | None = None) -> dict | None:
    problem = _plain(problem)
    recommendation = _plain(recommendation)
    if not problem or not recommendation:
        return None
    return {
        "problem": problem,
        "recommendation": recommendation,
        "drill_ids": drill_ids or [],
    }


def _findings_from_top3(text: str) -> list[dict]:
    section = _player_section(text, "top3")
    if not section:
        return []
    findings: list[dict] = []
    for match in _TOP3_ITEM_RE.finditer(section):
        title, rest = _split_label_value(match.group(1))
        rest, ids = _drill_ids_in(rest)
        item = _finding(title, rest, ids)
        if item is None:
            continue
        findings.append(item)
        if len(findings) >= FINDINGS_LIMIT:
            break
    return findings


def _findings_from_observations(text: str) -> list[dict]:
    starts = list(_OBS_START_RE.finditer(text))
    ranked: list[tuple[int, dict]] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[match.start() : end]
        heading = re.search(r"\n#{2,3}\s", block)
        if heading:
            block = block[: heading.start()]
        observation = _labeled(block, "Наблюдение", "Observation")
        problem = _labeled(block, "Проблема / плюс", "Issue / plus", "Проблема")
        recommendation = _labeled(block, "Рекомендация", "Recommendation")
        severity = _labeled(block, "Критичность", "Severity")
        if _is_strength(severity):
            continue
        recommendation, ids = _drill_ids_in(recommendation)
        item = _finding(problem or observation, recommendation, ids)
        if item is None:
            continue
        ranked.append((_severity_rank(severity), item))
    ranked.sort(key=lambda row: row[0])
    return [item for _, item in ranked[:FINDINGS_LIMIT]]


def _findings_from_markdown(text: str) -> list[dict]:
    return _findings_from_top3(text) or _findings_from_observations(text)


def parse_report(text: str) -> ParsedReport:
    """Достаёт scores/focus/drills/findings и секции summary/next_video."""
    if not text:
        return ParsedReport(text="")

    candidates = _extract_json_candidates(text)
    meta: dict = {}
    for data in candidates:
        if any(k in data for k in ("scores", "skills", "focus", "drills", "drill_ids", "findings")):
            meta = data
            break

    scores = _normalize_scores(meta.get("scores") or meta.get("skills") or {})
    focus = str(meta.get("focus") or "").strip()
    drill_ids = _normalize_drill_ids(meta.get("drills") or meta.get("drill_ids") or [])

    cleaned = text
    for match in _JSON_BLOCK_RE.finditer(text):
        cleaned = cleaned.replace(match.group(0), "")
    cleaned = cleaned.strip()
    body = cleaned or text.strip()

    findings = _normalize_findings(meta.get("findings"))
    if not findings:
        findings = _findings_from_markdown(body)

    return ParsedReport(
        text=body,
        scores=scores,
        focus=focus,
        drill_ids=drill_ids,
        findings=findings,
        summary=_player_section(body, "summary"),
        next_video=_player_section(body, "next_video"),
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
