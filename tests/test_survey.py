import survey
from i18n import t


def test_build_survey_keyboard_marks_selected():
    kb = survey.build_survey_keyboard(
        "ru", survey.SURVEY_TYPE_NO_VIDEO, {"record", "forgot"}
    )
    labels = [row[0].text for row in kb.inline_keyboard[:-1]]
    assert any("✅" in label and "корте" in label for label in labels)
    assert kb.inline_keyboard[-1][0].callback_data == "sv:done"


def test_build_onboarding_survey_keyboard():
    kb = survey.build_survey_keyboard("ru", survey.SURVEY_TYPE_NO_ONBOARDING, set())
    assert "долго" in kb.inline_keyboard[0][0].text.lower()


def test_is_coach_survey_command():
    assert survey.is_coach_survey_command("/опрос")
    assert survey.is_coach_survey_command("опрос")
    assert not survey.is_coach_survey_command("Привет")


def test_format_selected_summary_no_video():
    text = survey.format_selected_summary(
        "ru", survey.SURVEY_TYPE_NO_VIDEO, ["tech", "forgot"], "нет корта"
    )
    assert "Технические" in text
    assert "нет корта" in text


def test_format_selected_summary_no_onboarding():
    text = survey.format_selected_summary(
        "ru", survey.SURVEY_TYPE_NO_ONBOARDING, ["long", "privacy"]
    )
    assert "долго" in text.lower()
    assert "личной" in text.lower()


def test_survey_state_helpers():
    session = {}
    assert not survey.is_survey_active(session)
    survey.set_survey_state(
        session,
        {
            "type": survey.SURVEY_TYPE_NO_ONBOARDING,
            "step": survey.STEP_OTHER_TEXT,
        },
    )
    assert survey.is_survey_active(session)
    assert survey.is_survey_other_pending(session)


def test_i18n_survey_intros():
    assert "видео" in t("ru", "survey_no_video_intro").lower()
    assert "start" in t("ru", "survey_no_onboarding_intro").lower()
