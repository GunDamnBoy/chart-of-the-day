#!/bin/zsh
# 每日五圖 · 序列預抓 —— launchd 呼叫的包裝腳本
#
# 安裝位置：~/.chartfetch/prefetch.sh（本檔是 repo 內的參考副本，改完要同步過去）
# 由 com.kenny.chartfetch 每天 11:00 呼叫，在 11:31 那輪執行之前把快取刷新。
#
# 為什麼要有包裝而不是讓 launchd 直接跑 python：
#   1. launchd 的環境變數極少，PATH 要自己給
#   2. 要把 stdout/stderr 導進日誌，否則失敗是靜默的
#   3. 要記錄每次的起訖時間，判斷「今天到底有沒有跑」
#
# **這支不跑任何 git 指令。** dashpush 會在 180 秒內自動把快取的變動推上去。

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

REPO="$HOME/chart-of-the-day"
LOG="$HOME/.chartfetch/prefetch.log"
mkdir -p "$(dirname "$LOG")"

# 日誌只留最後 2000 行，免得長期跑下來吃掉磁碟
if [ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 2000 ]; then
  tail -n 1000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 開始預抓 ===" >> "$LOG"
cd "$REPO" || { echo "repo 不存在：$REPO" >> "$LOG"; exit 1; }

python3 tools/prefetch.py --quiet >> "$LOG" 2>&1
rc=$?

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 結束，exit=$rc ===" >> "$LOG"
exit $rc
