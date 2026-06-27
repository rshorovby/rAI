from prompts import USER_PROMPT, build_analysis_prompt


def test_no_comment_returns_base_prompt():
    assert build_analysis_prompt() == USER_PROMPT
    assert build_analysis_prompt(None) == USER_PROMPT


def test_empty_comment_returns_base_prompt():
    assert build_analysis_prompt("   ") == USER_PROMPT


def test_comment_is_included():
    result = build_analysis_prompt("болит локоть")
    assert "болит локоть" in result
    assert USER_PROMPT in result


def test_comment_is_stripped():
    result = build_analysis_prompt("  форхенд  ")
    assert '"форхенд"' in result
