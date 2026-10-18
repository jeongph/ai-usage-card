# ai-usage-card

Claude Code 토큰 사용량을 집계해 GitHub 프로필에 고정한 Gist에 표시하는 Python 스크립트입니다.

```
📊 2.9B tokens · $3,110 · 35 days
🔥 today 56.8M · peak 282.4M (Jun 20)
📈 this week 238.0M ▼59% vs last
📅 avg 82.1M/day · $89/day
🏃 6-day streak
```

> 프로필 pinned gist는 **첫 5줄만** 보입니다. 6번째 줄 `updated`는 gist를 열어야 보입니다.
> `$` 금액은 실제 결제액이 아니라 **API 정가(list price) 환산값**입니다 (구독 사용자는 실제로 이 돈을 내지 않음).

## 설치

0. 준비물: `python3`, `gh`(GitHub CLI). gist 쓰기 권한:
   ```sh
   gh auth login
   gh auth refresh -h github.com -s gist
   ```
1. 저장소를 받습니다:
   ```sh
   git clone https://github.com/jeongph/ai-usage-card.git ~/ai-usage-card
   ```
2. 빈 gist를 하나 만듭니다:
   ```sh
   echo "loading..." > claude-code-usage
   gh gist create --public claude-code-usage
   ```
   출력 URL 끝의 ID를 복사합니다.
3. 환경 변수로 gist ID를 지정합니다 (셸 rc 파일에 추가):
   ```sh
   export AI_USAGE_GIST_ID=<복사한_ID>
   ```
4. 수동 테스트:
   ```sh
   python3 ~/ai-usage-card/src/ai_usage.py --push
   ```
   출력 마지막에 `pushed`가 표시되면 업로드가 완료된 것입니다. Gist를 새로고침하면 카드를 확인할 수 있습니다.
5. `~/.claude/settings.json`에 Claude Code Stop 훅을 등록합니다:
   ```json
   { "hooks": { "Stop": [ { "hooks": [
     { "type": "command",
       "command": "AI_USAGE_GIST_ID=<복사한_ID> python3 $HOME/ai-usage-card/src/ai_usage.py --push --quiet" }
   ] } ] } }
   ```
   응답이 끝날 때마다 실행되지만 **하루 1회만** 실제로 push합니다 (`.last_push`로 마지막 업로드 시각 확인).
6. GitHub 프로필 → Customize your pins → 이 gist 선택.

## 옵션

- 타임존: `src/ai_usage.py` 상단 `TZ_NAME` 수정 (기본 `Asia/Seoul`).
- 강제 재갱신: `rm ~/ai-usage-card/.last_push && python3 ~/ai-usage-card/src/ai_usage.py --push`
- 로그 보관 연장(선택): `~/.claude/settings.json`에 `{ "cleanupPeriodDays": 90 }`.

## 카드에 표시되는 것

| 줄 | 내용 |
|----|------|
| 📊 | 총 토큰 · 비용 · 활동일수 |
| 🔥 | 오늘 사용량 · 최고 사용일 |
| 📈 | 이번 주 추세 (지난주 대비 증감) |
| 📅 | 일평균 토큰 · 비용 |
| 🏃 | 연속 사용일(streak) |

## 동작 원리

`~/.claude/projects/**/*.jsonl`을 파싱해 날짜별 토큰을 합산합니다. 집계에는 메시지 내용 대신 timestamp, 모델, usage의 토큰 수만 사용합니다.

- **토큰** = `input + output + cache_creation + cache_read` (ccusage, ai-token-monitor와 동일한 정의).
- **중복 제거**: 재시도, 분기, 서브에이전트 replay로 생기는 중복 레코드는 `message.id + requestId`로 제거.
- **비용**: 모델별 정가(list price)와 캐시 배수(cache write 1.25~2×, cache read 0.1×)로 환산.

## 개발

```sh
pip install -r requirements-dev.txt
python3 -m pytest          # pytest.ini의 pythonpath=src로 src를 인식
```
