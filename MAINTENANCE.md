# 維護筆記 · 每日五圖

> 每次動這套系統，把學到的東西寫回這裡。**寫「為什麼」，不要只寫「改了什麼」。**

## 1. 動手前必讀

- **`AGENT_BRIEF.md` 與排程 prompt 是一組兩份**（`~/Documents/Claude/Scheduled/chart-of-the-day-daily/SKILL.md`）。
  只改一邊 = 製造下一次故障。最容易漂移的是第 7 節的**發布前檢查腳本**與第 2 節的**軌道輪盤**。
- **不要跑任何 git 指令（含 `git status`）——維護階段與每日執行都適用。**
  本機 `com.kenny.dashpush` 每 180 秒自動 add + commit + push，跑 git 會留下 `.git/index.lock` 把它擋住。
  要看狀態只用 `cat` / `ls` / `grep` / `tail`；**要看有沒有推上去，讀 `.git/logs/HEAD`（純讀檔，安全）或直接抓 GitHub Pages 上的檔案比對**。
  **前提：本 repo 必須在 dashpush 的監看清單內**——不在的話這條禁令會讓產出永遠留在本機。見第 2 節最後一列。
- **不要用相對路徑讀寫檔案。** `~/advisory-knowledge-hub`、`~/podcast-knowledge-digest` 與本 repo 有多個同名檔案。
- **不要改寫既有的 `data/YYYY-MM-DD.json`。** 歷史是這套系統的資產。

## 2. 已知坑（都是實測踩到的）

| 現象 | 原因 | 處置 |
|------|------|------|
| FRED 回傳的檔案打不開、開頭是 `PK` | 一次請求了多條序列，FRED 會打包成 zip | 一條一條抓。`fetch.py` 已擋 |
| `BAMLxxx` 利差序列只有約 780 筆 | **FRED 政策**：序列頁面明載「Starting in April 2026, this series will only include 3 years of observations」，ICE Data Indices 版權所致 | 分位數一律標「近三年」，**不可寫成歷史低點**。**不要試圖用 FRED API key 或換端點解決——沒有用**，那是資料授權不是技術限制 |
| `GC=F`／`BZ=F` 出現無新聞對應的單日大跳動 | 近月期貨合約轉倉 | 改用現貨序列，或在 `note` 說明。QA 旗標會抓到 |
| 圖上中文變成方框或日文字形 | matplotlib 只登記 `.ttc` 的第一個 face（日文） | `chartkit._ensure_cjk_font()` 會抽出 TC face 到 `~/.cache/`。**字型檔不要進 repo，單檔 17MB** |
| 雙軸圖兩條線看起來完全重疊 | 兩軸各自縮放造成的視覺假象 | 利差、倍數這類量改用 `y_log: true` 單軸 |
| 面積填色把線壓在圖的上緣 | 面積會填到 y=0 | `chartkit` 已在雙軸時自動改為線圖 |
| **檢查全綠、檔案都在，網站卻停在舊的一期，且毫無錯誤訊息** | **repo 不在 `com.kenny.dashpush` 的推送清單內。** 清單寫死在 `~/.dashpush/auto-push.sh` 的 `set -- ...` 那一行，**新建的 repo 不會自動納入**。2026-08-05 實測：本機檔案改完 24 分鐘（8 個 daemon 週期）後 `.git/logs/HEAD` 仍只有建置時那次手動 commit，Pages 上還是舊版 | 在 `~/.dashpush/auto-push.sh` 的 `set --` 那行補上 `"$HOME/chart-of-the-day"`。**plist 不用動、`launchctl` 不用重載**——`StartInterval` 每 180 秒重新叫起腳本，存檔後下一輪就生效。**驗證：`tail ~/.dashpush/push.log` 要出現「chart-of-the-day: 已推送 <短雜湊>」**，再抓 Pages 上的檔案比對 |

### 關於 dashpush：這個坑會重複發生

`~/.dashpush/auto-push.sh` 的檔頭自己記著 **2026-08-03** 的修復紀錄——`podcast-knowledge-digest` 從 8/02 18:20 起完全沒被推送，同樣是無聲的（launchd exit 0、log 沒有新行、排程照常回報成功、只有網站停在舊版）。**本 repo 在 8/05 中的是同一個 bug，相隔兩天。**

8/03 那次的修法做對了一半：加了「無變更也要寫 log」讓靜默變成可辨識的狀態。但**根因沒解——repo 清單是寫死的**，每開一個新知識庫就會再中一次，而且新 repo 剛建的頭幾天正好最沒人盯著。

因此本 repo 的 `AGENT_BRIEF.md` 第 6 節加了第 10 步「驗證上線」：**每天抓一次 Pages 的 `index.json` 確認 `days[0].date` 是今天。** 這是把「發布成功」從假設變成檢查——不管根因有沒有解，至少不會再無聲。

**待改進**：把清單抽成 `~/.dashpush/repos.txt` 之類的資料檔，加 repo 就只是加一行純文字，且各 `*-maintain` skill 可以直接讀它自我檢查涵蓋範圍，不必像這次一樣靠推理發現。

## 2.1 建置當天踩到的兩個坑（下次開新知識庫會再遇到）

- **`git push` 回 403 而不是 404。** 帳號的 personal access token 都是 **fine-grained（repository-scoped）**，
  一把只授權一個 repo。新建的 repo 不在任何一把的清單裡，所以 GitHub 認得你也認得 repo，就是不給寫。
  修法：到 `https://github.com/settings/personal-access-tokens/17743798`（`home-mac push`）
  把新 repo 加進 Repository access，並確認 **Contents: Read and write** 與 **Workflows: Read and write** 兩項都有
  ——commit 裡有 `.github/workflows/deploy.yml`，少了 workflow 權限會單獨擋掉那個檔案。
- **第一次 push 後 workflow 10 秒就失敗**，錯誤是 `Get Pages site failed`。
  這不是程式問題：repo 的 Pages 還沒啟用。到 Settings → Pages → **Source 選 `GitHub Actions`**（預設是 Deploy from a branch），
  再 Re-run jobs 即可。**順序是先開 Pages 再跑 workflow**，反過來一定失敗。

## 3. 瀏覽器備援路徑的限制（只在本機直連失敗時用）

- 工具回傳值會被截斷（實測單一欄位約 1,000 字元），**不要試圖把整包資料當回傳值搬運**。
- `finance.yahoo.com` 的 CSP 會擋掉程式觸發的下載；`fred.stlouisfed.org` 第一次可以，第二次會被 Chrome 擋。
- Yahoo 的 CORS 只允許 `*.yahoo.com` 來源，從 FRED 頁面 fetch Yahoo 會失敗。

## 3.1 規格漂移：最容易出事的四個點（2026-08-05 巡檢實測）

首次巡檢在四處抓到不同步或規格有洞，**全部不是程式錯誤**。下次巡檢先查這四項：

| 檢查點 | 為什麼容易漂 | 現況 |
|---|---|---|
| `reading` 長度 | 散文版（brief 第 4 節）、腳本（第 7 節）、prompt 第 5 步**共三處**，改的人通常只改看得到的那一處 | 已統一 **200–520**。往腳本靠，因為既有 JSON 不得改寫 |
| 週末軌道圖 | 輪盤只定義週一到週五，排程卻一週跑七天 | 已定義為**週線複查**（不推進輪盤，避免軌道與星期錯位） |
| QA 旗標處置 | 規範要求寫進 `about.run`，但沒有機制驗證 | 檢查腳本已加**警示級**逐筆比對（不擋發布） |
| FRED API key | brief 第 3.1 節有雙路徑，prompt 曾寫「免 API key」 | 已同步進 prompt 第 4 步，含 `--check-key` |

**教訓：凡是同一個數字或規則出現在兩個以上的檔案裡，就要在文件裡明寫「共幾處、分別在哪」**，否則下一個人一定漏改。brief 第 4 節表格下方已加這樣的註記。

## 4. 待辦與觀察中

- [~] **費半自高點跌幅的基準差異**（2026-08-05 覆核，**原假設被推翻，但尚未結案**）
      重算確認 −21.9% 的算術沒錯：序列已 rebase 至 01-02＝100，高點 198.60 @ **2026-06-22**、
      末值 155.10，比例不受 rebase 影響。**但 `^SOX` 序列止於 08-03，比當期日期落後兩個交易日**，
      而 `window.note` 還寫著「行情序列最新至 2026-08-04／08-05」——**沒有任何序列以 08-04 結束**。
      所以第一嫌疑不是圖註寫的「盤中／不同基準日」，而是**我們的資料落後了兩天**。
      算出來的缺口對得上：要達到媒體的 −18.5% 需在 08-04／08-05 兩日再漲 **+4.36%**，
      −17% 則需 **+6.28%**。半導體在 −22% 回檔後兩日反彈 4–6% 屬合理範圍。
      **還缺的一步**：取 `^SOX` 在 08-04 與 08-05 的實際收盤價驗證。本機跑
      `python3 tools/fetch.py '^SOX'` 即可，沙箱沒有外網做不到。
      驗證前圖註的計算基準說明**繼續保留**。已加序列新鮮度檢查防止再犯（brief 第 3.5 節）。

- [x] **黃金 2026-01-29 → 01-30 單日 −11.4%**（2026-08-05 判定：**不是轉倉**）
      實測 z＝**−5.59σ**，落在舊門檻 6σ 之下所以漏掉。三點證據排除轉倉與錯價：
      (1) 黃金期貨轉倉價差來自持有成本，**正常在 1% 以內**，11.4% 差了一個數量級；
      (2) 錯價的特徵是隔日還原，但它之後停在 4,600–4,900，**沒有回到 5,300**；
      (3) 後續 02-03 的 +6.08% 是獨立的反彈，不是修正回補。
      **處置**：`qa_series` 門檻由 6σ 改為 5σ，並加入「同一序列連續日合併為單一事件」。
      同一份資料由 2 筆變 5 筆，多出來的都是已知真實事件（2024-08-02、2025-04-03/04、2025-05-12）。

- [~] **台股籌碼資料源**：已寫出 `tools/fetch_twse.py`（三大法人 `bfi82u`、融資融券 `mi-margn`），
      端點取自 advisory 產線的實測紀錄。**但本模組尚未在有網路的環境跑過**，
      刻意獨立成一個檔案而不併進 `fetch.py`，以免未驗證的程式碼影響每天 09:00 的關鍵路徑。
      **下一步**：本機跑 `python3 tools/fetch_twse.py --selftest`，核對 `fields` 欄位順序與
      `parse_bfi82u` 的假設是否一致、金額單位是不是元。對了才把它標為已實測並登錄進 brief 第 3.1 節。
      注意證交所 CORS 不允許跨源，**瀏覽器備援路徑對這幾支無效**，只能本機直連。

- [x] **前端 JSON 體積**（2026-08-05 量測，**原本的問題框架是錯的**）
      單日 105.7 KB，其中 `series` 47.1 KB、`option` 41.0 KB、文字 16.4 KB。
      **體積不隨天數累積**——每天獨立檔、前端一次只載一天，所以「累積到 300KB」這個說法不成立；
      它只隨單張圖的序列長度成長（`credit-spreads` 一張就佔 49 KB，因為 3 年×2 條日資料共 1,569 點）。
      **處置**：不做過早的拆檔優化，改在檢查腳本加體積守門（>250KB 警示、>600KB 硬失敗）。
      **真要瘦身時該拉的槓桿**：`option` 內嵌的資料點與 `series` 完全重複，佔全檔 **39%**。
      讓前端從 `series` 注入資料、`option` 只留樣式，一次省掉四成——但那要同時改
      `render_day.py` 與 `index.html`，在體積成為真問題之前不值得冒這個險。

## 5. 變更紀錄

見 `AGENT_BRIEF.md` 第 8 節。
