from errors import format_analysis_error, is_model_overloaded


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
    assert "тренер" in msg.lower()
    assert "gemini" not in msg.lower()


def test_503_unavailable_en():
    msg = format_analysis_error(
        Exception("503 UNAVAILABLE. This model is currently experiencing high demand."),
        lang="en",
    )
    assert "overloaded" in msg.lower()
    assert "coach" in msg.lower()
    assert "gemini" not in msg.lower()


def test_504_deadline_is_overloaded():
    exc = Exception(
        "ServerError: 504 DEADLINE_EXCEEDED. "
        "{'error': {'code': 504, 'message': 'Deadline expired before "
        "operation could complete.', 'status': 'DEADLINE_EXCEEDED'}}"
    )
    assert is_model_overloaded(exc)
    msg = format_analysis_error(exc, lang="ru")
    assert "перегружен" in msg.lower()
    assert "тренер" in msg.lower()


def test_is_model_overloaded():
    assert is_model_overloaded(Exception("ServerError: 503 UNAVAILABLE. high demand"))
    assert is_model_overloaded(TimeoutError("timeout"))
    assert not is_model_overloaded(Exception("Invalid API key"))


def test_500_internal():
    msg = format_analysis_error(Exception("500 INTERNAL"), lang="en")
    assert "temporary" in msg.lower() or "minute" in msg.lower()


def test_region_error_ru():
    msg = format_analysis_error(Exception("User location is not supported"), lang="ru")
    assert "регион" in msg.lower()


def test_api_key_error_en():
    msg = format_analysis_error(Exception("Invalid API key"), lang="en")
    assert "key" in msg.lower()


def test_timeout_error_maps_to_overloaded():
    msg = format_analysis_error(TimeoutError(), lang="ru")
    assert "перегружен" in msg.lower()


def test_generic_error():
    msg = format_analysis_error(Exception("unknown"), lang="en")
    assert "could not" in msg.lower()
