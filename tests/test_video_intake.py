from video_intake import (
    advance_intake_step,
    build_video_context,
    clear_intake_state,
    get_intake_answers,
    get_intake_step,
    is_intake_active,
    is_intake_skip_text,
    match_intake_answer,
    start_intake_state,
)


def test_intake_flow_asks_only_stroke():
    data: dict = {}
    start_intake_state(data)
    assert is_intake_active(data)
    assert get_intake_step(data) == "stroke"

    assert match_intake_answer("ru", "stroke", "🎾 Форхенд") == "forehand"
    get_intake_answers(data)["stroke"] = "forehand"
    assert advance_intake_step(data) is None

    ctx = build_video_context(get_intake_answers(data))
    assert ctx == {"stroke": "forehand", "look": None}


def test_serve_intake_asks_for_the_type():
    data: dict = {}
    start_intake_state(data)
    assert match_intake_answer("ru", "stroke", "🚀 Подача") == "serve"
    get_intake_answers(data)["stroke"] = "serve"
    assert advance_intake_step(data) == "serve_type"
    assert get_intake_step(data) == "serve_type"
    assert match_intake_answer("ru", "serve_type", "Кик") == "kick"
    get_intake_answers(data)["serve_type"] = "kick"
    assert advance_intake_step(data) is None
    ctx = build_video_context(get_intake_answers(data))
    assert ctx["stroke"] == "serve"
    assert ctx["serve_type"] == "kick"


def test_intake_skip_text():
    assert is_intake_skip_text("ru", "⏭ Пропустить — разбери как есть")
    assert is_intake_skip_text("en", "⏭ Skip — analyze as-is")


def test_clear_intake():
    data: dict = {}
    start_intake_state(data)
    clear_intake_state(data)
    assert not is_intake_active(data)
