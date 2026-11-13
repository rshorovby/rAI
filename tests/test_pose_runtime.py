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
    measured = {
        "contacts": [{"t": 5.135, "source": "audio"}],
        "metrics": {
            "hand": "right",
            "contacts": [{"t": 5.135, "elbow": 155.0, "stance": 0.86}],
            "spread": {},
        },
    }
    assert player_line(measured, "ru") == "Нашёл ударов: 1. Контакт: 5,13 с."
    assert "°" not in player_line(measured, "ru")


def test_analysis_prompt_includes_pose_brief():
    from prompts import build_analysis_prompt

    text = build_analysis_prompt(
        "ru", video_context={"stroke": "serve", "pose_brief": "ИЗМЕРЕНИЯ ДО РАЗБОРА"}
    )
    assert "ИЗМЕРЕНИЯ ДО РАЗБОРА" in text
    assert "подач" in text.lower() or "Подач" in text or "подача" in text.lower()


def test_prompt_adds_angles_for_the_profile_hand():
    from pose_runtime import metrics_for_prompt

    shown = metrics_for_prompt(
        {
            "hand": "right",
            "contacts": [
                {
                    "t": 3.005,
                    "elbow": 154.8,
                    "knee_left": 148.8,
                    "knee_right": 161.3,
                    "stance": 0.86,
                    "contact_above_head": 0.70,
                    "other_above_head": -0.4,
                    "toss_above_head": 0.78,
                    "knee_load": 148.8,
                },
                {
                    "t": 9.585,
                    "elbow": 158.8,
                    "knee_left": 155.4,
                    "knee_right": 166.4,
                    "stance": 0.96,
                    "contact_above_head": 0.47,
                    "other_above_head": -0.2,
                    "toss_above_head": 0.77,
                    "knee_load": 151.4,
                },
            ],
        },
        "serve",
    )
    text = prompt_text(
        {
            "contacts": [
                {"t": 3.005, "source": "audio"},
                {"t": 9.585, "source": "audio"},
            ],
            "metrics": shown,
        },
        "ru",
    )
    assert "локоть правой руки 154,8°" in text
    assert "кисть на 0,70 торса выше носа" in text
    assert "подброс на 0,78 торса выше носа" in text
    assert "колено в загрузке 148,8°" in text
    assert "Разброс: локоть 4°" in text
    assert "Опирайся на эти числа" in text
    assert "ниже другой" not in text


def test_prompt_drops_swapped_serve_arm_and_keeps_stance():
    from pose_runtime import metrics_for_prompt

    shown = metrics_for_prompt(
        {
            "hand": "right",
            "contacts": [
                {
                    "t": 5.135,
                    "elbow": 137.1,
                    "knee_left": 178.7,
                    "knee_right": 175.4,
                    "stance": 0.67,
                    "contact_above_head": -0.61,
                    "other_above_head": 0.9,
                    "toss_above_head": 0.73,
                    "knee_load": 133.2,
                }
            ],
        },
        "serve",
    )
    text = prompt_text(
        {"contacts": [{"t": 5.135, "source": "audio"}], "metrics": shown},
        "ru",
    )
    assert "137" not in text
    assert "178" not in text
    assert "0,73" not in text
    assert "стойка 0,67 торса" in text
    assert "колено в загрузке 133,2°" in text
    assert "кисть из профиля ниже другой" in text


def test_prompt_keeps_groundstroke_arm_below_the_nose():
    from pose_runtime import metrics_for_prompt

    shown = metrics_for_prompt(
        {
            "hand": "left",
            "contacts": [
                {
                    "t": 5.585,
                    "elbow": 178.4,
                    "knee_left": 141.1,
                    "knee_right": 162.1,
                    "stance": 0.85,
                    "contact_above_head": -1.23,
                    "other_above_head": -0.4,
                }
            ],
        },
        "",
    )
    text = prompt_text(
        {"contacts": [{"t": 5.585, "source": "wrist"}], "metrics": shown},
        "en",
    )
    assert "left elbow 178,4°" not in text
    assert "left elbow 178.4°" in text
    assert "wrist 1.23 torso below the nose" in text
    assert "left knee 141.1°" in text
    assert "Spread:" not in text
