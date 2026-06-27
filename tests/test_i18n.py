from i18n import (
    language_instruction,
    normalize_language_code,
    resolve_ui_lang,
    sync_user_lang,
    t,
)


def test_normalize_language_code():
    assert normalize_language_code("en-US") == "en"
    assert normalize_language_code("ru-RU") == "ru"
    assert normalize_language_code(None) == "en"


def test_resolve_ui_lang():
    assert resolve_ui_lang("ru") == "ru"
    assert resolve_ui_lang("ru-RU") == "ru"
    assert resolve_ui_lang("en") == "en"
    assert resolve_ui_lang("de") == "en"
    assert resolve_ui_lang(None) == "en"


def test_language_instruction_unknown():
    text = language_instruction("de")
    assert "German" in text


def test_sync_user_lang():
    data: dict = {}
    assert sync_user_lang(data, "ru-RU") == "ru"
    assert data["lang"] == "ru"
    assert data["language_code"] == "ru"


def test_t_russian_and_english():
    assert "теннис" in t("ru", "welcome").lower()
    assert "tennis" in t("en", "welcome").lower()


def test_t_unknown_lang_falls_back_to_en():
    assert t("de", "welcome") == t("en", "welcome")
