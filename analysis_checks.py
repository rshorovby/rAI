"""Бизнес-проверки structured output и текст, который видит игрок."""

import copy
import logging
import re
from pathlib import Path
from typing import Optional

from issue_tags import ISSUE_TAGS

logger = logging.getLogger(__name__)

TIMECODE_RE = re.compile(r"^\d{1,2}:\d{2}$")
_TIMECODE_IN_TEXT_RE = re.compile(r"\d{1,2}:\d{2}")
_AUTHORS = ("Николаев", "Джумок", "Feel Tennis")

# Оси, которые схема принимает, но для сегмента не отдаются в отчёт.
ALLOWED_AXES = {
    "serve": {"toss", "preparation", "leg_drive", "contact", "follow_through"},
    "forehand": {
        "preparation",
        "leg_drive",
        "contact",
        "follow_through",
        "footwork",
        "balance",
    },
    "backhand": {
        "preparation",
        "leg_drive",
        "contact",
        "follow_through",
        "footwork",
        "balance",
    },
    "rally": {
        "preparation",
        "leg_drive",
        "contact",
        "follow_through",
        "footwork",
        "balance",
    },
    "volley": {"preparation", "contact", "footwork", "balance"},
    "footwork": {"footwork", "balance", "preparation"},
}

_ARRAY_KEYS = (
    "observations",
    "remarks",
    "scores",
    "focus_checks",
    "findings",
    "issue_tags",
    "drills",
    "detected_segments",
)


def apply_checks(
    data: dict,
    *,
    duration_sec: Optional[float] = None,
    drill_ids: Optional[list] = None,
    downgrade_missing_evidence: bool = True,
) -> tuple:
    """Возвращает (блокирующие, заметки, исправленную копию)."""
    payload = copy.deepcopy(data)
    notes = []
    blocking = []
    visible = ((payload.get("video") or {}).get("visible_content")) or ""
    if visible == "not_tennis":
        for key in _ARRAY_KEYS:
            if payload.get(key):
                notes.append(f"not_tennis: очищен {key}")
                payload[key] = []
        return blocking, notes, payload

    if not payload.get("findings"):
        blocking.append("findings пустой при теннисе")
    if not payload.get("observations"):
        blocking.append("observations пустой при теннисе")

    _timecodes(payload, duration_sec, notes)
    _focus_checks(payload, downgrade_missing_evidence, notes)
    _axes(payload, notes)
    _catalog(payload, set(drill_ids or []), notes)
    return blocking, notes, payload


def player_text_issues(markdown: str) -> dict:
    """Подстроки, которых не должно быть в тексте игрока. Метаданные не проверяются."""
    body = markdown.split("## Метаданные", 1)[0]
    lowered = body.lower()
    slugs = []
    for slug in _leak_slugs():
        if re.search(rf"(?<![A-Za-z0-9-]){re.escape(slug)}(?![A-Za-z0-9-])", body):
            slugs.append(slug)
    if "[[" in body:
        slugs.append("[[")
    authors = [name for name in _AUTHORS if name.lower() in lowered]
    return {
        "phrase": ("поднос" in lowered) or ("waiter" in lowered),
        "slug_leak": slugs,
        "author_leak": authors,
    }


def _timecodes(payload: dict, duration_sec: Optional[float], notes: list) -> None:
    for key in ("observations", "remarks", "findings"):
        for index, item in enumerate(payload.get(key) or []):
            if not isinstance(item, dict):
                continue
            stamp = str(item.get("t") or "")
            if not TIMECODE_RE.match(stamp):
                notes.append(f"таймкод {key}[{index}]={stamp!r}")
                continue
            if duration_sec is None:
                continue
            if _seconds(stamp) > duration_sec + 1:
                notes.append(f"таймкод {stamp} длиннее ролика")


def _focus_checks(payload: dict, downgrade: bool, notes: list) -> None:
    detected = set(payload.get("detected_segments") or [])
    for item in payload.get("focus_checks") or []:
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        evidence = str(item.get("evidence") or "")
        if (
            downgrade
            and status in ("improved", "worse")
            and not _TIMECODE_IN_TEXT_RE.search(evidence)
        ):
            item["status"] = "not_visible"
            notes.append(f"фокус {item.get('stroke')}: нет evidence, not_visible")
        if item.get("stroke") not in detected and item.get("status") != "not_visible":
            item["status"] = "not_visible"
            notes.append(f"фокус {item.get('stroke')}: удара нет в detected_segments")


def _axes(payload: dict, notes: list) -> None:
    allowed = ALLOWED_AXES.get(payload.get("primary_segment") or "")
    if allowed is None:
        return
    kept = []
    for item in payload.get("scores") or []:
        axis = (item or {}).get("axis")
        if axis not in allowed:
            notes.append(f"ось {axis} снята")
            continue
        kept.append(item)
    payload["scores"] = kept


def _catalog(payload: dict, allowed_drills: set, notes: list) -> None:
    tags = set(ISSUE_TAGS)
    payload["issue_tags"] = _keep(payload.get("issue_tags"), tags, "тег", notes)
    payload["drills"] = _keep(payload.get("drills"), allowed_drills, "drill", notes)
    for item in payload.get("findings") or []:
        if not isinstance(item, dict):
            continue
        item["issue_tags"] = _keep(item.get("issue_tags"), tags, "тег", notes)
        item["drill_ids"] = _keep(item.get("drill_ids"), allowed_drills, "drill", notes)


def _keep(values, allowed: set, kind: str, notes: list) -> list:
    kept = []
    for value in values or []:
        if value in allowed:
            kept.append(value)
        else:
            notes.append(f"{kind} {value} вне реестра")
    return kept


def _seconds(stamp: str) -> int:
    minutes, seconds = stamp.split(":")
    return int(minutes) * 60 + int(seconds)


def _leak_slugs() -> list:
    slugs = set(ISSUE_TAGS)
    wiki = Path(__file__).resolve().parent / "knowledge" / "wiki"
    if wiki.is_dir():
        slugs.update(path.stem for path in wiki.rglob("*.md"))
    return sorted(slugs, key=len, reverse=True)
