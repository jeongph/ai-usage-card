#!/usr/bin/env python3
"""Claude Code AI 토큰 사용량 카드.

pipeline: ~/.claude/projects/**/*.jsonl 파싱 -> 날짜별 토큰 집계
-> data.json 누적 -> 5줄 gist 카드 렌더 -> gh api 로 gist push.
메시지 내용은 읽지 않고 timestamp/model/usage 토큰 수만 사용한다.
"""

import glob
import json
import os
import subprocess
import sys
from datetime import datetime, date, timedelta

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

TZ_NAME = "Asia/Seoul"
COMPONENTS = ("input", "output", "cache_creation", "cache_read")

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


def _local_tz():
    if ZoneInfo is not None:
        try:
            return ZoneInfo(TZ_NAME)
        except Exception:
            pass
    return None


def parse_date(ts):
    if not isinstance(ts, str) or len(ts) < 10:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None
    dt = dt.astimezone(_local_tz())
    return dt.date().isoformat()


def empty_day():
    return {"input": 0, "output": 0, "cache_creation": 0,
            "cache_read": 0, "records": 0, "cost": 0.0}


def add_usage(days, ts, usage, model):
    d = parse_date(ts)
    if d is None:
        return
    rec = days.setdefault(d, empty_day())
    rec["input"] += int(usage.get("input_tokens") or 0)
    rec["output"] += int(usage.get("output_tokens") or 0)
    rec["cache_creation"] += int(usage.get("cache_creation_input_tokens") or 0)
    rec["cache_read"] += int(usage.get("cache_read_input_tokens") or 0)
    rec["cost"] += record_cost(model, usage)
    rec["records"] += 1


LEVELS = "▁▂▃▄▅▆▇█"


def render_graph(values):
    """일별 값 리스트 -> (상단, 하단) 2줄 세로 막대.
    그래프 줄에는 막대 문자만 담는다 (텍스트/이모지 금지)."""
    maxv = max(values) if values else 0
    maxv = maxv or 1
    top, bot = [], []
    for v in values:
        h = v / maxv * 2.0
        if v == 0:
            bot.append("▁")
        else:
            bot.append(LEVELS[round(min(h, 1.0) * 7)])
        ht = h - 1.0
        top.append(" " if ht <= 0 else LEVELS[round(min(ht, 1.0) * 7)])
    return "".join(top).rstrip(), "".join(bot)


def human(n):
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= div:
            return f"{n/div:.1f}{unit}"
    return str(int(n))


def day_total(rec):
    return sum(int(rec.get(c) or 0) for c in COMPONENTS)


def render_card(days, today, updated_str):
    if not days:
        return "(no usage data yet)\n"

    totals = {d: day_total(r) for d, r in days.items()}
    window = [today - timedelta(days=29 - i) for i in range(30)]
    vals = [totals.get(d.isoformat(), 0) for d in window]
    top, bot = render_graph(vals)

    grand = sum(totals.values())
    total_cost = sum(float(r.get("cost") or 0) for r in days.values())
    active = sum(1 for t in totals.values() if t > 0)
    today_v = totals.get(today.isoformat(), 0)
    peak_d = max(totals, key=lambda d: totals[d])
    peak_v = totals[peak_d]
    avg = grand / active if active else 0
    cost_day = total_cost / active if active else 0
    peak_lbl = datetime.fromisoformat(peak_d).strftime("%b %d").replace(" 0", " ")

    return "\n".join([
        f"📊 {human(grand)} tokens · ${total_cost:,.2f} · {active} days",
        f"🔥 today {human(today_v)} · peak {human(peak_v)} ({peak_lbl})",
        top,
        bot,
        f"📅 avg {human(avg)}/day · ${cost_day:.0f}/day",
        f"🕐 updated {updated_str}",
    ]) + "\n"
