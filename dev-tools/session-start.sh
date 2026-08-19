#!/bin/bash
# ============================================
# session-start.sh — 会话启动统一钩子
# 每次 AI 会话开始时自动执行（替代 proot 无法使用的 cron）
# ============================================
set -e
WS=/workspace
CMM_SKILL=/skills/agent-core
LOG=$WS/dev-tools/session-start.log
echo "=== session-start $(date '+%F %T') ===" >> "$LOG"

# curl 重试包装（最多3次，退避 1/2/4s）
curl_retry() {
  local retries=3 wait=1
  for i in $(seq 1 $retries); do
    curl "$@" && return 0
    [ $i -eq $retries ] && return 1
    sleep $wait; wait=$((wait*2))
    echo "  [retry $i/$retries] 失败，$wait秒后重试" >> "$LOG"
  done
}

# 1. AgentRecall 加载上下文（习惯/纠错/规则）
if command -v arcli >/dev/null 2>&1; then
  arcli palace walk --depth active >> "$LOG" 2>&1 || echo "arcli palace walk 失败" >> "$LOG"
fi

# 2. 记忆复盘补跑
if [ -f "$CMM_SKILL/scripts/daily_review.py" ]; then
  LATEST=$(ls -t $WS/memory/daily/*.md 2>/dev/null | head -1)
  if [ -z "$LATEST" ]; then
    echo "首次运行 daily_review" >> "$LOG"
    python3 "$CMM_SKILL/scripts/daily_review.py" --workspace "$WS" --days 7 --update-timestamp --archive-days 30 >> "$LOG" 2>&1 || echo "daily_review 失败" >> "$LOG"
  else
    LATEST_TS=$(stat -c %Y "$LATEST")
    NOW_TS=$(date +%s)
    AGE_DAYS=$(( (NOW_TS - LATEST_TS) / 86400 ))
    if [ "$AGE_DAYS" -ge 2 ]; then
      echo "daily_review 已 $AGE_DAYS 天未跑，补跑" >> "$LOG"
      python3 "$CMM_SKILL/scripts/daily_review.py" --workspace "$WS" --days 7 --update-timestamp --archive-days 30 >> "$LOG" 2>&1 || echo "daily_review 失败" >> "$LOG"
    fi
  fi
fi

# 3. AgentRecall 定期维护
if command -v arcli >/dev/null 2>&1; then
  JOURNAL_COUNT=$(arcli list --limit 100 2>/dev/null | grep -c '"date"' || echo 0)
  if [ "$JOURNAL_COUNT" -gt 30 ] 2>/dev/null; then
    echo "journal $JOURNAL_COUNT 条，执行维护" >> "$LOG"
    arcli archive --older-than-days 30 >> "$LOG" 2>&1 || true
    arcli rollup --min-age-days 7 >> "$LOG" 2>&1 || true
  fi
fi

# 4. 情感状态加载
if command -v mood >/dev/null 2>&1; then
  echo "--- 情感状态 ---" >> "$LOG"
  mood read >> "$LOG" 2>&1 || echo "mood read 失败" >> "$LOG"
fi

# 5. 每日热榜存档
if [ -f "$WS/dev-tools/hotlist-save.sh" ]; then
  bash "$WS/dev-tools/hotlist-save.sh"
fi

echo "=== session-start 完成 ===" >> "$LOG"

# 6. 拉取 GitHub Actions 云端存档
if [ -f "$WS/.github_token" ]; then
  TOKEN=$(cat "$WS/.github_token")
  mkdir -p "$WS/memory/hotlist/cloud"
  curl_retry -s --max-time 10 -H "Authorization: Bearer $TOKEN" \
    "https://api.github.com/repos/lfiona244-beep/hotlist-archive/contents/latest/brief.json" \
    -o /tmp/cloud-brief.json 2>/dev/null
  if [ -s /tmp/cloud-brief.json ]; then
    python3 -c "
import json, base64
d = json.load(open('/tmp/cloud-brief.json'))
content = base64.b64decode(d['content']).decode('utf-8')
open('$WS/memory/hotlist/cloud/brief.json','w').write(content)
print('✅ 云端简报已拉取')
" >> "$LOG" 2>&1 || echo "云端简报解析失败" >> "$LOG"
  fi
fi

# 7. 周报补跑
if command -v weekly >/dev/null 2>&1; then
  REPORT_FILE="$WS/memory/daily/weekly-$(date +%Y-%m-%d).md"
  if [ ! -f "$REPORT_FILE" ]; then
    echo "--- 生成周报 ---" >> "$LOG"
    weekly > "$REPORT_FILE" 2>> "$LOG" || echo "weekly 失败" >> "$LOG"
  fi
fi

echo "=== session-start 完成 ===" >> "$LOG"

# 8. 数字分身每日状态生成
if command -v daily-state >/dev/null 2>&1; then
  echo "--- 分身每日状态 ---" >> "$LOG"
  daily-state >> "$LOG" 2>&1 || echo "daily-state 失败" >> "$LOG"
fi

# 9. 主动建议生成
if command -v advise >/dev/null 2>&1; then
  echo "--- 今日建议 ---" >> "$LOG"
  advise --brief >> "$LOG" 2>&1 || echo "advise 失败" >> "$LOG"
fi

# 10. 拉取 hotlist-archive 最新热点简报
echo "--- 拉取热点存档 ---" >> "$LOG"
mkdir -p $WS/memory/hotlist
curl_retry -sL --max-time 10 "https://raw.githubusercontent.com/lfiona244-beep/hotlist-archive/main/latest/brief.json" -o $WS/memory/hotlist/latest-brief.json 2>/dev/null && echo "热点简报已缓存" >> "$LOG" || echo "热点简报拉取失败" >> "$LOG"
TODAY=$(date +%Y-%m-%d)
YEAR=$(date +%Y)
MONTH=$(date +%m)
DAY=$(date +%d)
mkdir -p $WS/memory/hotlist/$YEAR/$MONTH/$DAY
for f in hotlist.json news.json bilibili.json zhihu_daily.json; do
  curl_retry -sL --max-time 8 "https://raw.githubusercontent.com/lfiona244-beep/hotlist-archive/main/data/$YEAR/$MONTH/$DAY/$f" -o $WS/memory/hotlist/$YEAR/$MONTH/$DAY/$f 2>/dev/null || true
done
echo "今日存档已缓存" >> "$LOG"

# 11. 定期推送到 GitHub（每日最多一次，防密钥泄露）
echo "--- GitHub 定期备份 ---" >> "$LOG"
command -v github-push-daily >/dev/null 2>&1 && python3 /usr/local/bin/github-push-daily >> "$LOG" 2>&1 || true

# 记忆树压缩队列（后台跑，不阻塞）
nohup bash -c "memory-tree run 2>/dev/null" > /dev/null 2>&1 &

# 记忆树衰减（艾宾浩斯遗忘曲线，后台跑）
nohup bash -c "memory-tree decay 2>/dev/null" > /dev/null 2>&1 &
