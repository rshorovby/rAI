from analyzer import _is_transient_error


def test_503_is_transient():
    assert _is_transient_error(Exception("503 UNAVAILABLE")) is True


def test_high_demand_is_transient():
    assert (
        _is_transient_error(Exception("This model is experiencing high demand")) is True
    )


def test_500_internal_is_transient():
    assert _is_transient_error(Exception("500 INTERNAL")) is True


def test_quota_is_not_transient():
    assert _is_transient_error(Exception("429 RESOURCE_EXHAUSTED")) is False


def test_api_key_is_not_transient():
    assert _is_transient_error(Exception("Invalid API key")) is False
