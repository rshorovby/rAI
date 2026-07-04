from onboarding import is_skip_text, match_step_answer


def test_match_level_answer_ru():
    from i18n import t

    assert (
        match_step_answer("ru", "level", t("ru", "ob_opt_level_beginner")) == "beginner"
    )


def test_match_focus_answer_en():
    from i18n import t

    assert match_step_answer("en", "focus", t("en", "ob_opt_focus_serve")) == "serve"


def test_skip_text():
    from i18n import t

    assert is_skip_text("ru", t("ru", "ob_skip")) is True
    assert is_skip_text("en", "random") is False
