"""Онбординг: вопросы о профиле игрока перед разбором."""

from datetime import date
from typing import Any, Optional

from telegram import KeyboardButton, ReplyKeyboardMarkup

from i18n import UI_LANGS, t

ONBOARDING_KEY = "onboarding"
ONBOARDING_ANSWERS_KEY = "onboarding_answers"
PROFILE_RESET_PENDING_KEY = "profile_reset_pending"

STEPS = (
    "level",
    "hand",
    "backhand",
    "frequency",
    "experience",
    "coaching",
    "injuries",
)
TRAINER_STEPS = ("age",) + STEPS

LEVEL_KEYS = ("beginner", "recreational", "advanced", "competitive")
JUNIOR_LEVEL_KEYS = ("starting", "training", "tournaments")
HAND_KEYS = ("right", "left")
BACKHAND_KEYS = ("one_handed", "two_handed")
FREQUENCY_KEYS = ("1", "2", "3_4", "5_plus")
EXPERIENCE_KEYS = ("under_1", "y1_3", "y3_7", "y7_15", "y15_plus")
COACHING_KEYS = ("individual", "group", "both", "none")
AGE_KEYS = ("u8", "y8_9", "y10_11", "y12_13", "y14_15", "y16_17", "adult")
FOCUS_KEYS = ("stability", "power", "technique", "footwork", "serve", "all")
FULL_EVAL_FOCUS = "all"

_STEP_OPTIONS = {
    "level": LEVEL_KEYS,
    "hand": HAND_KEYS,
    "backhand": BACKHAND_KEYS,
    "frequency": FREQUENCY_KEYS,
    "experience": EXPERIENCE_KEYS,
    "coaching": COACHING_KEYS,
    "age": AGE_KEYS,
}


def onboarding_flow(user_data: Optional[dict]) -> str:
    if not user_data:
        return "player"
    state = user_data.get(ONBOARDING_KEY) or {}
    if state.get("flow") == "trainer":
        return "trainer"
    return "player"


def steps_for_flow(flow: str) -> tuple:
    if flow == "trainer":
        return TRAINER_STEPS
    return STEPS


def is_onboarding_active(user_data: dict) -> bool:
    state = user_data.get(ONBOARDING_KEY)
    return bool(state and state.get("step") in TRAINER_STEPS)


def get_onboarding_step(user_data: dict) -> Optional[str]:
    state = user_data.get(ONBOARDING_KEY)
    return state.get("step") if state else None


def start_onboarding_state(user_data: dict, *, flow: str = "player") -> None:
    steps = steps_for_flow(flow)
    user_data[ONBOARDING_KEY] = {"step": steps[0], "flow": flow}
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
    steps = steps_for_flow(onboarding_flow(user_data))
    idx = steps.index(current)
    if idx + 1 >= len(steps):
        return None
    next_step = steps[idx + 1]
    state = user_data.get(ONBOARDING_KEY) or {}
    user_data[ONBOARDING_KEY] = {"step": next_step, "flow": state.get("flow", "player")}
    return next_step


def step_progress(step: str, *, flow: str = "player") -> tuple[int, int]:
    steps = steps_for_flow(flow)
    return steps.index(step) + 1, len(steps)


def is_skip_text(lang: str, text: str) -> bool:
    return text == t(lang, "ob_skip")


def is_injuries_none_text(lang: str, text: str) -> bool:
    return text == t(lang, "ob_injuries_none")


def is_junior_age(age: Optional[str]) -> bool:
    return bool(age) and age != "adult" and age in AGE_KEYS


def level_option_keys(age: Optional[str] = None) -> tuple:
    if is_junior_age(age):
        return JUNIOR_LEVEL_KEYS
    return LEVEL_KEYS


def match_step_answer(
    lang: str, step: str, text: str, *, age: Optional[str] = None
) -> Optional[str]:
    if step == "injuries":
        return None
    if step == "level":
        keys = level_option_keys(age)
    else:
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


def _step_keyboard(
    lang: str, step: str, *, age: Optional[str] = None
) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    if step == "level":
        keys: Optional[tuple] = level_option_keys(age)
    else:
        keys = _STEP_OPTIONS.get(step)
    if keys:
        rows = _rows_of_two(lang, step, keys)
    elif step == "injuries":
        rows = [[KeyboardButton(t(lang, "ob_injuries_none"))]]

    rows.append([KeyboardButton(t(lang, "ob_skip"))])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


def onboarding_keyboard(
    lang: str, step: str, *, age: Optional[str] = None
) -> ReplyKeyboardMarkup:
    return _step_keyboard(lang, step, age=age)


def profile_actions_keyboard(
    lang: str, current: Optional[str] = None
) -> ReplyKeyboardMarkup:
    def _lang_button(code: str, key: str) -> KeyboardButton:
        label = t(lang, key)
        if current == code:
            label = f"{label} ✓"
        return KeyboardButton(label)

    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(t(lang, "ob_edit_profile"))],
            [KeyboardButton(t(lang, "ob_reset_profile"))],
            [
                _lang_button("ru", "profile_btn_lang_ru"),
                _lang_button("en", "profile_btn_lang_en"),
            ],
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


def language_choice(text: str) -> Optional[str]:
    cleaned = text.replace(" ✓", "").strip()
    for lang in UI_LANGS:
        if cleaned == t(lang, "profile_btn_lang_ru"):
            return "ru"
        if cleaned == t(lang, "profile_btn_lang_en"):
            return "en"
    return None


def build_profile_dict(answers: dict[str, Any], *, skipped: bool = False) -> dict:
    profile = {
        "level": answers.get("level"),
        "hand": answers.get("hand"),
        "backhand": answers.get("backhand"),
        "frequency": answers.get("frequency"),
        "experience": answers.get("experience"),
        "coaching": answers.get("coaching"),
        "focus": FULL_EVAL_FOCUS,
        "injuries": answers.get("injuries", ""),
        "skipped": skipped,
    }
    if "age" in answers:
        band = answers.get("age") or None
        recorded = answers.get("age_recorded_on")
        if band and not recorded:
            recorded = date.today().isoformat()
        profile["age_band"] = band
        profile["age_recorded_on"] = recorded if band else None
    return profile
