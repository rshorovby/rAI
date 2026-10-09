"""Режим тренера: карточки учеников в том же боте."""

from typing import Optional

from telegram import KeyboardButton, ReplyKeyboardMarkup

from i18n import UI_LANGS, t

WIZARD_KEY = "trainer_wizard"
SESSION_PLAYER_KEY = "trainer_session_for"
NAME_MAX = 60

_BUTTON_KEYS = (
    "tr_btn_create",
    "tr_btn_select",
    "tr_btn_rename",
    "tr_btn_archive",
    "tr_btn_cancel",
    "tr_btn_back",
    "ob_edit_profile",
    "ob_skip",
    "ob_injuries_none",
)


def topic_title(player_name: str, coach_name: str) -> str:
    title = f"{(player_name or '').strip()} · {(coach_name or '').strip()}"
    return title[:128]


def normalize_name(text: str) -> str:
    return " ".join((text or "").split())


def reserved_name(name: str) -> bool:
    folded = name.casefold()
    for lang in UI_LANGS:
        for key in _BUTTON_KEYS:
            if folded == t(lang, key).casefold():
                return True
    return False


def name_problem(name: str) -> Optional[str]:
    """Ключ i18n, если имя нельзя сохранить."""
    if not name:
        return "tr_name_empty"
    if len(name) > NAME_MAX:
        return "tr_name_long"
    if reserved_name(name):
        return "tr_name_reserved"
    return None


def wizard(user_data: dict) -> Optional[dict]:
    raw = user_data.get(WIZARD_KEY)
    if isinstance(raw, dict) and raw.get("kind"):
        return raw
    return None


def set_wizard(user_data: dict, kind: str, **extra) -> None:
    user_data[WIZARD_KEY] = {"kind": kind, **extra}


def clear_wizard(user_data: dict) -> None:
    user_data.pop(WIZARD_KEY, None)


def blocks_video(user_data: dict) -> bool:
    return wizard(user_data) is not None


def is_cancel_text(lang: str, text: str) -> bool:
    return text in (t(lang, "tr_btn_cancel"), t(lang, "tr_btn_back"))


def menu_keyboard(lang: str, *, has_active: bool) -> ReplyKeyboardMarkup:
    rows = [
        [
            KeyboardButton(t(lang, "tr_btn_create")),
            KeyboardButton(t(lang, "tr_btn_select")),
        ]
    ]
    if has_active:
        rows.append(
            [
                KeyboardButton(t(lang, "ob_edit_profile")),
                KeyboardButton(t(lang, "tr_btn_rename")),
            ]
        )
        rows.append([KeyboardButton(t(lang, "tr_btn_archive"))])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def pick_keyboard(lang: str, names: list) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(name)] for name in names]
    rows.append([KeyboardButton(t(lang, "tr_btn_back"))])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def with_cancel(markup: ReplyKeyboardMarkup, lang: str) -> ReplyKeyboardMarkup:
    rows = [list(row) for row in markup.keyboard]
    rows.append([KeyboardButton(t(lang, "tr_btn_cancel"))])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)
