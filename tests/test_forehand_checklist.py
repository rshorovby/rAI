"""Чеклист форхенда включён по умолчанию. FOREHAND_CHECKLIST=0 его снимает."""

from prompts import (
    USER_PROMPT_RU,
    build_analysis_prompt,
    build_system_prompt,
)

_HEADER = "ДОПОЛНИТЕЛЬНЫЙ ЧЕКЛИСТ НАБЛЮДЕНИЯ: ФОРХЕНД"
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
    assert "Применяй только если на видео виден форхенд" in system
    assert "не пиши «не видно»" in system
    assert "данных недостаточно" in system
    assert "вперёд через мяч" in system
    assert "Сам по себе путь «снизу вверх» ошибкой не считай." in system
    assert "пояс–грудь — ориентир только для мяча удобной высоты" in system
    assert "жёсткой кистью на всём ударе" in system
    assert "Секции отчёта и JSON остаются прежними." in system


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
    monkeypatch.delenv("STRUCTURED_ANALYSIS_V2", raising=False)
    user = build_analysis_prompt("ru", video_context={"stroke": "backhand"})
    assert "Backhand checklist" in user
    assert _OLD_RUBRIC not in user


def test_english_prompt_ignores_the_flag(monkeypatch):
    monkeypatch.setenv("FOREHAND_CHECKLIST", "1")
    system = build_system_prompt("en", stroke="forehand")
    user = build_analysis_prompt("en", video_context={"stroke": "forehand"})
    assert _HEADER not in system
    assert _OLD_RUBRIC in user


def test_v2_prompt_gets_the_same_checklist_last(monkeypatch):
    monkeypatch.setenv("FOREHAND_CHECKLIST", "1")
    monkeypatch.setenv("STRUCTURED_ANALYSIS_V2", "1")
    system = build_system_prompt("ru", stroke="forehand")
    assert system.index("## ФОРХЕНД") < system.index(_HEADER)
    assert system.strip().endswith("быстрое восстановление позиции.")
    user = build_analysis_prompt("ru", video_context={"stroke": "forehand"})
    assert _OLD_RUBRIC not in user
    assert "Проанализируй прикреплённое видео" in user
