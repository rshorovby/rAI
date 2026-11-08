"""Кабинет тренера: статусы заявки и клавиатуры игрока."""

from __future__ import annotations

import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import video_clip
from analysis_dialog import parse_report
from i18n import report_section_headers, t

STATUS_QUEUED = "queued"
STATUS_IN_REVIEW = "in_review"
STATUS_AI_SENT = "ai_sent"
STATUS_AI_FAILED = "ai_failed"
STATUS_SENT_COACH = "sent_coach"
STATUS_SENT_FALLBACK = "sent_fallback"
STATUS_CANCELLED = "cancelled"

# Устаревшие действия (кнопки убраны; оставлены для совместимости callback).
ACTION_SEND = "send"
ACTION_REPLACE = "replace"
ACTION_NOTES = "notes"

# Режимы кабинета: ответ игроку vs эталон для ИИ vs закрепление черновика.
ACTION_REPLY_PLAYER = "reply"
ACTION_FIX_AI = "fix"
ACTION_FIX_AI_CONT = "fix_cont"
ACTION_APPROVE = "ok"
VALID_COACH_ACTIONS = (ACTION_REPLY_PLAYER, ACTION_FIX_AI)
FIX_AI_PENDING = (ACTION_FIX_AI, ACTION_FIX_AI_CONT)

_CABINET_DROP_HEADERS = (
    "Краткое резюме",
    "Brief summary",
    "Следующее видео",
    "Next video",
    "Метаданные (служебно)",
    "Метаданные",
    "Metadata (internal)",
    "Metadata",
)

PLAYER_MSG_PENDING_KEY = "player_coach_message_pending"
# Пока ключ задан, текст игрока уходит тренеру, а не в диалог с ботом.
COACH_REPLY_MODE_KEY = "coach_reply_mode"


def compose_final_report(
    draft_text: str,
    *,
    coach_notes: str = "",
    replacement: str = "",
    fallback: bool = False,
    lang: str = "ru",
) -> str:
    body = (replacement or draft_text or "").strip()
    notes = (coach_notes or "").strip()
    parts = []
    if fallback:
        parts.append(t(lang, "review_fallback_banner"))
    if notes:
        parts.append(t(lang, "review_coach_notes_block", notes=notes))
    if body:
        parts.append(body)
    return "\n\n".join(parts).strip()


def keyboard_message_coach(lang: str, player_id: int = 0) -> InlineKeyboardMarkup:
    data = f"rvp:msg:{int(player_id)}" if player_id else "rvp:msg"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t(lang, "review_btn_message_coach"),
                    callback_data=data,
                )
            ]
        ]
    )


def keyboard_reply_to_coach(
    lang: str, *, player_id: int, via_trainer: bool
) -> InlineKeyboardMarkup:
    data = f"rvp:reply:{int(player_id)}" if via_trainer else "rvp:reply"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t(lang, "review_btn_reply_coach"),
                    callback_data=data,
                )
            ]
        ]
    )


def keyboard_continue_with_bot(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t(lang, "review_btn_continue_bot"),
                    callback_data="rvp:bot",
                )
            ]
        ]
    )


RATING_OK = ACTION_APPROVE
RATING_ADDED = "added"
RATING_MISS = "miss"
VALID_RATINGS = (RATING_OK, RATING_ADDED, RATING_MISS)

TAG_PRIORITY = "priority"
TAG_HALLUCINATION = "hallucination"
TAG_MISSED = "missed"
TAG_TONE = "tone"
TAG_HOMEWORK = "homework"
VALID_TAGS = (
    TAG_PRIORITY,
    TAG_HALLUCINATION,
    TAG_MISSED,
    TAG_TONE,
    TAG_HOMEWORK,
)

_ACTION_BUTTONS = (
    (ACTION_REPLY_PLAYER, "💬 Ответить игроку"),
    (ACTION_FIX_AI, "✏️ Поправить AI"),
)


def _strip_h2_sections(report: str, headers: tuple) -> str:
    body = report
    for header in headers:
        pattern = rf"(?:^|\n)##\s*{re.escape(header)}\s*\n.*?(?=\n##\s|\Z)"
        body = re.sub(pattern, "\n", body, count=1, flags=re.DOTALL | re.IGNORECASE)
    return body.strip()


def strip_cabinet_draft(text: str) -> str:
    """Полный разбор без резюме, «следующего видео» и метаданных."""
    body = (text or "").strip()
    if not body:
        return ""
    stripped = _strip_h2_sections(body, _CABINET_DROP_HEADERS)
    stripped = re.sub(
        r"\n```json\s*\n.*?```\s*$",
        "",
        stripped,
        count=1,
        flags=re.DOTALL | re.IGNORECASE,
    ).strip()
    if stripped and stripped != body:
        return stripped
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if len(paras) >= 3:
        return "\n\n".join(paras[1:-1])
    return stripped or body


def _cabinet_headers(report: str, language_code: str) -> dict:
    for code in (language_code or "", "ru", "en"):
        if not code:
            continue
        headers = report_section_headers(code)
        marker = f"## {headers['video']}"
        if marker in report or f"## {headers['categories']}" in report:
            return headers
    base = "ru" if (language_code or "").startswith("ru") else "en"
    return report_section_headers(base)


def _observation_window(chunk: str):
    lowered = chunk.lower()
    if "недостаточно данных" in lowered or "insufficient data" in lowered:
        return None
    if not (
        "**наблюдение:**" in lowered
        or "**критичность:**" in lowered
        or "**observation:**" in lowered
    ):
        return None
    return video_clip.find_span_sec(chunk)


def cabinet_draft_parts(text: str, language_code: str = "ru") -> list:
    """Сообщения черновика: видео, каждое наблюдение, топ-3.

    Элемент: {"text": markdown, "window": (start, end) | None}.
    window есть только у наблюдения, из которого можно вырезать клип.
    """
    raw = (text or "").strip()
    if not raw:
        return []
    headers = _cabinet_headers(raw, language_code)
    sections = parse_report(raw, language_code)
    parts: list = []
    video = (sections.get("video") or "").strip()
    if video:
        parts.append({"text": f"## {headers['video']}\n{video}", "window": None})

    first_category = True
    for category in sections.get("categories") or []:
        title = (category.get("title") or "").strip()
        body = (category.get("body") or "").strip()
        chunks = [
            chunk.strip() for chunk in re.split(r"\n\s*\n", body) if chunk.strip()
        ]
        for chunk in chunks:
            lines = []
            if first_category:
                lines.append(f"## {headers['categories']}")
                first_category = False
            if title:
                lines.append(f"### {title}")
            lines.append(chunk)
            parts.append(
                {"text": "\n".join(lines), "window": _observation_window(chunk)}
            )

    top3 = (sections.get("top3") or "").strip()
    if top3:
        parts.append({"text": f"## {headers['top3']}\n{top3}", "window": None})
    if parts:
        return parts
    fallback = strip_cabinet_draft(raw) or raw
    return [{"text": fallback, "window": None}]


def coach_action_keyboard(job_id: int, action: str = "") -> InlineKeyboardMarkup:
    row = []
    active = ACTION_FIX_AI if action in FIX_AI_PENDING else action
    for key, label in _ACTION_BUTTONS:
        mark = "· " if active == key else ""
        row.append(
            InlineKeyboardButton(
                f"{mark}{label}",
                callback_data=f"ce:a:{job_id}:{key}",
            )
        )
    ok_mark = "· " if active == ACTION_APPROVE else ""
    ok_row = [
        InlineKeyboardButton(
            f"{ok_mark}✅ ОК",
            callback_data=f"ce:a:{job_id}:{ACTION_APPROVE}",
        )
    ]
    return InlineKeyboardMarkup([row, ok_row])


# Alias для старых импортов/тестов.
keyboard_player_waiting = keyboard_message_coach


def topic_title(user_id: int, first_name: str = "", username: str = "") -> str:
    name = (first_name or "").strip() or (f"@{username}" if username else "Игрок")
    # Telegram topic title max 128
    title = f"{name} · {user_id}"
    return title[:128]
