from prompts import build_player_context, build_system_prompt


def test_empty_profile_returns_empty():
    assert build_player_context(None) == ""
    assert build_player_context({"skipped": True}) == ""


def test_profile_included_in_system_prompt():
    profile = {
        "level": "recreational",
        "hand": "right",
        "backhand": "two_handed",
        "frequency": "3_4",
        "experience": "y1_3",
        "coaching": "individual",
        "focus": "technique",
        "injuries": "болит локоть",
        "skipped": False,
    }
    ctx = build_player_context(profile, "ru")
    assert "ПРОФИЛЬ ИГРОКА" in ctx
    assert "болит локоть" in ctx
    assert "3–4 раза в неделю" in ctx
    assert "1–3 года" in ctx
    assert "Индивидуально" in ctx
    assert "Двуручный" in ctx
    assert "Всё понемногу" in ctx
    assert "Техника" not in ctx
    assert "Главная цель" in ctx
    assert "не смешивай чеклисты" in ctx
    assert "частоту игры и стаж" in ctx
    assert "Возраст" not in ctx

    system = build_system_prompt("ru", player_profile=profile)
    assert "ПРОФИЛЬ ИГРОКА" in system
    assert "доверяй видео" in system


def test_junior_age_sets_the_yardstick():
    profile = {
        "level": "competitive",
        "hand": "right",
        "backhand": "two_handed",
        "frequency": "3_4",
        "experience": "y1_3",
        "coaching": "individual",
        "injuries": "",
        "skipped": False,
        "age_band": "y8_9",
        "age_recorded_on": "2026-10-09",
    }
    ctx = build_player_context(profile, "ru")
    assert "Возраст: 8–9" in ctx
    assert "orange" in ctx
    assert "не ошибка" in ctx
    assert "2026-10-09" in ctx
    assert "юниорские соревнования" in ctx
    assert "взрослым чеклистом" in ctx


def test_training_stage_stays_inside_the_age_standard():
    profile = {
        "level": "training",
        "hand": "right",
        "skipped": False,
        "age_band": "y8_9",
        "age_recorded_on": "2026-10-09",
    }
    ctx = build_player_context(profile, "ru")
    assert "Тренируется" in ctx
    assert "норму этого возраста" in ctx
    assert "юниорские соревнования" not in ctx


def test_adult_age_keeps_the_adult_yardstick():
    profile = {
        "level": "recreational",
        "hand": "right",
        "skipped": False,
        "age_band": "adult",
        "age_recorded_on": "2026-10-09",
    }
    ctx = build_player_context(profile, "ru")
    assert "Возраст: 18+" in ctx
    assert "взрослая техника" in ctx
    assert "orange" not in ctx
    assert "юниорские" not in ctx


def test_missing_backhand_is_identified_from_video():
    ctx = build_player_context({"level": "beginner", "skipped": False}, "en")
    assert "A bit of everything" in ctx
    assert "not in the profile" in ctx
