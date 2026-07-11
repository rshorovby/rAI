"""Уточнение перед разбором: что на видео и на чём сфокусироваться."""

from typing import Any, Optional

from telegram import KeyboardButton, ReplyKeyboardMarkup

from i18n import t

INTAKE_KEY = "video_intake"
INTAKE_ANSWERS_KEY = "video_intake_answers"

STEPS = ("stroke", "look")

STROKE_KEYS = (
    "forehand",
    "backhand",
    "serve",
    "volley",
    "footwork",
    "rally",
)
LOOK_KEYS = (
    "technique",
    "footwork",
    "contact",
    "general",
)

_STEP_OPTIONS = {
    "stroke": STROKE_KEYS,
    "look": LOOK_KEYS,
}


def is_intake_active(user_data: dict) -> bool:
    state = user_data.get(INTAKE_KEY)
    return bool(state and state.get("step") in STEPS)


def get_intake_step(user_data: dict) -> Optional[str]:
    state = user_data.get(INTAKE_KEY)
    return state.get("step") if state else None


def start_intake_state(user_data: dict) -> None:
    user_data[INTAKE_KEY] = {"step": "stroke"}
    user_data[INTAKE_ANSWERS_KEY] = {}


def clear_intake_state(user_data: dict) -> None:
    user_data.pop(INTAKE_KEY, None)
    user_data.pop(INTAKE_ANSWERS_KEY, None)


def get_intake_answers(user_data: dict) -> dict:
    return user_data.setdefault(INTAKE_ANSWERS_KEY, {})


def advance_intake_step(user_data: dict) -> Optional[str]:
    current = get_intake_step(user_data)
    if not current:
        return None
    idx = STEPS.index(current)
    if idx + 1 >= len(STEPS):
        return None
    next_step = STEPS[idx + 1]
    user_data[INTAKE_KEY] = {"step": next_step}
    return next_step


def is_intake_skip_text(lang: str, text: str) -> bool:
    return text == t(lang, "vi_skip")


def match_intake_answer(lang: str, step: str, text: str) -> Optional[str]:
    keys = _STEP_OPTIONS.get(step, ())
    for key in keys:
        if text == t(lang, f"vi_opt_{step}_{key}"):
            return key
    return None


def intake_option_label(lang: str, step: str, key: str) -> str:
    return t(lang, f"vi_opt_{step}_{key}")


def intake_value_label(lang: str, field: str, value: Optional[str]) -> str:
    if not value:
        return "—"
    key = f"vi_val_{field}_{value}"
    label = t(lang, key)
    return label if label != key else value


def intake_keyboard(lang: str, step: str) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    if step == "stroke":
        rows = [
            [
                KeyboardButton(intake_option_label(lang, step, STROKE_KEYS[0])),
                KeyboardButton(intake_option_label(lang, step, STROKE_KEYS[1])),
            ],
            [
                KeyboardButton(intake_option_label(lang, step, STROKE_KEYS[2])),
                KeyboardButton(intake_option_label(lang, step, STROKE_KEYS[3])),
            ],
            [
                KeyboardButton(intake_option_label(lang, step, STROKE_KEYS[4])),
                KeyboardButton(intake_option_label(lang, step, STROKE_KEYS[5])),
            ],
        ]
    elif step == "look":
        rows = [
            [
                KeyboardButton(intake_option_label(lang, step, LOOK_KEYS[0])),
                KeyboardButton(intake_option_label(lang, step, LOOK_KEYS[1])),
            ],
            [
                KeyboardButton(intake_option_label(lang, step, LOOK_KEYS[2])),
                KeyboardButton(intake_option_label(lang, step, LOOK_KEYS[3])),
            ],
        ]

    rows.append([KeyboardButton(t(lang, "vi_skip"))])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


def build_video_context(answers: dict[str, Any]) -> dict[str, Optional[str]]:
    return {
        "stroke": answers.get("stroke"),
        "look": answers.get("look"),
    }
