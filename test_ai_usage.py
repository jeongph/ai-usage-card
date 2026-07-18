import json as _json
from datetime import date
from ai_usage import human, record_cost, parse_date, add_usage, render_graph, render_card, aggregate, upsert


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


def test_graph_all_zero_bottom_is_baseline():
    top, bot = render_graph([0] * 30)
    assert bot == "▁" * 30      # 안 쓴 날도 바닥 막대로 꽉 채움
    assert top == ""             # 상단은 전부 비어 rstrip 결과 빈 문자열


def test_graph_length_matches_input():
    top, bot = render_graph([0] * 30)
    assert len(bot) == 30


def test_graph_peak_fills_both_rows():
    vals = [0] * 29 + [100]
    top, bot = render_graph(vals)
    assert bot[-1] == "█"        # 최댓값 -> 하단 꽉
    assert top[-1] == "█"        # 최댓값 -> 상단도 꽉 (h==2)


def test_graph_half_max_only_bottom():
    # 절반 값은 h==1.0 -> 하단 꽉, 상단 비움
    top, bot = render_graph([50, 100] + [0] * 28)
    assert bot[0] == "█"
    assert top[:1] == " "        # 첫 칸 상단 공백


def _mk(day, total, cost):
    # 전량 input 으로 몰아 total 토큰을 맞춘 하루치 레코드
    return {"input": total, "output": 0, "cache_creation": 0,
            "cache_read": 0, "records": 1, "cost": cost}


def test_render_card_has_six_lines_and_markers():
    days = {"2026-07-18": _mk("d", 10_000_000, 2.0),
            "2026-07-15": _mk("d", 100_000_000, 20.0)}
    card = render_card(days, date(2026, 7, 18), "2026-07-18 13:40 KST")
    lines = card.rstrip("\n").split("\n")
    assert len(lines) == 6
    assert lines[0].startswith("📊 ")
    assert lines[1].startswith("🔥 today ")
    assert lines[4].startswith("📅 avg ")
    assert lines[5].startswith("🕐 updated ")


def test_render_card_graph_rows_have_no_text():
    days = {"2026-07-18": _mk("d", 10_000_000, 2.0)}
    card = render_card(days, date(2026, 7, 18), "2026-07-18 13:40 KST")
    top, bot = card.split("\n")[2], card.split("\n")[3]
    # 그래프 줄은 막대/공백만 (알파벳·이모지 없음)
    assert all(ch in " " + "▁▂▃▄▅▆▇█" for ch in top)
    assert all(ch in "▁▂▃▄▅▆▇█" for ch in bot)


def test_render_card_empty():
    assert render_card({}, date(2026, 7, 18), "x") == "(no usage data yet)\n"


def test_aggregate_reads_usage_lines(tmp_path):
    log = tmp_path / "proj" / "s.jsonl"
    log.parent.mkdir(parents=True)
    rows = [
        {"timestamp": "2026-07-17T16:00:00.000Z",
         "message": {"model": "claude-opus-4-8",
                     "usage": {"input_tokens": 10, "output_tokens": 20}}},
        {"type": "summary"},  # usage 없는 줄은 무시
    ]
    log.write_text("\n".join(_json.dumps(r) for r in rows), encoding="utf-8")

    days = aggregate(str(tmp_path))
    assert days["2026-07-18"]["input"] == 10
    assert days["2026-07-18"]["output"] == 20


def test_upsert_latest_wins(tmp_path):
    data = tmp_path / "data.json"
    upsert({"2026-07-18": {"input": 1, "output": 0, "cache_creation": 0,
                           "cache_read": 0, "records": 1, "cost": 0.0}}, str(data))
    store = upsert({"2026-07-18": {"input": 99, "output": 0, "cache_creation": 0,
                                   "cache_read": 0, "records": 1, "cost": 0.0}}, str(data))
    assert store["days"]["2026-07-18"]["input"] == 99  # 최신 파싱이 덮어씀
