"""Онбординг: вопросы о профиле игрока перед разбором."""

from typing import Any, Optional

from telegram import KeyboardButton, ReplyKeyboardMarkup

from i18n import UI_LANGS, t

ONBOARDING_KEY = "onboarding"
ONBOARDING_ANSWERS_KEY = "onboarding_answers"
PROFILE_RESET_PENDING_KEY = "profile_reset_pending"

STEPS = (
    "level",
    "hand",
    "frequency",
    "experience",
    "coaching",
    "focus",
    "injuries",
)

LEVEL_KEYS = ("beginner", "recreational", "advanced", "competitive")
HAND_KEYS = ("right", "left")
FREQUENCY_KEYS = ("1", "2", "3_4", "5_plus")
EXPERIENCE_KEYS = ("under_1", "y1_3", "y3_7", "y7_15", "y15_plus")
COACHING_KEYS = ("individual", "group", "both", "none")
FOCUS_KEYS = ("stability", "power", "technique", "footwork", "serve", "all")

_STEP_OPTIONS = {
    "level": LEVEL_KEYS,
    "hand": HAND_KEYS,
    "frequency": FREQUENCY_KEYS,
    "experience": EXPERIENCE_KEYS,
    "coaching": COACHING_KEYS,
    "focus": FOCUS_KEYS,
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


def step_progress(step: str) -> tuple[int, int]:
    return STEPS.index(step) + 1, len(STEPS)


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


def _rows_of_two(
    lang: str, step: str, keys: tuple[str, ...]
) -> list[list[KeyboardButton]]:
    rows: list[list[KeyboardButton]] = []
    for i in range(0, len(keys), 2):
        chunk = keys[i : i + 2]
        rows.append([KeyboardButton(option_label(lang, step, k)) for k in chunk])
    return rows


def _step_keyboard(lang: str, step: str) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    keys = _STEP_OPTIONS.get(step)
    if keys:
        rows = _rows_of_two(lang, step, keys)
    elif step == "injuries":
        rows = [[KeyboardButton(t(lang, "ob_injuries_none"))]]

    rows.append([KeyboardButton(t(lang, "ob_skip"))])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


def onboarding_keyboard(lang: str, step: str) -> ReplyKeyboardMarkup:
    return _step_keyboard(lang, step)


def profile_actions_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(t(lang, "ob_edit_profile"))],
            [KeyboardButton(t(lang, "ob_reset_profile"))],
        ],
        resize_keyboard=True,
    )


def profile_edit_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return profile_actions_keyboard(lang)


def profile_reset_confirm_keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(t(lang, "profile_reset_confirm_yes"))],
            [KeyboardButton(t(lang, "profile_reset_confirm_no"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def set_reset_pending(user_data: dict) -> None:
    user_data[PROFILE_RESET_PENDING_KEY] = True


def is_reset_pending(user_data: dict) -> bool:
    return bool(user_data.get(PROFILE_RESET_PENDING_KEY))


def clear_reset_pending(user_data: dict) -> None:
    user_data.pop(PROFILE_RESET_PENDING_KEY, None)


def is_edit_profile_text(text: str) -> bool:
    for lang in UI_LANGS:
        if text == t(lang, "ob_edit_profile"):
            return True
    return False


def is_reset_profile_text(text: str) -> bool:
    for lang in UI_LANGS:
        if text == t(lang, "ob_reset_profile"):
            return True
    return False


def is_reset_confirm_yes(text: str) -> bool:
    for lang in UI_LANGS:
        if text == t(lang, "profile_reset_confirm_yes"):
            return True
    return False


def is_reset_confirm_no(text: str) -> bool:
    for lang in UI_LANGS:
        if text == t(lang, "profile_reset_confirm_no"):
            return True
    return False


def build_profile_dict(answers: dict[str, Any], *, skipped: bool = False) -> dict:
    return {
        "level": answers.get("level"),
        "hand": answers.get("hand"),
        "frequency": answers.get("frequency"),
        "experience": answers.get("experience"),
        "coaching": answers.get("coaching"),
        "focus": answers.get("focus"),
        "injuries": answers.get("injuries", ""),
        "skipped": skipped,
    }
