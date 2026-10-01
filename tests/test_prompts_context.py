from prompts import (
    build_coach_context,
    build_coach_correction_block,
    build_system_prompt,
)


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
    result = build_coach_context(history, "ru")
    assert "Сессия 1" in result
    assert "Любитель. Слабый форхенд." in result
    assert "Форхенд" in result


def test_multiple_sessions_all_present():
    history = [
        {"created_at": f"0{i} Jan 2025", "summary": f"Summary {i}", "top3": ""}
        for i in range(1, 4)
    ]
    result = build_coach_context(history, "en")
    for i in range(1, 4):
        assert f"Summary {i}" in result


def test_progress_hint_in_output():
    history = [{"created_at": "01 Jan 2025", "summary": "Улучшение ног.", "top3": ""}]
    result = build_coach_context(history, "ru")
    assert "прогресс" in result.lower() or "улучшилось" in result.lower()


def test_no_top3_doesnt_crash():
    history = [{"created_at": "01 Jan 2025", "summary": "Просто резюме.", "top3": ""}]
    result = build_coach_context(history, "ru")
    assert "Просто резюме." in result


def test_serve_history_does_not_carry_racket_face():
    from prompts import build_foci_block

    history = [
        {
            "created_at": "01 Oct 2026",
            "stroke": "serve",
            "summary": "Поднос официанта. Подброс низкий.",
            "top3": "1. Континентальная хватка\n2. Выше подброс",
            "focus": "замах ребром ракетки",
        }
    ]
    result = build_coach_context(history, "ru").lower()
    for token in ("поднос", "хват", "ребр", "континент"):
        assert token not in result
    assert "подброс низкий" in result
    assert "выше подброс" in result

    forehand = build_coach_context(
        [
            {
                "created_at": "01 Oct 2026",
                "stroke": "forehand",
                "summary": "Восточная хватка. Контакт впереди.",
                "top3": "",
            }
        ],
        "ru",
    )
    assert "Восточная хватка" in forehand

    foci = build_foci_block(
        [
            {"stroke": "serve", "focus": "континентальная хватка"},
            {"stroke": "forehand", "focus": "восточная хватка"},
            {"stroke": "serve", "focus": "подброс выше"},
        ],
        "ru",
    )
    assert "континенталь" not in foci.lower()
    assert "восточная хватка" in foci
    assert "подброс выше" in foci


def test_correction_block_empty_without_delta():
    assert build_coach_correction_block([]) == ""
    assert build_coach_correction_block([{"draft_text": "x", "delta_text": ""}]) == ""


def test_correction_block_includes_approved():
    corrections = [
        {
            "scope": "approved",
            "draft_text": "Точка контакта впереди. Главное — встретить мяч.",
            "delta_text": "",
        }
    ]
    block = build_coach_correction_block(corrections, "ru")
    assert "нажал ОК" in block
    assert "Точка контакта" in block
    assert "AI-помощник" in block
    system = build_system_prompt("ru", coach_corrections=corrections)
    assert "нажал ОК" not in system
    assert "ЭТАЛОН ТРЕНЕРА" not in system


def test_correction_block_in_system_prompt():
    corrections = [
        {
            "draft_text": "AI: поздний замах",
            "delta_text": "Главное — встретить мяч впереди",
        }
    ]
    block = build_coach_correction_block(corrections, "ru")
    assert "ЭТАЛОН ТРЕНЕРА" in block
    assert "для всех" in block.lower()
    assert "поздний замах" in block
    assert "встретить мяч" in block
    assert "вычеркнул" in block
    system = build_system_prompt("ru", coach_corrections=corrections)
    assert "ЭТАЛОН ТРЕНЕРА" not in system


def test_history_is_personal_and_comes_after_the_coach_standard():
    history = [
        {
            "created_at": "2026-09-20 10:00:00",
            "summary": "Поздний разворот.",
            "top3": "",
            "stroke": "forehand",
            "focus": "разворот",
            "scores": {"contact": 4},
            "drill_ids": ["unit-turn-shadow"],
        }
    ]
    corrections = [
        {
            "scope": "player",
            "draft_text": "черновик",
            "delta_text": "у него двуручный бэкхенд",
        }
    ]
    text = build_system_prompt(
        "ru",
        history,
        coach_corrections=corrections,
        prompt_context={"today": "2026-09-26", "session_count": 6},
    )
    assert "форхенд" in text
    assert "6 дн. назад" in text
    assert "видео №7" in text
    assert "unit-turn-shadow" in text
    assert "больше чем на 1" in text
    assert "факты об этом игроке" not in text
    assert "ЭТАЛОН ТРЕНЕРА" not in text
    assert "у него двуручный бэкхенд" not in text


def test_correction_block_splits_global_and_player():
    corrections = [
        {
            "scope": "global",
            "draft_text": "глобальный черновик",
            "delta_text": "глобальная версия тренера",
        },
        {
            "scope": "player",
            "draft_text": "личный черновик",
            "delta_text": "личная версия тренера",
        },
    ]
    block = build_coach_correction_block(corrections, "ru")
    assert "Глобальные правки" in block
    assert "по этому игроку" in block.lower()
    assert "глобальная версия" in block
    assert "личная версия" in block
