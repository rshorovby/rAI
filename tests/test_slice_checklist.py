"""Резаный удар в выборе и в чеклисте. SLICE_CHECKLIST=0 снимает только чеклист."""

from i18n import t
from prompts import (
    USER_PROMPT_EN,
    USER_PROMPT_RU,
    build_analysis_prompt,
    build_system_prompt,
)
from video_intake import STROKE_KEYS, intake_keyboard

_HEADER = "ADDITIONAL OBSERVATION CHECKLIST: SLICE"


def test_slice_is_a_stroke_choice():
    assert STROKE_KEYS[2] == "slice"
    ru = intake_keyboard("ru", "stroke")
    labels = [button.text for row in ru.keyboard for button in row]
    assert t("ru", "vi_opt_stroke_slice") in labels
    assert t("en", "vi_opt_stroke_slice") in [
        button.text
        for row in intake_keyboard("en", "stroke").keyboard
        for button in row
    ]


def test_flag_off_removes_the_checklist_but_keeps_the_button(monkeypatch):
    monkeypatch.setenv("SLICE_CHECKLIST", "0")
    monkeypatch.delenv("STRUCTURED_ANALYSIS_V2", raising=False)
    system = build_system_prompt("ru", stroke="slice")
    user = build_analysis_prompt("ru", video_context={"stroke": "slice"})
    assert _HEADER not in system
    assert "резаный удар" in user
    assert USER_PROMPT_RU in user


def test_default_checklist_is_the_same_for_every_language(monkeypatch):
    monkeypatch.delenv("SLICE_CHECKLIST", raising=False)
    monkeypatch.delenv("STRUCTURED_ANALYSIS_V2", raising=False)
    ru = build_system_prompt("ru", stroke="slice")
    en = build_system_prompt("en", stroke="slice")
    assert ru[ru.index(_HEADER) :] == en[en.index(_HEADER) :]
    assert "Do not score a slice with the topspin" in ru
    assert "shoulders stay sideways through contact" in ru
    assert "Do not uncoil the chest to the net" in ru
    assert "judge only if the strings are clearly visible" in ru
    assert "waist to chest is the reference only for a comfortable ball height" in ru
    assert "Do not require a low crouch" in ru
    assert "Skip this item for a forehand slice and for a two-handed slice" in ru
    assert "only when a real rally is visible" in ru
    assert "Do not invent a purpose" in ru
    user = build_analysis_prompt("en", video_context={"stroke": "slice"})
    assert USER_PROMPT_EN in user
    assert "slice, serve" in user
