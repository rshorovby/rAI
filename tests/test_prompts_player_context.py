from prompts import build_player_context, build_system_prompt


def test_empty_profile_returns_empty():
    assert build_player_context(None) == ""
    assert build_player_context({"skipped": True}) == ""


def test_profile_included_in_system_prompt():
    profile = {
        "level": "recreational",
        "focus": "strokes",
        "hand": "right",
        "injuries": "болит локоть",
        "skipped": False,
    }
    ctx = build_player_context(profile, "ru")
    assert "ПРОФИЛЬ ИГРОКА" in ctx
    assert "болит локоть" in ctx

    system = build_system_prompt("ru", player_profile=profile)
    assert "ПРОФИЛЬ ИГРОКА" in system
    assert "доверяй видео" in system
