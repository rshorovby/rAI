import cabinet


def test_format_start_new_and_returning():
    text = cabinet.format_start(1, first_name="Ann", username="ann", is_new=True)
    assert "новый" in text.lower() or "🚀" in text
    assert "1" in text
    text2 = cabinet.format_start(1, first_name="Ann", is_new=False)
    assert "▶️" in text2 or "вернулся" in text2.lower()


def test_format_onboarding_with_profile():
    text = cabinet.format_onboarding_done(
        7, "Уровень: любитель", skipped=False, first_name="Bob"
    )
    assert "Онбординг завершён" in text
    assert "любитель" in text
    skipped = cabinet.format_onboarding_done(7, "профиль пропущен", skipped=True)
    assert "пропущен" in skipped.lower()


def test_format_practice_date():
    text = cabinet.format_practice_date(
        3, date_label="09.08.2026", focus="кисть", drill="shadow"
    )
    assert "09.08.2026" in text
    assert "кисть" in text
    unknown = cabinet.format_practice_date(
        3, date_label="10.08.2026", focus="x", unknown=True
    )
    assert "не знает" in unknown.lower()


def test_format_reminder_kinds():
    assert "давненько" in cabinet.format_reminder(1, kind="inactive").lower()
    assert "перед" in cabinet.format_reminder(1, kind="practice_pre").lower()
    assert "после" in cabinet.format_reminder(1, kind="practice_post").lower()


def test_player_label():
    assert "@ann" in cabinet.player_label(1, "Ann", "ann")
    assert "user 2" in cabinet.player_label(2)


def test_format_video_and_feedback():
    video = cabinet.format_video_uploaded(1, duration=20, comment="форхенд")
    assert "Видео загружено" in video
    assert "20" in video
    assert "форхенд" in video
    assert "Полезно" in cabinet.format_feedback(1, kind="pos")
    assert "Не помогло" in cabinet.format_feedback(1, kind="neg")


def test_format_practice_post_and_followup():
    post = cabinet.format_practice_post(2, answer="yes", focus="кисть", drill="shadow")
    assert "Сделал" in post
    assert "кисть" in post
    q = cabinet.format_followup(3, question="Как держать ракетку?", label="Хват")
    assert "Вопрос" in q
    assert "ракетку" in q
    assert "Хват" in q


def test_format_error_retry_same_focus_reset():
    err = cabinet.format_analysis_failed(1, error="TimeoutError")
    assert "Ошибка" in err
    retry = cabinet.format_analysis_failed(1, retry=True, simple=True)
    assert "простой" in retry.lower() or "⚡" in retry
    same = cabinet.format_same_focus(
        1, focus="кисть", previous_focus="кисть", analyses_count=3
    )
    assert "Повторное" in same
    assert cabinet.same_focus("Кисть вперёд", "кисть вперёд")
    assert not cabinet.same_focus("", "x")
    assert "Сброс" in cabinet.format_profile_reset(9)
