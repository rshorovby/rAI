from pose_runtime import player_line, prompt_text


def test_prompt_lists_contacts_and_count():
    text = prompt_text(
        {"contacts": [{"t": 5.135, "source": "audio"}, {"t": 3.6, "source": "wrist"}]},
        "ru",
    )
    assert "Число ударов: 2" in text
    assert "5,13 с (звук)" in text
    assert "3,60 с (кисть)" in text


def test_prompt_empty_without_contacts():
    assert prompt_text({"contacts": []}, "ru") == ""
    assert prompt_text({"error": "model"}, "en") == ""


def test_player_line_skips_errors_and_names_hits():
    assert player_line({"error": "model"}, "ru") is None
    assert "не выделил" in player_line({"contacts": []}, "ru")
    line = player_line({"contacts": [{"t": 5.135, "source": "audio"}]}, "ru")
    assert line == "Нашёл ударов: 1. Контакт: 5,13 с."


def test_analysis_prompt_includes_pose_brief():
    from prompts import build_analysis_prompt

    text = build_analysis_prompt(
        "ru", video_context={"stroke": "serve", "pose_brief": "ИЗМЕРЕНИЯ ДО РАЗБОРА"}
    )
    assert "ИЗМЕРЕНИЯ ДО РАЗБОРА" in text
    assert "подач" in text.lower() or "Подач" in text or "подача" in text.lower()
