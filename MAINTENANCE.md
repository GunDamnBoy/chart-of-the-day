# 維護筆記 · 每日五圖

> 每次動這套系統，把學到的東西寫回這裡。**寫「為什麼」，不要只寫「改了什麼」。**

## 1. 動手前必讀

- **`AGENT_BRIEF.md` 與排程 prompt 是一組兩份**（`~/Documents/Claude/Scheduled/chart-of-the-day-daily/SKILL.md`）。
  只改一邊 = 製造下一次故障。最容易漂移的是第 7 節的**發布前檢查腳本**與第 2 節的**軌道輪盤**。
- **不要跑任何 git 指令（含 `git status`）。** 本機有推送 daemon，跑 git 會留下 `.git/index.lock` 擋住推送。
  要看狀態只用 `cat` / `ls` / `grep` / `tail`。
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

## 3. 瀏覽器備援路徑的限制（只在本機直連失敗時用）

- 工具回傳值會被截斷（實測單一欄位約 1,000 字元），**不要試圖把整包資料當回傳值搬運**。
- `finance.yahoo.com` 的 CSP 會擋掉程式觸發的下載；`fred.stlouisfed.org` 第一次可以，第二次會被 Chrome 擋。
- Yahoo 的 CORS 只允許 `*.yahoo.com` 來源，從 FRED 頁面 fetch Yahoo 會失敗。

## 4. 待辦與觀察中

- [ ] **費半自高點跌幅的基準差異**：2026-08-05 我們以 Yahoo `^SOX` 收盤價算得 −21.9%，
      當日媒體（Barron's、IBD）引用 −17%～−18.5%。需以第二來源（如 Nasdaq 官方指數歷史）覆核，
      確認是「盤中 vs 收盤」還是「不同基準日」。**在釐清前，圖註必須保留計算基準說明。**
- [ ] **黃金 2026-01-29 → 01-30 單日 −11.4%**：未達 6σ 門檻所以沒被旗標抓到，但幅度可疑。
      待確認是真實行情還是 `GC=F` 轉倉。若是後者，考慮把 QA 門檻由 6σ 降到 5σ。
- [ ] 台股序列目前靠 Yahoo `^TWII`。若要做籌碼類的圖（三大法人、融資餘額），
      需接證交所開放資料，且其 CORS 不允許跨源，得走本機直連。
- [ ] 前端目前每次載入整份當日 JSON（含完整序列，約 100KB）。
      若未來累積到單日 300KB 以上，考慮把 `series` 拆到獨立檔、`option` 留在主檔。

## 5. 變更紀錄

見 `AGENT_BRIEF.md` 第 8 節。
