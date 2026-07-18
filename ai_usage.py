#!/usr/bin/env python3
"""Claude Code AI 토큰 사용량 카드.

pipeline: ~/.claude/projects/**/*.jsonl 파싱 -> 날짜별 토큰 집계
-> data.json 누적 -> 5줄 gist 카드 렌더 -> gh api 로 gist push.
메시지 내용은 읽지 않고 timestamp/model/usage 토큰 수만 사용한다.
"""


def human(n):
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= div:
            return f"{n/div:.1f}{unit}"
    return str(int(n))
