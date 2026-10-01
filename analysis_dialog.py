"""Диалоговый показ разбора: парсинг секций и inline-кнопки."""

import re
from typing import Any, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from i18n import report_section_headers, t

DIALOG_KEY = "analysis_dialog"

_NOT_PRIORITY = {
    "в этом разборе не в приоритете",
    "not a priority in this review",
}
_RECOMMENDATION_LINE = re.compile(
    r"^\*\*(?:Рекомендация|Recommendation):\*\*.*$",
    re.MULTILINE,
)

_CATEGORY_ALIASES = {
    "техника удара": "stroke",
    "stroke technique": "stroke",
    "передвижение и работа ног": "footwork",
    "movement and footwork": "footwork",
    "позиционирование и баланс": "balance",
    "positioning and balance": "balance",
}


def _extract_h2(report: str, header: str) -> str:
    pattern = rf"##\s*{re.escape(header)}\s*\n(.*?)(?=\n##\s|\Z)"
    m = re.search(pattern, report, re.DOTALL)
    return m.group(1).strip() if m else ""


def _headers_for_report(report: str, language_code: str) -> dict[str, str]:
    primary = report_section_headers(language_code)
    if _extract_h2(report, primary["summary"]):
        return primary
    for alt in ("ru", "en"):
        headers = report_section_headers(alt)
        if _extract_h2(report, headers["summary"]):
            return headers
    return primary


def _parse_categories(body: str) -> list[dict[str, str]]:
    if not body.strip():
        return []
    parts = re.split(r"\n###\s+", "\n" + body)
    categories: list[dict[str, str]] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.splitlines()
        title = lines[0].strip()
        content = "\n".join(lines[1:]).strip()
        if not title:
            continue
        key = _CATEGORY_ALIASES.get(title.lower(), f"cat{len(categories)}")
        categories.append({"key": key, "title": title, "body": content})
    return categories


def _parse_top3_items(body: str) -> list[str]:
    items: list[list[str]] = []
    for line in body.splitlines():
        match = re.match(r"^\s*\d+[.)]\s*(.+)$", line.strip())
        if match:
            items.append([match.group(1).strip()])
        elif items and line.strip():
            items[-1].append(line.strip())
    return ["\n".join(parts) for parts in items][:3]


def parse_report(report: str, language_code: str = "ru") -> dict[str, Any]:
    """Разбирает markdown-отчёт на секции для пошагового показа."""
    headers = _headers_for_report(report, language_code)
    summary = _extract_h2(report, headers["summary"])
    video = _extract_h2(report, headers["video"])
    categories_body = _extract_h2(report, headers["categories"])
    top3_body = _extract_h2(report, headers["top3"])
    next_video = _extract_h2(report, headers["next_video"])
    limitations = _extract_h2(report, headers["limitations"])

    if not summary:
        summary = report.strip()[:600]

    categories = _parse_categories(categories_body)
    top3_items = _parse_top3_items(top3_body)
    remarks = _remarks_from_categories(categories)
    # Старый отчёт без блоков «Наблюдение» по-прежнему ведёт карусель из топ-3.
    errors = list(top3_items)

    return {
        "summary": summary,
        "video": video,
        "categories": categories,
        "top3": top3_body,
        "top3_items": top3_items,
        "errors": errors,
        "remarks": remarks,
        "next_video": next_video,
        "limitations": limitations,
    }


def start_dialog(
    user_data: dict,
    report: str,
    language_code: str,
) -> dict:
    sections = parse_report(report, language_code)
    state = {
        "step": "summary",
        "language_code": language_code,
        "sections": sections,
        "visited_categories": [],
        "error_index": 0,
    }
    user_data[DIALOG_KEY] = state
    return state


def get_dialog(user_data: dict) -> Optional[dict]:
    state = user_data.get(DIALOG_KEY)
    return state if isinstance(state, dict) else None


def clear_dialog(user_data: dict) -> None:
    user_data.pop(DIALOG_KEY, None)


def _btn(lang: str, key: str, callback: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(t(lang, key), callback_data=callback)


def _with_summary_row(
    lang: str, rows: list[list[InlineKeyboardButton]]
) -> InlineKeyboardMarkup:
    rows = list(rows)
    rows.append([_btn(lang, "dialog_btn_back", "d:summary")])
    return InlineKeyboardMarkup(rows)


def keyboard_summary(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [_btn(lang, "dialog_btn_video", "d:video")],
        [_btn(lang, "dialog_btn_top3", "d:top3")],
        [_btn(lang, "dialog_btn_finish", "d:finish")],
    ]
    return InlineKeyboardMarkup(rows)


def keyboard_after_video(lang: str) -> InlineKeyboardMarkup:
    return _with_summary_row(
        lang,
        [[_btn(lang, "dialog_btn_top3", "d:top3")]],
    )


def keyboard_categories(lang: str, state: dict) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for i, cat in enumerate(state["sections"].get("categories") or []):
        rows.append(
            [
                InlineKeyboardButton(
                    cat["title"][:60],
                    callback_data=f"d:cat:{i}",
                )
            ]
        )
    rows.append([_btn(lang, "dialog_btn_top3", "d:top3")])
    return _with_summary_row(lang, rows)


def keyboard_error(lang: str, state: dict) -> InlineKeyboardMarkup:
    errors = state["sections"].get("errors") or []
    idx = int(state.get("error_index") or 0)
    rows: list[list[InlineKeyboardButton]] = [
        [_btn(lang, "dialog_btn_err_deep", "d:err:deep")],
    ]
    if idx + 1 < len(errors):
        rows.append([_btn(lang, "dialog_btn_err_next", "d:err:next")])
    else:
        rows.append([_btn(lang, "dialog_btn_err_done", "d:err:done")])
    rows.append([_btn(lang, "dialog_btn_finish", "d:finish")])
    return _with_summary_row(lang, rows)


def keyboard_after_error_deep(lang: str, state: dict) -> InlineKeyboardMarkup:
    errors = state["sections"].get("errors") or []
    idx = int(state.get("error_index") or 0)
    rows: list[list[InlineKeyboardButton]] = []
    if idx + 1 < len(errors):
        rows.append([_btn(lang, "dialog_btn_err_next", "d:err:next")])
    else:
        rows.append([_btn(lang, "dialog_btn_err_done", "d:err:done")])
    rows.append([_btn(lang, "dialog_btn_finish", "d:finish")])
    return _with_summary_row(lang, rows)


def keyboard_top3(lang: str, _state: dict) -> InlineKeyboardMarkup:
    return _with_summary_row(
        lang,
        [
            [_btn(lang, "dialog_btn_drills", "d:drills")],
            [_btn(lang, "dialog_btn_next", "d:next")],
        ],
    )


def keyboard_after_prio(lang: str) -> InlineKeyboardMarkup:
    return _with_summary_row(
        lang,
        [
            [
                _btn(lang, "dialog_btn_drills", "d:drills"),
                _btn(lang, "dialog_btn_next", "d:next"),
            ],
            [_btn(lang, "dialog_btn_top3", "d:top3")],
        ],
    )


def keyboard_after_drills(lang: str) -> InlineKeyboardMarkup:
    return _with_summary_row(
        lang,
        [
            [
                _btn(lang, "dialog_btn_top3", "d:top3"),
                _btn(lang, "dialog_btn_next", "d:next"),
            ],
            [_btn(lang, "dialog_btn_finish", "d:finish")],
        ],
    )


def keyboard_finish(lang: str) -> InlineKeyboardMarkup:
    return _with_summary_row(
        lang,
        [
            [_btn(lang, "dialog_btn_next", "d:next")],
            [_btn(lang, "dialog_btn_feedback", "d:fb")],
        ],
    )


def keyboard_after_next(lang: str) -> InlineKeyboardMarkup:
    return _with_summary_row(
        lang,
        [
            [_btn(lang, "dialog_btn_ask", "d:ask")],
            [_btn(lang, "dialog_btn_feedback", "d:fb")],
        ],
    )


def format_summary_message(lang: str, state: dict) -> str:
    summary = state["sections"].get("summary") or "—"
    return f"{t(lang, 'dialog_ready')}\n\n{summary}"


def format_section_title(lang: str, title_key: str, body: str) -> str:
    title = t(lang, title_key)
    if not body:
        return f"{title}\n\n{t(lang, 'dialog_section_empty')}"
    return f"{title}\n\n{body}"


def _remarks_from_categories(categories: list) -> list:
    remarks = []
    for category in categories:
        chunks = re.split(r"\n\s*\n", (category.get("body") or "").strip())
        for chunk in chunks:
            text = chunk.strip()
            if not text or text.lower() in _NOT_PRIORITY:
                continue
            if not _is_structured_remark(text):
                continue
            remarks.append(
                {
                    "kind": _remark_kind(text),
                    "card": _RECOMMENDATION_LINE.sub("", text).strip(),
                    "full": text,
                }
            )
    return remarks


def _is_structured_remark(text: str) -> bool:
    lowered = text.lower()
    return (
        "**наблюдение:**" in lowered
        or "**критичность:**" in lowered
        or "недостаточно данных" in lowered
        or "**observation:**" in lowered
        or "insufficient data" in lowered
    )


def _remark_kind(text: str) -> str:
    lowered = text.lower()
    if "недостаточно данных" in lowered or "insufficient data" in lowered:
        return "insufficient"
    if "🟢" in text or "сильная сторона" in lowered or "strength" in lowered:
        return "strength"
    return "remark"


def _severity_emoji(text: str) -> str:
    for emoji in ("🔴", "🟠", "🟡", "🟢"):
        if emoji in text:
            return emoji
    return ""


def keyboard_remark(lang: str, index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[_btn(lang, "dialog_btn_err_deep", f"d:err:deep:{index}")]]
    )


def format_error_card(lang: str, state: dict) -> str:
    remarks = state["sections"].get("remarks") or []
    idx = int(state.get("error_index") or 0)
    if remarks:
        if idx < 0 or idx >= len(remarks):
            return t(lang, "dialog_no_errors")
        remark = remarks[idx]
        label_key = (
            "dialog_label_strength"
            if remark["kind"] == "strength"
            else "dialog_label_remark"
        )
        emoji = _severity_emoji(remark["card"])
        badge = f"{emoji} " if emoji else ""
        return t(
            lang,
            "dialog_note_title",
            badge=badge,
            label=t(lang, label_key),
            n=idx + 1,
            total=len(remarks),
            text=remark["card"],
        )
    errors = state["sections"].get("errors") or []
    if not errors or idx < 0 or idx >= len(errors):
        return t(lang, "dialog_no_errors")
    return t(
        lang,
        "dialog_title_error",
        n=idx + 1,
        total=len(errors),
        text=errors[idx],
    )


def current_error_text(state: dict) -> str:
    remarks = state["sections"].get("remarks") or []
    idx = int(state.get("error_index") or 0)
    if remarks:
        if idx < 0 or idx >= len(remarks):
            return ""
        return remarks[idx]["full"]
    errors = state["sections"].get("errors") or []
    if not errors or idx < 0 or idx >= len(errors):
        return ""
    return errors[idx]


def current_remark_kind(state: dict) -> str:
    remarks = state["sections"].get("remarks") or []
    idx = int(state.get("error_index") or 0)
    if remarks and 0 <= idx < len(remarks):
        return remarks[idx]["kind"]
    return "error"
