from errors import format_analysis_error


def test_quota_error():
    msg = format_analysis_error(Exception("429 RESOURCE_EXHAUSTED"))
    assert "квота" in msg.lower()


def test_503_unavailable():
    msg = format_analysis_error(
        Exception("503 UNAVAILABLE. This model is currently experiencing high demand.")
    )
    assert "перегружен" in msg.lower()


def test_500_internal():
    msg = format_analysis_error(Exception("500 INTERNAL"))
    assert "gemini" in msg.lower()


def test_region_error():
    msg = format_analysis_error(Exception("User location is not supported"))
    assert "регион" in msg.lower()


def test_api_key_error():
    msg = format_analysis_error(Exception("Invalid API key"))
    assert "ключ" in msg.lower()


def test_timeout_error():
    msg = format_analysis_error(TimeoutError())
    assert "вовремя" in msg.lower() or "обработать" in msg.lower()


def test_generic_error():
    msg = format_analysis_error(Exception("что-то неизвестное"))
    assert "не удалось" in msg.lower()
