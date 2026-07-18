# ai-usage-card

Claude Code 토큰 사용량을 GitHub 프로필 **pinned gist** 카드로 띄우는 단일 파이썬 스크립트.

```
📊 7.8B tokens · $9,811.79 · 35 days
🔥 today 10.4M · peak 943.9M (Jun 20)
 █▇▃       ▂   ▄▃
▂███▃▃▂▇▃▂▂█▃▆▇██▆▂▄▂▁▁▁▂▂▄▂▂▁
📅 avg 224.2M/day · $280/day
```

> 프로필 pinned gist는 **첫 5줄만** 보입니다. 6번째 줄 `updated`는 gist를 열어야 보입니다.
> `$` 금액은 실제 결제액이 아니라 **API 정가(list price) 환산값**입니다 (구독 사용자는 실제로 이 돈을 내지 않음).

## 설치

0. 준비물: `python3`, `gh`(GitHub CLI). gist 쓰기 권한:
   ```sh
   gh auth login
   gh auth refresh -h github.com -s gist
   ```
1. 이 저장소를 받습니다: `git clone <repo-url> ~/ai-usage-card`
2. 빈 gist를 하나 만듭니다:
   ```sh
   echo "loading..." > claude-code-usage
   gh gist create --public claude-code-usage
   ```
   출력 URL 끝의 ID를 복사합니다.
3. 환경변수로 gist ID를 지정합니다 (셸 rc 파일에 추가):
   ```sh
   export AI_USAGE_GIST_ID=<복사한_ID>
   ```
4. 수동 테스트:
   ```sh
   python3 ~/ai-usage-card/ai_usage.py --push
   ```
   끝에 `pushed`가 뜨면 성공. gist를 새로고침하면 카드가 보입니다.
5. Claude Code Stop 훅 등록 — `~/.claude/settings.json`:
   ```json
   { "hooks": { "Stop": [ { "hooks": [
     { "type": "command",
       "command": "AI_USAGE_GIST_ID=<복사한_ID> python3 $HOME/ai-usage-card/ai_usage.py --push --quiet" }
   ] } ] } }
   ```
   응답이 끝날 때마다 실행되지만 **하루 1회만** 실제 push 합니다 (`.last_push` 디바운스).
6. GitHub 프로필 → Customize your pins → 이 gist 선택.

## 옵션

- 타임존: `ai_usage.py` 상단 `TZ_NAME` 수정.
- 강제 재갱신: `rm ~/ai-usage-card/.last_push && python3 ~/ai-usage-card/ai_usage.py --push`
- 로그 보관 연장(선택): `~/.claude/settings.json` 에 `{ "cleanupPeriodDays": 90 }`.

## 동작 원리

`~/.claude/projects/**/*.jsonl` 을 파싱해 날짜별 토큰을 합산합니다. **메시지 내용은 읽지 않고**
timestamp·모델·usage 토큰 수만 사용합니다. 카드는 최근 30일을 2줄 세로 막대로 그립니다.
