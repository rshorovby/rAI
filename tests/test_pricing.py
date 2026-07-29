from pricing import Usage, cost_for_usage, estimate_cost, usage_from_response


def test_estimate_cost_pro():
    cost = estimate_cost(8500, 4500, 0, "gemini-3.1-pro-preview")
    assert 0.07 < cost < 0.08


def test_thinking_counts_as_output():
    without = estimate_cost(1000, 1000, 0, "gemini-3.5-flash")
    with_think = estimate_cost(1000, 1000, 1000, "gemini-3.5-flash")
    assert with_think > without


def test_usage_from_response_object():
    class Meta:
        prompt_token_count = 100
        candidates_token_count = 50
        thoughts_token_count = 20

    class Resp:
        usage_metadata = Meta()

    usage = usage_from_response(Resp(), "gemini-3.5-flash")
    assert usage == Usage(100, 50, 20, "gemini-3.5-flash")
    assert cost_for_usage(usage) > 0


def test_usage_missing_meta():
    class Resp:
        usage_metadata = None

    usage = usage_from_response(Resp())
    assert usage.input_tokens == 0
