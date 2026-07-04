"""Онбординг: вопросы о профиле игрока перед разбором."""

from typing import Any, Optional

from telegram import KeyboardButton, ReplyKeyboardMarkup

from i18n import UI_LANGS, t

ONBOARDING_KEY = "onboarding"
ONBOARDING_ANSWERS_KEY = "onboarding_answers"

STEPS = ("level", "focus", "hand", "injuries")

LEVEL_KEYS = ("beginner", "recreational", "advanced", "competitive")
FOCUS_KEYS = ("strokes", "serve", "footwork", "all")
HAND_KEYS = ("right", "left")

_STEP_OPTIONS = {
    "level": LEVEL_KEYS,
    "focus": FOCUS_KEYS,
    "hand": HAND_KEYS,
}


def is_onboarding_active(user_data: dict) -> bool:
    state = user_data.get(ONBOARDING_KEY)
    return bool(state and state.get("step") in STEPS)


def get_onboarding_step(user_data: dict) -> Optional[str]:
    state = user_data.get(ONBOARDING_KEY)
    return state.get("step") if state else None


def start_onboarding_state(user_data: dict) -> None:
    user_data[ONBOARDING_KEY] = {"step": "level"}
    user_data[ONBOARDING_ANSWERS_KEY] = {}


def clear_onboarding_state(user_data: dict) -> None:
    user_data.pop(ONBOARDING_KEY, None)
    user_data.pop(ONBOARDING_ANSWERS_KEY, None)


def get_onboarding_answers(user_data: dict) -> dict:
    return user_data.setdefault(ONBOARDING_ANSWERS_KEY, {})


def advance_step(user_data: dict) -> Optional[str]:
    current = get_onboarding_step(user_data)
    if not current:
        return None
    idx = STEPS.index(current)
    if idx + 1 >= len(STEPS):
        return None
    next_step = STEPS[idx + 1]
    user_data[ONBOARDING_KEY] = {"step": next_step}
    return next_step


def is_skip_text(lang: str, text: str) -> bool:
    return text == t(lang, "ob_skip")


def is_injuries_none_text(lang: str, text: str) -> bool:
    return text == t(lang, "ob_injuries_none")


def match_step_answer(lang: str, step: str, text: str) -> Optional[str]:
    if step == "injuries":
        return None
    keys = _STEP_OPTIONS.get(step, ())
    for key in keys:
        if text == t(lang, f"ob_opt_{step}_{key}"):
            return key
    return None


def option_label(lang: str, step: str, key: str) -> str:
    return t(lang, f"ob_opt_{step}_{key}")


def profile_value_label(lang: str, field: str, value: Optional[str]) -> str:
    if not value:
        return "—"
    key = f"ob_val_{field}_{value}"
    label = t(lang, key)
    return label if label != key else value


def _step_keyboard(lang: str, step: str) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    if step == "level":
        rows = [
            [
                KeyboardButton(option_label(lang, step, LEVEL_KEYS[0])),
                KeyboardButton(option_label(lang, step, LEVEL_KEYS[1])),
            ],
            [
                KeyboardButton(option_label(lang, step, LEVEL_KEYS[2])),
                KeyboardButton(option_label(lang, step, LEVEL_KEYS[3])),
            ],
        ]
    elif step == "focus":
        rows = [
            [
                KeyboardButton(option_label(lang, step, FOCUS_KEYS[0])),
                KeyboardButton(option_label(lang, step, FOCUS_KEYS[1])),
            ],
            [
                KeyboardButton(option_label(lang, step, FOCUS_KEYS[2])),
                KeyboardButton(option_label(lang, step, FOCUS_KEYS[3])),
            ],
        ]
    elif step == "hand":
        rows = [
            [
                KeyboardButton(option_label(lang, step, HAND_KEYS[0])),
                KeyboardButton(option_label(lang, step, HAND_KEYS[1])),
            ],
        ]
    elif step == "injuries":
        rows = [[KeyboardButton(t(lang, "ob_injuries_none"))]]

    rows.append([KeyboardButton(t(lang, "ob_skip"))])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


def onboarding_keyboard(lang: str, step: str) -> ReplyKeyboardMarkup:
    return _step_keyboard(lang, step)


def profile_edit_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(t(lang, "ob_edit_profile"))]],
        resize_keyboard=True,
    )


def is_edit_profile_text(text: str) -> bool:
    for lang in UI_LANGS:
        if text == t(lang, "ob_edit_profile"):
            return True
    return False


def build_profile_dict(answers: dict[str, Any], *, skipped: bool = False) -> dict:
    return {
        "level": answers.get("level"),
        "focus": answers.get("focus"),
        "hand": answers.get("hand"),
        "injuries": answers.get("injuries", ""),
        "skipped": skipped,
    }
