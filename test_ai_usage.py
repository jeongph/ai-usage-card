import json as _json
from datetime import date
from unittest import mock
from ai_usage import human, record_cost, parse_date, add_usage, render_card, aggregate, upsert, pushed_today, push_gist


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
    assert lines[2].startswith("📈 this week ")
    assert lines[3].startswith("📅 avg ")
    assert lines[4].startswith("⚡ ")
    assert lines[4].endswith("-day streak")
    assert lines[5].startswith("🕐 updated ")


def test_render_card_empty():
    assert render_card({}, date(2026, 7, 18), "x") == "(no usage data yet)\n"


def test_render_card_trend_and_streak():
    today = date(2026, 7, 18)
    days = {}
    # 최근 7일(07-12~07-18): 07-15만 기록이 없어(=0) streak 을 3에서 끊는다
    for day, total in [
        ("2026-07-18", 2_000_000),
        ("2026-07-17", 1_000_000),
        ("2026-07-16", 1_000_000),
        ("2026-07-14", 1_000_000),
        ("2026-07-13", 1_000_000),
        ("2026-07-12", 1_000_000),
    ]:
        days[day] = _mk(day, total, 0.0)
    # 이전 7일(07-05~07-11): 각 500K
    for day in ("2026-07-11", "2026-07-10", "2026-07-09", "2026-07-08",
                "2026-07-07", "2026-07-06", "2026-07-05"):
        days[day] = _mk(day, 500_000, 0.0)

    card = render_card(days, today, "2026-07-18 13:40 KST")
    lines = card.rstrip("\n").split("\n")

    # last7 = 2M+1M+1M+0+1M+1M+1M = 7.0M, prev7 = 7*500K = 3.5M
    # pct = (7.0M-3.5M)/3.5M*100 = +100% -> ▲
    assert "▲100%" in lines[2]
    assert lines[2].startswith("📈 this week 7.0M")
    # streak: 07-18/17/16 은 값이 있고 07-15 가 비어(0) 있어 끊긴다 -> 3
    assert lines[4] == "⚡ 3-day streak"


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


def test_aggregate_dedupes_by_message_id_and_request(tmp_path):
    log = tmp_path / "proj" / "s.jsonl"
    log.parent.mkdir(parents=True)
    rows = [
        # 같은 message.id + 같은 requestId -> 1회만 집계 (subagent/resume 중복 재생)
        {"timestamp": "2026-07-17T16:00:00.000Z", "requestId": "req-1",
         "message": {"id": "msg-1", "model": "claude-opus-4-8",
                     "usage": {"input_tokens": 10, "output_tokens": 20}}},
        {"timestamp": "2026-07-17T16:05:00.000Z", "requestId": "req-1",
         "message": {"id": "msg-1", "model": "claude-opus-4-8",
                     "usage": {"input_tokens": 10, "output_tokens": 20}}},
        # 같은 message.id 지만 requestId 다름 -> 별개로 집계
        {"timestamp": "2026-07-17T16:10:00.000Z", "requestId": "req-2",
         "message": {"id": "msg-1", "model": "claude-opus-4-8",
                     "usage": {"input_tokens": 10, "output_tokens": 20}}},
    ]
    log.write_text("\n".join(_json.dumps(r) for r in rows), encoding="utf-8")

    days = aggregate(str(tmp_path))
    d = days["2026-07-18"]
    assert d["input"] == 20    # 10(req-1, 중복제거) + 10(req-2)
    assert d["records"] == 2


def test_upsert_latest_wins(tmp_path):
    data = tmp_path / "data.json"
    upsert({"2026-07-18": {"input": 1, "output": 0, "cache_creation": 0,
                           "cache_read": 0, "records": 1, "cost": 0.0}}, str(data))
    store = upsert({"2026-07-18": {"input": 99, "output": 0, "cache_creation": 0,
                                   "cache_read": 0, "records": 1, "cost": 0.0}}, str(data))
    assert store["days"]["2026-07-18"]["input"] == 99  # 최신 파싱이 덮어씀


def test_pushed_today_false_when_missing(tmp_path):
    assert pushed_today(str(tmp_path / "nope"), "2026-07-18") is False


def test_pushed_today_true_when_matches(tmp_path):
    p = tmp_path / ".last_push"
    p.write_text("2026-07-18", encoding="utf-8")
    assert pushed_today(str(p), "2026-07-18") is True
    assert pushed_today(str(p), "2026-07-19") is False


def test_push_gist_skips_without_id(tmp_path):
    msg = push_gist("card", "", str(tmp_path / ".last_push"), "2026-07-18")
    assert "skip" in msg.lower()


def test_push_gist_skips_when_already_pushed(tmp_path):
    p = tmp_path / ".last_push"
    p.write_text("2026-07-18", encoding="utf-8")
    msg = push_gist("card", "someid", str(p), "2026-07-18")
    assert "already" in msg.lower()


def test_push_gist_success_writes_last_push(tmp_path):
    lp = tmp_path / ".last_push"
    fake = mock.Mock(returncode=0, stderr="")
    with mock.patch("ai_usage.subprocess.run", return_value=fake) as m:
        result = push_gist("card-text", "realid", str(lp), "2026-07-18")
    assert result == "pushed"
    assert lp.read_text() == "2026-07-18"
    cmd = m.call_args.args[0]
    assert cmd[:5] == ["gh", "api", "-X", "PATCH", "/gists/realid"]
    assert "card-text" in m.call_args.kwargs["input"]
