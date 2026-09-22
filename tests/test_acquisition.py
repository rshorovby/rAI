from acquisition import normalize_start_code, source_label


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
    assert source_label("instagram") == "instagram"
    assert source_label(None) == ""
    assert source_label("") == ""
