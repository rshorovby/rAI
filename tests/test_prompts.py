from prompts import USER_PROMPT_EN, USER_PROMPT_RU, build_analysis_prompt


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
