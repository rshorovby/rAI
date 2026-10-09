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
# «поднос» / waiter нельзя ни на каком ударе. Остальное — только подача:
# модель называет хватку и открытую струнную поверхность, даже когда блок это запрещает.
_PHRASE_RE = re.compile(r"поднос|waiter", re.IGNORECASE)
_SERVE_RACKET_RE = re.compile(
    r"(?:"
    r"(?<![A-Za-zА-Яа-яЁё])(?:хват\w*|continental\w*|континенталь\w*)"
    r"|струн\w*"
    r"|ракет\w*\s+на\s+ребр\w*"
    r"|на\s+ребр\w*"
    r"|ребр\w*(?:\s+\w+){0,2}\s+ракет\w*"
    r")",
    re.IGNORECASE,
)
_SENTENCE_RE = re.compile(r"[^.!?\n]+(?:[.!?]+|\n|$)", re.DOTALL)

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
    "slice": {
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

    _drop_serve_racket_orientation(payload, notes)

    if not payload.get("findings"):
        blocking.append("findings пустой при теннисе")
    if not payload.get("observations"):
        blocking.append("observations пустой при теннисе")

    _timecodes(payload, duration_sec, notes)
    _focus_checks(payload, downgrade_missing_evidence, notes)
    _axes(payload, notes)
    _catalog(payload, set(drill_ids or []), notes)
    return blocking, notes, payload


def racket_orientation_leak(text: str, *, serve: bool) -> bool:
    """Хватка и открытая струнная поверхность. На подаче — целиком, иначе только «поднос»."""
    if not text:
        return False
    if _PHRASE_RE.search(text):
        return True
    return bool(serve and _SERVE_RACKET_RE.search(text))


def redact_racket_orientation(text: str, *, serve: bool) -> str:
    """Убирает предложения про хватку и ориентацию. Остальной текст сохраняет."""
    if not racket_orientation_leak(text, serve=serve):
        return text
    lines = []
    for line in text.splitlines():
        if not racket_orientation_leak(line, serve=serve):
            lines.append(line)
            continue
        kept = "".join(
            sentence
            for sentence in _SENTENCE_RE.findall(line)
            if sentence.strip() and not racket_orientation_leak(sentence, serve=serve)
        ).strip()
        if kept and not re.fullmatch(r"\d+\.?", kept):
            lines.append(kept)
    return "\n".join(lines).strip()


def _drop_serve_racket_orientation(payload: dict, notes: list) -> None:
    if payload.get("primary_segment") != "serve":
        return
    kept_obs = []
    for item in payload.get("observations") or []:
        if not isinstance(item, dict):
            continue
        seen = redact_racket_orientation(
            str(item.get("what_is_seen") or ""), serve=True
        )
        if not seen:
            notes.append("наблюдение подачи: ориентация ракетки снята")
            continue
        if seen != item.get("what_is_seen"):
            notes.append("наблюдение подачи: ориентация ракетки снята")
            item["what_is_seen"] = seen
        kept_obs.append(item)
    payload["observations"] = kept_obs

    payload["remarks"] = _without_racket_items(
        payload.get("remarks"),
        ("observation", "why_it_matters", "recommendation"),
        "замечание подачи",
        notes,
    )
    payload["findings"] = _without_racket_items(
        payload.get("findings"),
        ("problem", "recommendation", "detail", "practice"),
        "приоритет подачи",
        notes,
    )
    payload["issue_tags"] = [
        tag for tag in (payload.get("issue_tags") or []) if tag != "grip"
    ]
    for key in ("summary", "focus", "next_video"):
        raw = str(payload.get(key) or "")
        cleaned = redact_racket_orientation(raw, serve=True)
        if cleaned != raw:
            notes.append(f"{key}: ориентация ракетки снята")
            payload[key] = cleaned
    video = payload.get("video")
    if isinstance(video, dict):
        note = str(video.get("mismatch_note") or "")
        cleaned = redact_racket_orientation(note, serve=True)
        if cleaned != note:
            video["mismatch_note"] = cleaned
    for item in payload.get("focus_checks") or []:
        if isinstance(item, dict):
            item["evidence"] = redact_racket_orientation(
                str(item.get("evidence") or ""), serve=True
            )


def _without_racket_items(items, fields: tuple, kind: str, notes: list) -> list:
    kept = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        if any(
            racket_orientation_leak(str(item.get(field) or ""), serve=True)
            for field in fields
        ):
            notes.append(f"{kind}: ориентация ракетки снята")
            continue
        if "issue_tags" in item:
            item["issue_tags"] = [
                tag for tag in item.get("issue_tags") or [] if tag != "grip"
            ]
        kept.append(item)
    return kept


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
