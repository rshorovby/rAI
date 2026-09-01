from prompts import (
    FOLLOW_UP_SYSTEM_PROMPT_BASE,
    SYSTEM_PROMPT_BASE,
    USER_PROMPT_EN,
    USER_PROMPT_RU,
    build_analysis_prompt,
    build_video_context_block,
)


def test_prompts_assistant_not_coach_persona():
    assert "You are an AI tennis-technique assistant" in SYSTEM_PROMPT_BASE
    assert "human staff coach is in charge" in SYSTEM_PROMPT_BASE
    assert "Gemini" not in SYSTEM_PROMPT_BASE
    assert not SYSTEM_PROMPT_BASE.startswith("You are an experienced tennis coach")
    assert (
        "You are the same AI tennis-technique assistant" in FOLLOW_UP_SYSTEM_PROMPT_BASE
    )
    assert "Gemini" not in FOLLOW_UP_SYSTEM_PROMPT_BASE
    assert "не от лица тренера" in USER_PROMPT_RU
    assert "not as the coach" in USER_PROMPT_EN


def test_user_prompt_requires_next_video_section():
    assert "## Следующее видео" in USER_PROMPT_RU
    assert "## Next video" in USER_PROMPT_EN


def test_no_comment_returns_base_prompt_ru():
    assert build_analysis_prompt("ru") == USER_PROMPT_RU
    assert build_analysis_prompt("ru", None) == USER_PROMPT_RU


def test_no_comment_returns_base_prompt_en():
    assert build_analysis_prompt("en") == USER_PROMPT_EN


def test_empty_comment_returns_base_prompt():
    assert build_analysis_prompt("ru", "   ") == USER_PROMPT_RU


def test_comment_is_included():
    result = build_analysis_prompt("ru", "болит локоть")
    assert "болит локоть" in result
    assert USER_PROMPT_RU in result


def test_comment_is_stripped():
    result = build_analysis_prompt("ru", "  форхенд  ")
    assert '"форхенд"' in result


def test_german_uses_english_template_with_language_rule():
    result = build_analysis_prompt("de")
    assert USER_PROMPT_EN in result
    assert "German" in result


def test_video_context_adds_stroke_rubric():
    result = build_analysis_prompt(
        "ru",
        video_context={"stroke": "forehand", "look": "contact"},
    )
    assert "УТОЧНЕНИЕ ОТ ИГРОКА" in result
    assert "форхенд" in result
    assert "расхождение" in result.lower() or "другой удар" in result.lower()
    assert USER_PROMPT_RU in result


def test_rally_stroke_rubric():
    result = build_analysis_prompt(
        "ru",
        video_context={"stroke": "rally", "look": "general"},
    )
    assert "серия ударов" in result or "розыгрыш" in result
    assert "Rally" in result or "rally" in result.lower()


def test_video_context_block_empty_without_answers():
    assert build_video_context_block(None) == ""
    assert build_video_context_block({}) == ""
    assert build_video_context_block({"stroke": None, "look": None}) == ""
