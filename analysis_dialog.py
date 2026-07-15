"""Диалоговый показ разбора: парсинг секций и inline-кнопки."""

import re
from typing import Any, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from i18n import report_section_headers, t

DIALOG_KEY = "analysis_dialog"

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
    items: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^\s*\d+[.)]\s*(.+)$", line.strip())
        if m:
            items.append(m.group(1).strip())
    return items[:3]


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
    # Ошибки для режима «разбор ошибок» — в порядке приоритета (топ-3).
    errors = list(top3_items)

    return {
        "summary": summary,
        "video": video,
        "categories": categories,
        "top3": top3_body,
        "top3_items": top3_items,
        "errors": errors,
        "next_video": next_video,
        "limitations": limitations,
    }


def start_dialog(
    user_data: dict,
    report: str,
    language_code: str,
    *,
    video_file_id: str,
    video_mime: str,
) -> dict:
    sections = parse_report(report, language_code)
    state = {
        "step": "summary",
        "language_code": language_code,
        "sections": sections,
        "skeleton_shown": False,
        "video_file_id": video_file_id,
        "video_mime": video_mime,
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


def keyboard_summary(lang: str, state: dict) -> InlineKeyboardMarkup:
    rows = [
        [_btn(lang, "dialog_btn_video", "d:video")],
        [_btn(lang, "dialog_btn_errors", "d:errors")],
        [
            _btn(lang, "dialog_btn_cats", "d:cats"),
            _btn(lang, "dialog_btn_top3", "d:top3"),
        ],
    ]
    if not state.get("skeleton_shown"):
        rows.append([_btn(lang, "dialog_btn_skeleton", "d:skeleton")])
    rows.append([_btn(lang, "dialog_btn_finish", "d:finish")])
    return InlineKeyboardMarkup(rows)


def keyboard_after_video(lang: str) -> InlineKeyboardMarkup:
    return _with_summary_row(
        lang,
        [
            [_btn(lang, "dialog_btn_errors", "d:errors")],
            [
                _btn(lang, "dialog_btn_cats", "d:cats"),
                _btn(lang, "dialog_btn_top3", "d:top3"),
            ],
        ],
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


def keyboard_top3(lang: str, state: dict) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    items = state["sections"].get("top3_items") or []
    for i, item in enumerate(items, start=1):
        label = f"{i}. {item}"
        if len(label) > 60:
            label = label[:57] + "…"
        rows.append([InlineKeyboardButton(label, callback_data=f"d:prio:{i}")])
    rows.append(
        [
            _btn(lang, "dialog_btn_drills", "d:drills"),
            _btn(lang, "dialog_btn_next", "d:next"),
        ]
    )
    rows.append([_btn(lang, "dialog_btn_finish", "d:finish")])
    return _with_summary_row(lang, rows)


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


def format_error_card(lang: str, state: dict) -> str:
    errors = state["sections"].get("errors") or []
    idx = int(state.get("error_index") or 0)
    if not errors or idx < 0 or idx >= len(errors):
        return t(lang, "dialog_no_errors")
    n = idx + 1
    total = len(errors)
    return t(lang, "dialog_title_error", n=n, total=total, text=errors[idx])


def current_error_text(state: dict) -> str:
    errors = state["sections"].get("errors") or []
    idx = int(state.get("error_index") or 0)
    if not errors or idx < 0 or idx >= len(errors):
        return ""
    return errors[idx]
