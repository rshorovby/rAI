from prompts import build_coach_context


def test_empty_history_returns_empty_string():
    assert build_coach_context([]) == ""


def test_single_session_included():
    history = [
        {
            "created_at": "01 Jan 2025",
            "summary": "Любитель. Слабый форхенд.",
            "top3": "1. Форхенд\n2. Ноги\n3. Подача",
        }
    ]
    result = build_coach_context(history)
    assert "Сессия 1" in result
    assert "Любитель. Слабый форхенд." in result
    assert "Форхенд" in result


def test_multiple_sessions_all_present():
    history = [
        {"created_at": f"0{i} Jan 2025", "summary": f"Summary {i}", "top3": ""}
        for i in range(1, 4)
    ]
    result = build_coach_context(history)
    for i in range(1, 4):
        assert f"Summary {i}" in result


def test_progress_hint_in_output():
    history = [{"created_at": "01 Jan 2025", "summary": "Улучшение ног.", "top3": ""}]
    result = build_coach_context(history)
    assert "прогресс" in result.lower() or "улучшилось" in result.lower()


def test_no_top3_doesnt_crash():
    history = [{"created_at": "01 Jan 2025", "summary": "Просто резюме.", "top3": ""}]
    result = build_coach_context(history)
    assert "Просто резюме." in result
