"""Чеклист форхенда включён по умолчанию. FOREHAND_CHECKLIST=0 его снимает."""

from prompts import (
    USER_PROMPT_EN,
    USER_PROMPT_RU,
    build_analysis_prompt,
    build_system_prompt,
)

_HEADER = "ADDITIONAL OBSERVATION CHECKLIST: FOREHAND"
_OLD_RUBRIC = "Forehand checklist (prioritize visible items)"


def test_flag_off_leaves_the_live_prompt_unchanged(monkeypatch):
    monkeypatch.setenv("FOREHAND_CHECKLIST", "0")
    monkeypatch.delenv("STRUCTURED_ANALYSIS_V2", raising=False)
    system = build_system_prompt("ru", stroke="forehand")
    user = build_analysis_prompt("ru", video_context={"stroke": "forehand"})
    assert _HEADER not in system
    assert _OLD_RUBRIC in user
    assert USER_PROMPT_RU in user


def test_default_appends_checklist_after_the_forehand_reference(monkeypatch):
    monkeypatch.delenv("FOREHAND_CHECKLIST", raising=False)
    monkeypatch.delenv("STRUCTURED_ANALYSIS_V2", raising=False)
    system = build_system_prompt("ru")
    assert system.index("БАЗА ЗНАНИЙ") < system.index(_HEADER)
    assert "only when a forehand drive is visible" in system
    assert "Do not score a slice with these items." in system
    assert 'do not write "not visible"' in system
    assert "insufficient data does not apply" in system
    assert "forward through the ball" in system
    assert "A low-to-high path by itself is not an error." in system
    assert (
        "waist to chest is the reference only for a comfortable ball height" in system
    )
    assert "stiff wrist for the whole swing" in system
    assert "The report language follows the player." in system


def test_checklist_is_the_same_text_for_every_language(monkeypatch):
    monkeypatch.delenv("FOREHAND_CHECKLIST", raising=False)
    monkeypatch.delenv("STRUCTURED_ANALYSIS_V2", raising=False)
    ru = build_system_prompt("ru", stroke="forehand")
    en = build_system_prompt("en", stroke="forehand")
    assert ru[ru.index(_HEADER) :] == en[en.index(_HEADER) :]


def test_flag_on_keeps_the_report_contract_and_drops_the_short_rubric(monkeypatch):
    monkeypatch.setenv("FOREHAND_CHECKLIST", "1")
    monkeypatch.delenv("STRUCTURED_ANALYSIS_V2", raising=False)
    user = build_analysis_prompt("ru", video_context={"stroke": "forehand"})
    assert _OLD_RUBRIC not in user
    assert "## Краткое резюме" in user
    assert "## Топ-3 приоритета для тренировки" in user
    assert '"primary_segment"' in user
    assert "все видимые составные части" in user


def test_flag_on_still_covers_a_forehand_inside_a_rally(monkeypatch):
    monkeypatch.setenv("FOREHAND_CHECKLIST", "1")
    monkeypatch.delenv("STRUCTURED_ANALYSIS_V2", raising=False)
    system = build_system_prompt("ru", stroke="rally")
    user = build_analysis_prompt("ru", video_context={"stroke": "rally"})
    assert _HEADER in system
    assert "Rally / point checklist" in user


def test_flag_on_does_not_replace_another_stroke_rubric(monkeypatch):
    monkeypatch.setenv("FOREHAND_CHECKLIST", "1")
    monkeypatch.setenv("BACKHAND_CHECKLIST", "0")
    monkeypatch.delenv("STRUCTURED_ANALYSIS_V2", raising=False)
    user = build_analysis_prompt("ru", video_context={"stroke": "backhand"})
    assert "Backhand checklist" in user
    assert _OLD_RUBRIC not in user


def test_english_report_keeps_its_sections_and_the_same_checklist(monkeypatch):
    monkeypatch.setenv("FOREHAND_CHECKLIST", "1")
    monkeypatch.delenv("STRUCTURED_ANALYSIS_V2", raising=False)
    system = build_system_prompt("en", stroke="forehand")
    user = build_analysis_prompt("en", video_context={"stroke": "forehand"})
    assert _HEADER in system
    assert _OLD_RUBRIC not in user
    assert USER_PROMPT_EN in user


def test_v2_prompt_gets_the_same_checklist_last(monkeypatch):
    monkeypatch.setenv("FOREHAND_CHECKLIST", "1")
    monkeypatch.setenv("STRUCTURED_ANALYSIS_V2", "1")
    system = build_system_prompt("ru", stroke="forehand")
    assert system.index("## ФОРХЕНД") < system.index(_HEADER)
    assert "a quick return to position." in system
    user = build_analysis_prompt("ru", video_context={"stroke": "forehand"})
    assert _OLD_RUBRIC not in user
    assert "Проанализируй прикреплённое видео" in user
