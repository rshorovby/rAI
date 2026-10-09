"""Чеклист подачи включён по умолчанию. SERVE_CHECKLIST=0 его снимает."""

from prompts import USER_PROMPT_RU, build_analysis_prompt, build_system_prompt

_HEADER = "ADDITIONAL OBSERVATION CHECKLIST: SERVE"


def test_flag_off_keeps_the_short_serve_rubric(monkeypatch):
    monkeypatch.setenv("SERVE_CHECKLIST", "0")
    monkeypatch.delenv("STRUCTURED_ANALYSIS_V2", raising=False)
    system = build_system_prompt("ru", stroke="serve")
    user = build_analysis_prompt("ru", video_context={"stroke": "serve"})
    assert _HEADER not in system
    assert "Serve checklist:" in user
    assert USER_PROMPT_RU in user


def test_default_checklist_is_the_same_for_every_language(monkeypatch):
    monkeypatch.delenv("SERVE_CHECKLIST", raising=False)
    monkeypatch.delenv("STRUCTURED_ANALYSIS_V2", raising=False)
    ru = build_system_prompt("ru", stroke="serve")
    en = build_system_prompt("en", stroke="serve")
    assert ru[ru.index(_HEADER) :] == en[en.index(_HEADER) :]
    assert "Do not assess grip or racket-face orientation." in ru
    assert "do not invent it" in ru
    assert "single serve" in ru
    assert "Do not demand maximum power" in ru
    assert "waiter" not in ru[ru.index(_HEADER) :].lower()
    assert "поднос" not in ru[ru.index(_HEADER) :]
    user = build_analysis_prompt(
        "ru", video_context={"stroke": "serve", "serve_type": "kick"}
    )
    assert "кик" in user
    assert "тип не выдумывай" in user
    assert "Serve checklist:" not in user
    assert USER_PROMPT_RU in user
