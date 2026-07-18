#!/usr/bin/env python3
"""Claude Code AI 토큰 사용량 카드.

pipeline: ~/.claude/projects/**/*.jsonl 파싱 -> 날짜별 토큰 집계
-> data.json 누적 -> 5줄 gist 카드 렌더 -> gh api 로 gist push.
메시지 내용은 읽지 않고 timestamp/model/usage 토큰 수만 사용한다.
"""

# $ per 1M tokens: (input_rate, output_rate). List price; prefix 매칭.
PRICING = {
    "claude-fable-5": (10.0, 50.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-opus-4-5": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}


def _rates(model):
    if not model:
        return None
    for key, rates in PRICING.items():
        if model.startswith(key):
            return rates
    return None


def record_cost(model, usage):
    r = _rates(model)
    if not r:
        return 0.0
    in_rate, out_rate = r
    inp = int(usage.get("input_tokens") or 0)
    out = int(usage.get("output_tokens") or 0)
    read = int(usage.get("cache_read_input_tokens") or 0)
    cc = usage.get("cache_creation") if isinstance(usage.get("cache_creation"), dict) else {}
    cc5 = int(cc.get("ephemeral_5m_input_tokens") or 0)
    cc1 = int(cc.get("ephemeral_1h_input_tokens") or 0)
    if not (cc5 or cc1):
        cc5 = int(usage.get("cache_creation_input_tokens") or 0)
    return (inp * in_rate
            + out * out_rate
            + cc5 * in_rate * 1.25
            + cc1 * in_rate * 2.0
            + read * in_rate * 0.10) / 1_000_000.0


def human(n):
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= div:
            return f"{n/div:.1f}{unit}"
    return str(int(n))
