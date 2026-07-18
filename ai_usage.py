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

LOG_ROOT = os.path.expanduser("~/.claude/projects")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "data.json")
CARD_PATH = os.path.join(HERE, "card.txt")
LAST_PUSH = os.path.join(HERE, ".last_push")

GIST_ID = os.environ.get("AI_USAGE_GIST_ID", "").strip() or "PUT_YOUR_GIST_ID_HERE"
GIST_FILENAME = "claude-code-usage"


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


def aggregate(root):
    days = {}
    for f in glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True):
        try:
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(o, dict):
                        continue
                    msg = o.get("message")
                    if not isinstance(msg, dict):
                        continue
                    usage = msg.get("usage")
                    if not isinstance(usage, dict):
                        continue
                    add_usage(days, o.get("timestamp"), usage, msg.get("model"))
        except Exception as e:
            print(f"read error {f}: {e}", file=sys.stderr)
    return days


def upsert(fresh, data_path):
    store = {"days": {}, "tz": TZ_NAME}
    if os.path.exists(data_path):
        try:
            with open(data_path, encoding="utf-8") as fh:
                store = json.load(fh)
        except Exception:
            pass
    store.setdefault("days", {})
    store["days"].update(fresh)
    store["tz"] = TZ_NAME
    store["updated_at"] = datetime.now(_local_tz()).isoformat(timespec="seconds")
    with open(data_path, "w", encoding="utf-8") as fh:
        json.dump(store, fh, ensure_ascii=False, indent=2, sort_keys=True)
    return store


def pushed_today(last_push_path, today_str):
    if not os.path.exists(last_push_path):
        return False
    try:
        return open(last_push_path, encoding="utf-8").read().strip() == today_str
    except Exception:
        return False


def push_gist(card, gist_id, last_push_path, today_str):
    if not gist_id or "PUT_YOUR" in gist_id:
        return "skipped (GIST_ID not set)"
    if pushed_today(last_push_path, today_str):
        return "skipped (already pushed today)"
    payload = json.dumps({"files": {GIST_FILENAME: {"content": card}}})
    try:
        p = subprocess.run(
            ["gh", "api", "-X", "PATCH", f"/gists/{gist_id}", "--input", "-"],
            input=payload, text=True, capture_output=True, timeout=60)
    except Exception as e:
        return f"push error: {e}"
    if p.returncode != 0:
        return "push failed: " + (p.stderr or "").strip()[:200]
    with open(last_push_path, "w", encoding="utf-8") as fh:
        fh.write(today_str)
    return "pushed"


def main():
    argv = sys.argv
    tz = _local_tz()
    today = datetime.now(tz).date()
    today_str = today.isoformat()

    if "--push" in argv and (not GIST_ID or "PUT_YOUR" in GIST_ID
                             or pushed_today(LAST_PUSH, today_str)):
        return  # fast path: 오늘 이미 push 했으면 파싱도 건너뜀

    fresh = aggregate(LOG_ROOT)
    store = upsert(fresh, DATA_PATH)
    updated_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M") + " KST"
    card = render_card(store.get("days", {}), today, updated_str)

    with open(CARD_PATH, "w", encoding="utf-8") as fh:
        fh.write(card)

    if "--push" in argv:
        print(push_gist(card, GIST_ID, LAST_PUSH, today_str), file=sys.stderr)
    if "--quiet" not in argv:
        sys.stdout.write(card)


if __name__ == "__main__":
    main()
