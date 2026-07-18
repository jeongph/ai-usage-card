from ai_usage import human, record_cost, parse_date, add_usage


def test_parse_date_seoul():
    # UTC 2026-07-17T16:00Z -> 서울 2026-07-18 01:00
    assert parse_date("2026-07-17T16:00:00.000Z") == "2026-07-18"


def test_parse_date_invalid():
    assert parse_date("nope") is None
    assert parse_date(None) is None


def test_add_usage_accumulates_components_and_cost():
    days = {}
    add_usage(days, "2026-07-17T16:00:00.000Z",
              {"input_tokens": 10, "output_tokens": 20,
               "cache_creation_input_tokens": 5, "cache_read_input_tokens": 100},
              "claude-opus-4-8")
    d = days["2026-07-18"]
    assert d["input"] == 10 and d["output"] == 20
    assert d["cache_creation"] == 5 and d["cache_read"] == 100
    assert d["records"] == 1
    assert d["cost"] > 0


def test_human_billions():
    assert human(7_845_328_754) == "7.8B"


def test_human_millions():
    assert human(10_429_559) == "10.4M"


def test_human_thousands():
    assert human(2_500) == "2.5K"


def test_human_small_is_int_string():
    assert human(500) == "500"


def test_record_cost_unknown_model_is_zero():
    assert record_cost(None, {"input_tokens": 100}) == 0.0
    assert record_cost("gpt-4", {"input_tokens": 100}) == 0.0


def test_record_cost_opus_input_output():
    # opus-4-8: (5.0, 25.0) per 1M
    cost = record_cost("claude-opus-4-8", {"input_tokens": 1_000_000, "output_tokens": 1_000_000})
    assert round(cost, 6) == round(5.0 + 25.0, 6)


def test_record_cost_cache_read_weighted():
    # cache_read 는 input_rate * 0.10
    cost = record_cost("claude-opus-4-8", {"cache_read_input_tokens": 1_000_000})
    assert round(cost, 6) == round(5.0 * 0.10, 6)
