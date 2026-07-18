from ai_usage import human


def test_human_billions():
    assert human(7_845_328_754) == "7.8B"


def test_human_millions():
    assert human(10_429_559) == "10.4M"


def test_human_thousands():
    assert human(2_500) == "2.5K"


def test_human_small_is_int_string():
    assert human(500) == "500"
