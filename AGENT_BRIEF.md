# 每日五圖 · Chart of the Day — 執行規格（AGENT_BRIEF）

> 這份文件與排程 prompt（`~/Documents/Claude/Scheduled/chart-of-the-day-daily/SKILL.md`）是**一組兩份**。
> 改任何一邊，另一邊必須同步。不同步是這類系統最常見、也最難察覺的故障。

---

## 1. 這套系統是什麼

一句話：**每天挑五個題目，用公開資料自己畫五張圖，每張圖配一段自己的判讀；當天封存成一個獨立 JSON，圖與資料永久保留。**

三件事必須同時成立，缺一張圖就不算數：

1. **圖是自己重製的。** 選題可以取材自 Bloomberg、FT、Economist 的圖表專欄，但**絕不轉載他們的圖**。我們讀他們的論點，然後用 FRED／Yahoo 的公開資料自己畫、自己算、自己下結論。
2. **每張圖都要有「所以呢」。** 一張沒有投資意涵的漂亮圖，對本知識庫沒有價值。`takeaway`／`so_what`／`watch` 三個欄位是必填。
3. **資料留得住。** 每天的 JSON 內含該圖用到的完整序列，`data/series/` 另存 CSV 快取。任何一天的圖，一年後都要能被 `tools/render_day.py` 原樣重畫。

### 它在整個知識庫系統中的位置

```
advisory-dashboard-daily（每天 07:30，114 則新聞、15 個子類別）
              │  提供當日題材
              ▼
     chart-of-the-day（每天 09:00，本系統）
              │  提供「已經畫好、可直接引用」的圖與判讀
              ├──────────────► convergence-weekly（每週日，主題匯流訊號報）
              └──────────────► House View 月報（pptx 直接取用 PNG）
```

**下游會直接拿 `charts/<date>/*.png` 貼進簡報。** 所以圖的頁尾要自帶來源標註，離開網站也站得住。

---

## 2. 五個欄位（slot）——每天固定五張，順序固定

| # | slot | 要回答的問題 | 題材來源 |
|---|------|------------|---------|
| 1 | **當日主圖** | 今天最重要的一件事，用一張圖說清楚 | 投顧儀表板當日 headline 與深度卡 |
| 2 | **市場異動圖** | 今天市場哪裡最不尋常 | 程式化掃描：把當日變動放進歷史分布看分位 |
| 3 | **重製圖** | 國際媒體今天在講什麼、我們怎麼看得更準 | Bloomberg Graphics／FT Visual & LEX／Economist Graphic Detail／Reuters Graphics |
| 4 | **主題深掘** | 儀表板 15 個子類別中，今天最值得補一張圖的 | 投顧儀表板子類別 |
| 5 | **軌道圖** | 五大長期軌道輪值，確保跨期序列不斷線 | 固定輪盤（見下） |

**軌道輪盤（依星期輪值，週末順延）：**

| 星期 | 軌道 |
|------|------|
| 一 | 利率與匯率 |
| 二 | 台股與資金流 |
| 三 | AI 與半導體 |
| 四 | 原物料與能源 |
| 五 | 信用與風險偏好 |

軌道圖的價值在**跨期可比**：同一條軌道每週同一天出現，序列與基期盡量沿用上一次，讀者才看得出趨勢。**不要每次換算法或換基期。**

### 三條硬規則

- **五張圖不得有兩張落在同一個 `theme`。** 主題撞車就換掉排序較後的那張。
- **`slot` 1–4 必須是當天的事**，不可以拿舊題材充數。素材真的不足時，正確做法是把該 slot 改成「前瞻框架」並在 `about.run` 如實記錄，**不是硬湊**。
- **`slot` 3 的 `provenance.inspired_by` 必填**（媒體、標題、URL）。這是我們與轉載的分界線，也是日後回頭檢查「我們當初看對了沒」的依據。

---

## 3. 取數規範

### 3.1 允許的來源

| 來源 | 用途 | 取法 |
|------|------|------|
| **FRED** | 總經、利率、利差、信用、匯率、通膨預期 | `tools/fetch.py` 的 `fred()` |
| **Yahoo Finance** | 指數、個股、期貨、匯率日收盤 | `tools/fetch.py` 的 `yahoo()` |
| 世界銀行／IMF／EIA | 跨國、能源實體數據 | 官方 JSON／CSV 端點 |
| 台灣證交所、櫃買、央行、主計總處 | 台股籌碼、台灣總經 | 官方開放資料 |
| 公司財報、法說簡報 | 個別公司數字 | 原始文件，不引用二手轉述 |

**一律不使用付費牆內的圖或數據。** 讀了 Bloomberg／FT 的文章拿到論點沒問題，把他們的數字當成我們的資料來源不行——因為我們無法驗證，也無權轉載。

**FRED 的兩條路徑**：`fetch.py` 會自動選——讀得到 API key 就走官方 API（`api.stlouisfed.org`，文件化、120 req/min），讀不到就退回繪圖端點（`fredgraph.csv`，免認證但非文件化 API）。key 從 `FRED_API_KEY` 環境變數或 `~/.config/fred/api_key` 讀取，**不寫進程式碼、不進版控**（`.fred_key` 與 `.env` 已列入 `.gitignore`）。所有對外輸出都經過 `_redact()`，key 不會出現在 log 或錯誤訊息裡。
用 `python3 tools/fetch.py --check-key` 可自我檢查。

### 3.2 兩個實測過的限制（不要重踩）

1. **FRED 一次只能抓一條序列。** `fredgraph.csv?id=A,B` 會回傳 **zip**，不是 CSV。`fetch.py` 已對 `PK` 開頭做偵測並拋錯。
2. **ICE BofA 利差序列（`BAMLxxx`）只有近三年。** 這不是端點限制，是 FRED 的政策——序列頁面明載「Starting in April 2026, this series will only include 3 years of observations.」，資料本身受 ICE Data Indices 版權保護。**申請 FRED API key 不會解決這件事**，換 API 端點也不會。因此凡是用到 HY／IG OAS 的圖，分位數與中位數一律標明「近三年」，**不可以寫成「歷史低點」**。要更長的歷史只能改用其他來源（如 ICE 官方或 Bloomberg 授權資料）。

### 3.3 本機直連失敗時的備援（已實測可行）

公司網路或代理擋掉 Python 直連時，改由瀏覽器**同源** fetch：

- **FRED**：先 `navigate` 到 `https://fred.stlouisfed.org/series/<ID>`，再 `javascript_tool` 執行
  `await fetch('/graph/fredgraph.csv?id=<ID>&cosd=2015-01-01').then(r=>r.text())`
- **Yahoo**：先 `navigate` 到 `https://finance.yahoo.com/quote/<SYM>`，再 fetch
  `https://query1.finance.yahoo.com/v8/finance/chart/<SYM>?range=5y&interval=1d`
  （Yahoo 的 CORS 只允許 `*.yahoo.com` 來源，從 FRED 頁面抓會被擋。）

**注意兩件實測到的事：**
- **不要把整包資料當成工具回傳值往外送**——回傳會被截斷（實測單一欄位約 1,000 字元）。要嘛在本機處理完，要嘛用 `a.download` 存成檔案再讀。
- **`finance.yahoo.com` 的 CSP 會擋掉程式觸發的下載**；`fred.stlouisfed.org` 可以，但同一站台第二次自動下載會被 Chrome 擋。備援路徑只適合救急，正式流程請用本機直連。

### 3.4 資料品質檢查（強制）

`tools/render_day.py` 會對每條序列跑 `qa_series()`，抓出單日跳動超過 6 個標準差的點，寫進 `about.qa_flags` 並顯示在網站上。

**看到旗標不要直接忽略。** 它有三種可能，處置不同：

| 原因 | 特徵 | 處置 |
|------|------|------|
| 真實市場事件 | 有對應新聞（如 2025/04/03 關稅衝擊） | 保留，可在判讀中引用 |
| 期貨轉倉 | 出現在 `GC=F`／`BZ=F` 這類近月合約 | 改用現貨或連續調整序列，或在圖註說明 |
| 來源錯價 | 隔日就跳回去、無對應新聞 | 換來源重抓，**不要**照原樣出圖 |

---

## 4. 內容規範

| 欄位 | 長度 | 要求 |
|------|------|------|
| `title` | 12–30 字 | **是一個判斷，不是一個標籤。**「台股補上了費半掉下來的那一段」而不是「台股與費半走勢比較」 |
| `subtitle` | 一行 | 畫的是什麼、期間、單位、基期 |
| `takeaway` | ≤ 70 字 | 一句話結論，帶數字 |
| `reading` | 250–420 字，分 3 段 | 第 1 段講圖上看到什麼（帶數字）；第 2 段講為什麼會這樣；第 3 段講這裡面有什麼是市場還沒想清楚的 |
| `so_what` | 60–120 字 | 對投組的意涵。不准寫「須密切關注」這種空話 |
| `watch` | 1–3 條 | **可被驗證的觸發條件**，要有數字或事件名 |
| `tags` | 2–5 個 | 供跨期檢索 |

### 寫作要求

- 全程**繁體中文（台灣用語）**。
- **數字一律來自我們自己算出來的序列**，不是抄新聞。若我們算出的數字與媒體引用不一致，**兩個都寫，並說明計算基準**——這正是重製的價值。
- 允許有觀點，但觀點要能被證偽。凡是寫「可能」「或許」的地方，問自己：**怎樣才算錯？** 寫不出來就刪掉那句。
- 不要用 emoji。不要用「驚人」「暴漲」這類形容詞去補數字說服力不足的地方。

---

## 5. JSON schema（`data/YYYY-MM-DD.json`）

```jsonc
{
  "date": "2026-08-05",
  "weekday": "週三",
  "headline": "當日總標題（20–30 字，一個判斷）",
  "standfirst": "導言 60–100 字，串起五張圖的共同線索",
  "window": { "data_asof": "2026-08-05T10:40+08:00", "note": "各序列最新日期不一致時在此說明" },
  "about": {
    "upstream": ["advisory-knowledge-hub/data/2026-08-05.json", "..."],
    "run": "本輪執行紀錄：降級、替換、待覆核事項",
    "qa_flags": []                       // 由 render_day.py 自動寫入，不要手改
  },
  "charts": [{
    "slug": "risk-premium-unwind",       // 檔名用，英文小寫連字號
    "slot": "當日主圖",
    "theme": "能源與原物料",              // 必須是投顧儀表板 15 個子類別之一
    "title": "...", "subtitle": "...",
    "kind": "timeseries",                // timeseries | scatter
    "y_label": "...", "y2_label": "...",
    "y_fmt": "{:,.0f}", "y2_fmt": "{:,.2f}",
    "y_log": false,                      // 利差、倍數這類「比例才有意義」的量請開 true
    "zero_line": false,
    "source": "資料來源：...（含期間）",
    "note": "計算基準、限制、取材出處",
    "series": [{ "name":"布蘭特原油", "dates":["2026-01-02",...], "values":[60.75,...],
                 "color":"#C8102E", "axis":"left", "style":"line", "dash":false }],
    "markers": [{ "date":"2026-03-31", "label":"油價見頂" }],
    "pts": [], "hi_pts": [],             // kind=scatter 用
    "provenance": { "inspired_by": { "outlet":"Bloomberg", "title":"...", "url":"..." } },
    "takeaway": "...", "reading": "...\n\n...", "so_what": "...",
    "watch": ["...", "..."], "tags": ["..."],
    "files":  {},                        // render_day.py 寫入
    "option": {}                         // render_day.py 寫入（ECharts）
  }]
}
```

**`series` 一定要把資料點寫進 JSON。** 這是「歷史可查閱」的實作方式——不要只存檔名或只存來源代號。

---

## 6. 每日執行步驟

1. **讀上游**：`~/advisory-knowledge-hub/data/<今天>.json`。若當天檔案不存在（投顧儀表板還沒跑完或失敗），**等 15 分鐘再讀一次**；仍無則改用前一日檔案並在 `about.run` 註明。
2. **掃圖表專欄**：Bloomberg Graphics、FT Visual & Data／LEX、Economist Graphic Detail、Reuters Graphics。**只取圖題與論點**，記下 outlet／title／url。
3. **選題**：依第 2 節五個 slot 各挑一個，檢查 `theme` 不重複。
4. **取數**：`python3 tools/fetch.py <ids...>`；跨市場比較先 `align()` 再 `rebase()`。
5. **寫 JSON**：依第 5 節 schema 寫 `data/<今天>.json`，含完整 `series`。
6. **算圖 + 檢查**：`python3 tools/render_day.py <今天>`，看 QA 旗標並依第 3.4 節處置。
7. **更新索引**：重建 `data/index.json`。
8. **跑發布前檢查腳本**（第 7 節），全綠才發布。
9. **推送**：`git add -A && git commit && git push`。

---

## 7. 發布前檢查腳本

```python
import json, os, glob, collections
REPO = os.path.expanduser('~/chart-of-the-day')          # 一律絕對路徑
DAY  = sorted(g for g in glob.glob(REPO+'/data/2*.json'))[-1]
d    = json.load(open(DAY, encoding='utf-8'))
SLOTS  = ['當日主圖','市場異動圖','重製圖','主題深掘']    # 第 5 個是「軌道圖｜xxx」
THEMES = {'美股與財報','AI 與半導體','央行、利率與匯率','台灣','中國','日本',
          '能源與原物料','金融、併購與企業','地緣政治（中東與戰事）','美國政治與政策',
          '歐洲','亞太（韓國、印度、東南亞）','生技健護','信用債','黃金'}
ok = True
def bad(m):
    global ok; ok = False; print('✗', m)

print(DAY.split('/')[-1], '| 圖數', len(d['charts']))
if len(d['charts']) != 5: bad('圖數不是 5')
for f in ('headline','standfirst','window'):
    if not d.get(f): bad(f'缺 {f}')

seen_theme, seen_slot = [], []
for i, c in enumerate(d['charts'], 1):
    p = f'[{i}] {c.get("slug","?")}'
    for f in ('slug','slot','theme','title','subtitle','source','takeaway','reading','so_what'):
        if not c.get(f): bad(f'{p} 缺 {f}')
    if c.get('theme') not in THEMES: bad(f'{p} theme 不在 15 個子類別：{c.get("theme")}')
    seen_theme.append(c.get('theme')); seen_slot.append(c.get('slot',''))
    if not (12 <= len(c.get("title","")) <= 30): bad(f'{p} title 長度 {len(c.get("title",""))} 不在 12–30')
    if len(c.get("takeaway","")) > 70:           bad(f"{p} takeaway 超過 70 字")
    if not (200 <= len(c.get('reading','')) <= 520): bad(f'{p} reading 長度 {len(c.get("reading",""))} 不在 200–520')
    if len(c.get('reading','').split('\n\n')) < 3:   bad(f'{p} reading 未分 3 段')
    if not c.get('watch'):  bad(f'{p} 缺 watch')
    if not c.get('files',{}).get('png'): bad(f'{p} 未產出 PNG')
    if not c.get('option'): bad(f'{p} 未產出 ECharts option')
    if c.get('slot') == '重製圖' and not c.get('provenance',{}).get('inspired_by',{}).get('url'):
        bad(f'{p} 重製圖缺 provenance.inspired_by.url')
    if c.get('kind') != 'scatter':
        if not c.get('series'): bad(f'{p} 缺 series')
        for s in c.get('series', []):
            if len(s['dates']) != len(s['values']):
                bad(f'{p} 序列 {s["name"]} 日期({len(s["dates"])})與值({len(s["values"])})長度不符')
            if len(s['values']) < 20: bad(f'{p} 序列 {s["name"]} 只有 {len(s["values"])} 點，太短')

dup = [t for t, n in collections.Counter(seen_theme).items() if n > 1]
if dup: bad(f'theme 重複：{dup}')
for s in SLOTS:
    if s not in seen_slot: bad(f'缺 slot：{s}')
if not any(s.startswith('軌道圖') for s in seen_slot): bad('缺 slot：軌道圖')

for c in d['charts']:
    png = os.path.join(REPO, c.get('files',{}).get('png',''))
    if not os.path.exists(png): bad(f'PNG 檔不存在：{c.get("files",{}).get("png")}')
    elif os.path.getsize(png) < 20000: bad(f'PNG 過小可能沒畫出來：{png}')

q = d.get('about',{}).get('qa_flags',[])
print(f'   QA 旗標 {len(q)} 筆' + ('（已於 about.run 說明？請確認）' if q else ''))
print('全部通過 ✓' if ok else '★ 有問題，不要發布')
```

---

## 8. 變更紀錄

### 2026-08-05 · 第 1 版（建立）

- 建立本系統。定調為投顧知識庫的第四個上游庫，接在 `advisory-dashboard-daily` 之後執行。
- **五個 slot 的設計理由**：純「當日題材」會讓長期序列斷線，純「固定輪盤」會漏掉當天的大事。所以 1–4 吃當日、5 走輪盤，兩者互補。
- **雙軌產出（互動 HTML + 靜態 PNG／SVG）出自同一個 `Chart` 物件**，因為兩軌若各寫一次必然漂移。`render_day.py` 從 JSON 產圖，JSON 是唯一事實來源。
- **決定不轉載國際媒體圖表，改為重製**。除了版權，更實際的理由是：重製過程本身會抓到媒體的計算基準問題。首日試作即出現一例——費半自 6/22 高點跌幅，我們以 Yahoo `^SOX` 收盤價算得 −21.9%，而當日媒體引用為 −17%～−18.5%，已在圖註標明基準待覆核。
- 加入 `qa_series()` 單日跳動檢查（6σ）。首日抓到 2025/04/03 的 HY／IG 利差跳動，經查為關稅衝擊的真實市場事件而非資料錯誤——檢查有效。
- **已知限制**：FRED 對 ICE BofA 序列只給近三年；Yahoo 期貨為近月合約、轉倉會造成跳動。兩者都寫進第 3 節。
