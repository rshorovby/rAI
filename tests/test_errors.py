from errors import format_analysis_error


def test_quota_error_ru():
    msg = format_analysis_error(Exception("429 RESOURCE_EXHAUSTED"), lang="ru")
    assert "квота" in msg.lower()


def test_quota_error_en():
    msg = format_analysis_error(Exception("429 RESOURCE_EXHAUSTED"), lang="en")
    assert "quota" in msg.lower()


def test_503_unavailable_ru():
    msg = format_analysis_error(
        Exception("503 UNAVAILABLE. This model is currently experiencing high demand."),
        lang="ru",
    )
    assert "перегружен" in msg.lower()


def test_503_unavailable_en():
    msg = format_analysis_error(
        Exception("503 UNAVAILABLE. This model is currently experiencing high demand."),
        lang="en",
    )
    assert "overloaded" in msg.lower()


def test_500_internal():
    msg = format_analysis_error(Exception("500 INTERNAL"), lang="en")
    assert "gemini" in msg.lower()


def test_region_error_ru():
    msg = format_analysis_error(Exception("User location is not supported"), lang="ru")
    assert "регион" in msg.lower()


def test_api_key_error_en():
    msg = format_analysis_error(Exception("Invalid API key"), lang="en")
    assert "key" in msg.lower()


def test_timeout_error():
    msg = format_analysis_error(TimeoutError(), lang="ru")
    assert "вовремя" in msg.lower() or "обработать" in msg.lower()


def test_generic_error():
    msg = format_analysis_error(Exception("unknown"), lang="en")
    assert "could not" in msg.lower()
