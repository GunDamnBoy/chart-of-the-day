# 每日五圖 · Chart of the Day

每天挑五個題目，用公開資料**自己重製**五張圖，每張圖配一段自己的判讀。
當天封存成一個獨立 JSON，圖與底層資料永久保留。

網站：**https://gundamnboy.github.io/chart-of-the-day/**

- 規格與每日執行步驟：**[AGENT_BRIEF.md](AGENT_BRIEF.md)**
- 已知坑與待辦：**[MAINTENANCE.md](MAINTENANCE.md)**
- 維護入口（在 Claude 輸入）：`/chart-maintain`

## 這套系統在哪個位置

```
advisory-dashboard-daily  07:30  →  chart-of-the-day  11:00
                                          ├─→ convergence-weekly（週日）
                                          └─→ House View 月報（pptx 取用 PNG）
```

## 目錄

```
index.html              前端（ECharts 互動圖 + 判讀全文）
data/index.json         期數索引
data/YYYY-MM-DD.json    當日封存：五張圖的資料、文字、ECharts option
data/series/*.csv       序列快取（同日重跑不重複打外部站台）
charts/YYYY-MM-DD/      靜態 PNG（200dpi）與 SVG，供簡報直接取用
tools/fetch.py          取數層（FRED / Yahoo，免 API key）
tools/chartkit.py       繪圖引擎（PNG/SVG 與 ECharts option 同源）
tools/render_day.py     從 JSON 產圖並回寫 option、跑資料品質檢查
```

## 常用指令

```bash
python3 tools/fetch.py DGS10 BAMLH0A0HYM2 '^GSPC' '^SOX' 'GC=F'   # 取數
python3 tools/render_day.py 2026-08-05                             # 產圖 + QA
```

## 兩條不能違反的規則

1. **不轉載國際媒體的圖。** 取材可以，資料一律自己抓、自己算。
2. **`data/YYYY-MM-DD.json` 一旦發布就不要改寫。** 要修正就發新的一天並在 `about.run` 說明。
