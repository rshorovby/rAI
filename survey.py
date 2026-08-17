"""Опрос «почему не отправили видео» — multi-select inline."""

from __future__ import annotations

from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from i18n import t

SURVEY_TYPE_NO_VIDEO = "no_video"
SURVEY_STATE_KEY = "survey"
STEP_SELECT = "select"
STEP_OTHER_TEXT = "other_text"

OPTION_KEYS = (
    "record",
    "tech",
    "forgot",
    "doubt",
    "howto",
    "shy",
    "other",
)

COACH_SURVEY_COMMANDS = frozenset(
    {
        "/survey",
        "/опрос",
        "опрос",
        "survey",
    }
)


def is_coach_survey_command(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    first = normalized.split()[0]
    return first in COACH_SURVEY_COMMANDS


def option_label(lang: str, key: str) -> str:
    return t(lang, f"survey_opt_{key}")


def build_survey_keyboard(lang: str, selected: set[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for key in OPTION_KEYS:
        mark = "✅ " if key in selected else ""
        rows.append(
            [
                InlineKeyboardButton(
                    f"{mark}{option_label(lang, key)}",
                    callback_data=f"sv:t:{key}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                t(lang, "survey_btn_done"),
                callback_data="sv:done",
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def format_selected_summary(
    lang: str, selected: list[str], other_text: str = ""
) -> str:
    lines = [option_label(lang, key) for key in OPTION_KEYS if key in selected]
    if other_text.strip():
        lines.append(f"{option_label(lang, 'other')}: {other_text.strip()}")
    return "\n".join(f"• {line}" for line in lines)


def get_survey_state(session: dict) -> Optional[dict]:
    state = session.get(SURVEY_STATE_KEY)
    return state if isinstance(state, dict) else None


def set_survey_state(session: dict, state: Optional[dict]) -> None:
    if state:
        session[SURVEY_STATE_KEY] = state
    else:
        session.pop(SURVEY_STATE_KEY, None)


def is_survey_active(session: dict) -> bool:
    state = get_survey_state(session)
    return bool(state and state.get("type") == SURVEY_TYPE_NO_VIDEO)


def is_survey_other_pending(session: dict) -> bool:
    state = get_survey_state(session)
    return bool(
        state
        and state.get("type") == SURVEY_TYPE_NO_VIDEO
        and state.get("step") == STEP_OTHER_TEXT
    )
