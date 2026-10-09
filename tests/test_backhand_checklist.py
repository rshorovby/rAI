"""Чеклист бэкхенда включён по умолчанию. BACKHAND_CHECKLIST=0 его снимает."""

from prompts import (
    USER_PROMPT_EN,
    USER_PROMPT_RU,
    build_analysis_prompt,
    build_system_prompt,
)

_HEADER = "ADDITIONAL OBSERVATION CHECKLIST: BACKHAND"
_OLD_RUBRIC = "Backhand checklist:"


def test_flag_off_keeps_the_short_backhand_rubric(monkeypatch):
    monkeypatch.setenv("BACKHAND_CHECKLIST", "0")
    monkeypatch.delenv("STRUCTURED_ANALYSIS_V2", raising=False)
    system = build_system_prompt("ru", stroke="backhand")
    user = build_analysis_prompt("ru", video_context={"stroke": "backhand"})
    assert _HEADER not in system
    assert _OLD_RUBRIC in user
    assert USER_PROMPT_RU in user


def test_default_appends_checklist_for_both_languages(monkeypatch):
    monkeypatch.delenv("BACKHAND_CHECKLIST", raising=False)
    monkeypatch.delenv("STRUCTURED_ANALYSIS_V2", raising=False)
    ru = build_system_prompt("ru", stroke="backhand")
    en = build_system_prompt("en", stroke="backhand")
    assert ru.index("БАЗА ЗНАНИЙ") < ru.index(_HEADER)
    assert ru[ru.index(_HEADER) :] == en[en.index(_HEADER) :]
    assert "two-handed uses section B, one-handed uses section C" in ru
    assert "mirror left and right" in ru
    assert "Do not score a slice with these items." in ru
    assert "Do not require the back to face the net." in ru
    assert "Do not require the chin to sit over the shoulder." in ru
    assert "A low-to-high path by itself is not an error." in ru
    assert "waist to chest is the reference only for a comfortable ball height" in ru
    assert "That is not a stiff wrist for the whole swing." in ru
    assert "standing too close to the ball" in ru


def test_checklist_drops_the_short_rubric_and_keeps_the_report(monkeypatch):
    monkeypatch.delenv("BACKHAND_CHECKLIST", raising=False)
    monkeypatch.delenv("STRUCTURED_ANALYSIS_V2", raising=False)
    ru = build_analysis_prompt("ru", video_context={"stroke": "backhand"})
    en = build_analysis_prompt("en", video_context={"stroke": "backhand"})
    assert _OLD_RUBRIC not in ru
    assert _OLD_RUBRIC not in en
    assert USER_PROMPT_RU in ru
    assert USER_PROMPT_EN in en
    assert "## Краткое резюме" in ru
    assert '"primary_segment"' in ru


def test_forehand_rubric_stays_when_only_backhand_checklist_is_on(monkeypatch):
    monkeypatch.setenv("FOREHAND_CHECKLIST", "0")
    monkeypatch.delenv("BACKHAND_CHECKLIST", raising=False)
    monkeypatch.delenv("STRUCTURED_ANALYSIS_V2", raising=False)
    user = build_analysis_prompt("ru", video_context={"stroke": "forehand"})
    assert "Forehand checklist (prioritize visible items)" in user
    system = build_system_prompt("ru", stroke="forehand")
    assert _HEADER in system


def test_v2_prompt_ends_with_the_backhand_checklist(monkeypatch):
    monkeypatch.delenv("BACKHAND_CHECKLIST", raising=False)
    monkeypatch.setenv("STRUCTURED_ANALYSIS_V2", "1")
    system = build_system_prompt("ru", stroke="backhand")
    assert system.index("## БЭКХЕНД") < system.index(_HEADER)
    assert "a loss of balance." in system
