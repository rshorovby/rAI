import survey
from i18n import t


def test_build_survey_keyboard_marks_selected():
    kb = survey.build_survey_keyboard("ru", {"record", "forgot"})
    labels = [row[0].text for row in kb.inline_keyboard[:-1]]
    assert any("✅" in label and "корте" in label for label in labels)
    assert kb.inline_keyboard[-1][0].callback_data == "sv:done"


def test_toggle_option_in_keyboard():
    kb = survey.build_survey_keyboard("en", set())
    assert kb.inline_keyboard[0][0].callback_data == "sv:t:record"


def test_is_coach_survey_command():
    assert survey.is_coach_survey_command("/опрос")
    assert survey.is_coach_survey_command("опрос")
    assert survey.is_coach_survey_command("/survey")
    assert not survey.is_coach_survey_command("Привет")


def test_format_selected_summary():
    text = survey.format_selected_summary("ru", ["tech", "forgot"], "нет корта")
    assert "Технические" in text
    assert "Забыл" in text
    assert "нет корта" in text


def test_survey_state_helpers():
    session = {}
    assert not survey.is_survey_active(session)
    survey.set_survey_state(
        session,
        {"type": survey.SURVEY_TYPE_NO_VIDEO, "step": survey.STEP_OTHER_TEXT},
    )
    assert survey.is_survey_active(session)
    assert survey.is_survey_other_pending(session)
    survey.set_survey_state(session, None)
    assert not survey.is_survey_active(session)


def test_i18n_survey_intro_ru():
    assert "видео" in t("ru", "survey_no_video_intro").lower()
