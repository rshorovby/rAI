from datetime import date

from onboarding import (
    STEPS,
    TRAINER_STEPS,
    advance_step,
    build_profile_dict,
    get_onboarding_step,
    is_skip_text,
    match_step_answer,
    onboarding_flow,
    onboarding_keyboard,
    start_onboarding_state,
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


def test_player_flow_does_not_ask_age():
    data = {}
    start_onboarding_state(data)
    assert onboarding_flow(data) == "player"
    assert get_onboarding_step(data) == "level"
    assert "age" not in STEPS


def test_trainer_flow_asks_age_first():
    from i18n import t

    data = {}
    start_onboarding_state(data, flow="trainer")
    assert TRAINER_STEPS[0] == "age"
    assert get_onboarding_step(data) == "age"
    assert step_progress("age", flow="trainer") == (1, 8)
    assert advance_step(data) == "level"
    assert onboarding_flow(data) == "trainer"
    assert step_progress("level", flow="trainer") == (2, 8)
    assert match_step_answer("ru", "age", t("ru", "ob_opt_age_y8_9")) == "y8_9"
    assert match_step_answer("en", "age", t("en", "ob_opt_age_adult")) == "adult"
    labels = [
        btn.text for row in onboarding_keyboard("ru", "age").keyboard for btn in row
    ]
    assert "8–9" in labels
    assert "10–11" in labels
    assert "18+" in labels


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
    assert "age_band" not in profile


def test_build_profile_dict_records_trainer_age():
    profile = build_profile_dict(
        {
            "age": "y8_9",
            "level": "beginner",
            "hand": "right",
            "backhand": "two_handed",
            "frequency": "2",
            "experience": "under_1",
            "coaching": "individual",
            "injuries": "",
        }
    )
    assert profile["age_band"] == "y8_9"
    assert profile["age_recorded_on"] == date.today().isoformat()


def test_skip_text():
    from i18n import t

    assert is_skip_text("ru", t("ru", "ob_skip")) is True
    assert is_skip_text("en", "random") is False
