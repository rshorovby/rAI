from onboarding import (
    STEPS,
    build_profile_dict,
    is_skip_text,
    match_step_answer,
    step_progress,
)


def test_language_choice_ru_en():
    from onboarding import language_choice, profile_actions_keyboard

    assert language_choice("🇷🇺 Русский") == "ru"
    assert language_choice("🇬🇧 English") == "en"
    assert language_choice("🇷🇺 Русский ✓") == "ru"
    assert language_choice("изменить") is None

    labels = [
        btn.text for row in profile_actions_keyboard("en", "en").keyboard for btn in row
    ]
    assert "🇬🇧 English ✓" in labels
    assert "🇷🇺 Русский" in labels


def test_steps_order():
    assert STEPS == (
        "level",
        "hand",
        "backhand",
        "frequency",
        "experience",
        "coaching",
        "injuries",
    )


def test_step_progress():
    assert step_progress("level") == (1, 7)
    assert step_progress("injuries") == (7, 7)


def test_match_level_answer_ru():
    from i18n import t

    assert (
        match_step_answer("ru", "level", t("ru", "ob_opt_level_beginner")) == "beginner"
    )
    assert (
        match_step_answer("ru", "level", t("ru", "ob_opt_level_competitive"))
        == "competitive"
    )


def test_match_new_steps():
    from i18n import t

    assert match_step_answer("ru", "hand", t("ru", "ob_opt_hand_left")) == "left"
    assert (
        match_step_answer("ru", "frequency", t("ru", "ob_opt_frequency_3_4")) == "3_4"
    )
    assert (
        match_step_answer("en", "experience", t("en", "ob_opt_experience_y7_15"))
        == "y7_15"
    )
    assert (
        match_step_answer("ru", "coaching", t("ru", "ob_opt_coaching_individual"))
        == "individual"
    )
    assert (
        match_step_answer("ru", "backhand", t("ru", "ob_opt_backhand_one_handed"))
        == "one_handed"
    )
    assert (
        match_step_answer("en", "backhand", t("en", "ob_opt_backhand_two_handed"))
        == "two_handed"
    )
    assert match_step_answer("en", "backhand", t("en", "ob_opt_focus_serve")) is None


def test_build_profile_dict_includes_new_fields():
    profile = build_profile_dict(
        {
            "level": "advanced",
            "hand": "right",
            "backhand": "two_handed",
            "frequency": "2",
            "experience": "y3_7",
            "coaching": "group",
            "focus": "power",
            "injuries": "",
        }
    )
    assert profile["frequency"] == "2"
    assert profile["experience"] == "y3_7"
    assert profile["coaching"] == "group"
    assert profile["backhand"] == "two_handed"
    assert profile["focus"] == "all"
    assert profile["skipped"] is False


def test_skip_text():
    from i18n import t

    assert is_skip_text("ru", t("ru", "ob_skip")) is True
    assert is_skip_text("en", "random") is False
