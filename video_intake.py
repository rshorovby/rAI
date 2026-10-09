"""Уточнение перед разбором: какой удар на видео."""

from typing import Any, Optional

from telegram import KeyboardButton, ReplyKeyboardMarkup

from i18n import t

INTAKE_KEY = "video_intake"
INTAKE_ANSWERS_KEY = "video_intake_answers"

STEPS = ("stroke", "serve_type")

STROKE_KEYS = (
    "forehand",
    "backhand",
    "slice",
    "serve",
    "volley",
    "footwork",
    "rally",
)

SERVE_TYPE_KEYS = ("flat", "slice", "kick", "unsure")

_STEP_OPTIONS = {
    "stroke": STROKE_KEYS,
    "serve_type": SERVE_TYPE_KEYS,
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
    if current != "stroke":
        return None
    if get_intake_answers(user_data).get("stroke") != "serve":
        return None
    user_data[INTAKE_KEY] = {"step": "serve_type"}
    return "serve_type"


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
        keys = list(STROKE_KEYS)
        rows = [
            [
                KeyboardButton(intake_option_label(lang, step, key))
                for key in keys[i : i + 2]
            ]
            for i in range(0, len(keys), 2)
        ]
    elif step == "serve_type":
        keys = list(SERVE_TYPE_KEYS)
        rows = [
            [
                KeyboardButton(intake_option_label(lang, step, key))
                for key in keys[i : i + 2]
            ]
            for i in range(0, len(keys), 2)
        ]

    rows.append([KeyboardButton(t(lang, "vi_skip"))])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


def build_video_context(answers: dict[str, Any]) -> dict[str, Optional[str]]:
    context: dict[str, Optional[str]] = {
        "stroke": answers.get("stroke"),
        "look": answers.get("look"),
    }
    serve_type = answers.get("serve_type")
    if serve_type:
        context["serve_type"] = serve_type
    return context
