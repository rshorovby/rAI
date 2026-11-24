from acquisition import is_ios_waitlist, normalize_start_code, source_label


def test_normalize_start_code_accepts_telegram_payload():
    assert normalize_start_code("minsk_mir") == "minsk_mir"
    assert normalize_start_code("  instagram-story ") == "instagram-story"
    assert normalize_start_code("") is None
    assert normalize_start_code(None) is None
    assert normalize_start_code("Минск") is None
    assert normalize_start_code("a" * 65) is None
    assert normalize_start_code("has space") is None


def test_source_label_uses_catalog_or_raw_code():
    assert source_label("minsk_mir") == "Минск-Мир"
    assert source_label("web") == "Сайт"
    assert source_label("web_ios") == "Сайт · iOS"
    assert source_label("web_en") == "Сайт · EN"
    assert source_label("web_ios_en") == "Сайт · iOS EN"
    assert source_label("instagram") == "instagram"
    assert source_label(None) == ""
    assert source_label("") == ""


def test_is_ios_waitlist_matches_site_codes():
    assert is_ios_waitlist("web_ios") is True
    assert is_ios_waitlist("web_ios_en") is True
    assert is_ios_waitlist("web") is False
    assert is_ios_waitlist(None) is False
