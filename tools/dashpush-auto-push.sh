#!/bin/zsh
# ~/.dashpush/auto-push.sh — 多 repo 自動推送，由 launchd com.kenny.dashpush 每 180 秒觸發。
#
# 語法刻意維持 POSIX 相容：launchd 走 shebang 用 zsh，但人工除錯時常會直接
# `bash auto-push.sh`，若混用 zsh 專有語法（${VAR:t}、zsh 陣列）就會炸掉。
# 因此這裡用 set -- 搭配 "$@" 傳遞 repo 清單，並以 basename 取目錄名。
#
# 2026-08-03 修復紀錄：
#   前一版只設了 REPO="$HOME/advisory-knowledge-hub" 單一路徑，podcast-knowledge-digest
#   因此從 8/2 18:20 起完全沒有被推送，而且是無聲的——launchd exit 0、push.log 沒有新行
#   （原版在「無變更」時直接 exit 0 且不留紀錄）、data/ 檔案照常寫入、排程任務照常回報
#   成功，只有網站悄悄停在舊版。修正重點：
#     1. 改回多 repo，任一 repo 失敗都不影響其他 repo
#     2. 用 continue 跳過該 repo，不再用 exit 中止整支腳本
#     3. 每次執行都留下時間戳，「沒有變更」也要寫進 log —— 靜默必須是可辨識的狀態
#     4. 推送成功後記錄 HEAD 短雜湊，方便事後與線上版本比對
#
# 2026-08-05 修復紀錄（同一個 bug 的第三次發作，這次治根）：
#   chart-of-the-day 於 8/5 建立後同樣沒被推送，症狀與 8/03 那次一模一樣——
#   launchd exit 0、檔案照常寫入、排程回報全綠，只有網站停在建置當天那一版。
#   8/03 的修法只做了一半：加了 log 讓靜默變成可辨識，但**清單仍寫死在程式裡**，
#   所以每開一個新知識庫就會再中一次，而新 repo 剛建的頭幾天正好最沒人盯著。
#   本版把清單抽成資料檔 ~/.dashpush/repos.txt：
#     1. 加 repo ＝ 加一行純文字，不必碰邏輯，不會改壞語法
#     2. 各 *-maintain skill 可以直接 cat 那個檔，自我檢查「我這個 repo 有沒有被涵蓋」
#     3. 清單檔不存在或全空時大聲失敗，不要安靜地什麼都不做
#     4. 每輪開頭記錄本次涵蓋的 repo 數，log 自己就能回答「它到底在看哪幾個」

set -u
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"

BRANCH="main"
LOG="$HOME/.dashpush/push.log"
LIST="$HOME/.dashpush/repos.txt"

say() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG"; }

# ---- 讀清單 -----------------------------------------------------------------
# 格式：一行一個路徑，允許 ~ 開頭，# 為註解，空行略過。
if [ ! -f "$LIST" ]; then
  say "★ 清單檔不存在：$LIST —— 本輪未推送任何 repo"
  exit 1
fi

set --
while IFS= read -r line || [ -n "$line" ]; do
  line="${line%%#*}"                                  # 去掉行內註解
  line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  [ -z "$line" ] && continue
  case "$line" in
    "~"*) line="$HOME${line#\~}" ;;                   # 展開 ~，read 不會自動展
  esac
  set -- "$@" "$line"
done < "$LIST"

if [ "$#" -eq 0 ]; then
  say "★ 清單檔是空的：$LIST —— 本輪未推送任何 repo"
  exit 1
fi

say "本輪涵蓋 $# 個 repo"

# ---- 逐一推送 ---------------------------------------------------------------
for REPO in "$@"; do
  NAME=$(basename "$REPO")

  if [ ! -d "$REPO/.git" ]; then
    say "$NAME: 略過（不是 git repo）"
    continue
  fi

  cd "$REPO" || { say "$NAME: 略過（cd 失敗）"; continue; }

  # 殘留的 index.lock 會讓所有 git 操作失敗。確認沒有 git 程序在跑才清掉。
  if [ -f .git/index.lock ] && ! pgrep -x git >/dev/null 2>&1; then
    rm -f .git/index.lock
    say "$NAME: 清除殘留的 .git/index.lock"
  fi

  if [ -z "$(git status --porcelain 2>/dev/null)" ]; then
    say "$NAME: 無變更"
    continue
  fi

  if ! git add -A >>"$LOG" 2>&1; then
    say "$NAME: git add 失敗，略過"
    continue
  fi

  if ! git commit -q -m "chore: update $(date '+%Y-%m-%d %H:%M')" >>"$LOG" 2>&1; then
    say "$NAME: commit 失敗，略過"
    continue
  fi

  if ! git pull --rebase --autostash -q origin "$BRANCH" >>"$LOG" 2>&1; then
    say "$NAME: pull --rebase 失敗，略過推送"
    continue
  fi

  if git push -q origin "$BRANCH" >>"$LOG" 2>&1; then
    say "$NAME: 已推送 $(git rev-parse --short HEAD)"
  else
    say "$NAME: push 失敗"
  fi
done
