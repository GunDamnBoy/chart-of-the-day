# -*- coding: utf-8 -*-
"""
check_day.py — 發布前檢查。**這裡是唯一權威副本**（2026-08-09 自 AGENT_BRIEF 第 7 節移入）。

    python3 tools/check_day.py               # 檢查最新一期
    python3 tools/check_day.py 2026-08-05    # 診斷指定舊期
    CHART_REPO=/path python3 ...             # 沙箱維護時覆蓋 repo 位置

為什麼移出 brief：檢查只需要「被跑」，不需要每天「被讀」——放在 brief 裡讓每日執行
多讀 ~9,000 字元。brief 第 7 節留了薄殼，維護 skill 的 regex 抽取仍然有效（抽到的
是殼，殼會執行本檔）。**改規則就改這裡**，並同步 brief 第 4 節散文版與排程 prompt。
"""
import json, os, re, sys, glob, collections
REPO = os.environ.get('CHART_REPO') or os.path.expanduser('~/chart-of-the-day')  # 一律絕對路徑
# 預設檢查最新一期；發布流程用這個。維護時要診斷舊期，傳日期進來即可：
#     python3 -c "...exec(檢查腳本)..." 2026-08-05
# 沒有這個開關的話，想看舊期就得手改路徑，改完常常忘了改回來。
DAY  = (REPO + f'/data/{sys.argv[1]}.json') if len(sys.argv) > 1 else \
       sorted(g for g in glob.glob(REPO+'/data/2*.json'))[-1]
d    = json.load(open(DAY, encoding='utf-8'))

# 已知的歷史例外：不是待修的 bug，是不回頭改寫已發表分析的結果。
# **列在這裡是為了讓紅字有解釋**，否則下一個人會以為是新問題而去「修好」它。
KNOWN = {
  '2026-08-05': ['risk-premium-unwind so_what 59 字（規範 60–120）',
                 'spx-vix-corise so_what 42 字（規範 60–120）',
                 'sox-vs-twse reading 引用 8/4 費半 +6.55%，該日不在本圖序列內（已於 note 標明）'],
}
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
    if not (200 <= len(c.get('reading','')) <= 620): bad(f'{p} reading 長度 {len(c.get("reading",""))} 不在 200–620')
    # 歷史錨點的弱檢查（2026-08-10）：出現類比詞卻整段沒有年份 → 多半是印象不是歷史。
    # 攔不住所有編造，但攔得住最懶的那種。提示級，不擋發布。
    _rd = c.get('reading','')
    if re.search(r'上一次|上次|歷史上|前例|以來首次', _rd) and not re.search(r'(19|20)\d\d', _rd):
        print(f'   ⚠ {p} reading 有「上一次／歷史上」等類比詞，但整段找不到年份——'
              f'數字型錨點要從序列算出並帶日期，事件型類比要帶年份與關鍵差異（brief §4 歷史縱深）')
    if len(c.get('reading','').split('\n\n')) < 3:   bad(f'{p} reading 未分 3 段')
    if not c.get('watch'):  bad(f'{p} 缺 watch')
    if not (1 <= len(c.get('watch') or []) <= 3): bad(f'{p} watch {len(c.get("watch") or [])} 條，規範 1–3')
    if not (2 <= len(c.get('tags') or []) <= 5):  bad(f'{p} tags {len(c.get("tags") or [])} 個，規範 2–5')
    if not (60 <= len(c.get('so_what','')) <= 120):
        bad(f'{p} so_what 長度 {len(c.get("so_what",""))} 不在 60–120')
    # 配色只有四個角色，第 5 條序列會 PALETTE[4 % 4] 繞回主角紅，
    # 一張圖就出現兩個主角。超過 4 條要拆圖，不是換色。
    if len(c.get('series') or []) > 4:
        bad(f'{p} 有 {len(c["series"])} 條序列，超過四個角色——第 5 條會繞回主角紅，請拆成兩張圖')
    elif len(c.get('series') or []) == 4:
        print(f'   ⚠ {p} 有 4 條序列，已用到背景色當資料序列——確認第 4 條真的只是背景')
    if not c.get('files',{}).get('png'): bad(f'{p} 未產出 PNG')
    if not c.get('option'): bad(f'{p} 未產出 ECharts option')
    if c.get('slot') == '重製圖' and not c.get('provenance',{}).get('inspired_by',{}).get('url'):
        bad(f'{p} 重製圖缺 provenance.inspired_by.url')
    # 每種圖型有自己的資料欄位——**不是每種圖都用 `series`**。
    # 原本只豁免 scatter，使 waterfall／grouped_bar／stacked_bar／pct_stacked_bar／
    # heatmap／gauge 一律硬失敗（它們用 cats／vals／groups／matrix／gauge）。
    # 後果不是「報錯」而是**選題被暗中窄化**：多樣性守門要求每期至少一張非折線，
    # 而唯一過得了關的非折線就只剩 range_area（它剛好也帶 series）。
    # 連兩天的非折線圖都是同一型，原因在這裡，不在選題偏好。
    _NEED = {'scatter': ('pts',), 'waterfall': ('cats', 'vals'),
             'grouped_bar': ('cats', 'groups'), 'stacked_bar': ('cats', 'groups'),
             'pct_stacked_bar': ('cats', 'groups'), 'heatmap': ('matrix', 'rows', 'cats'),
             'gauge': ('gauge',), 'range_area': ('series', 'band')}
    _kind = c.get('kind', 'timeseries')
    for _f in _NEED.get(_kind, ('series',)):
        if not c.get(_f):
            bad(f'{p} kind={_kind} 缺必要欄位 `{_f}`')
    # marker 只有日期軸畫得出來（chartkit.DATE_AXIS_KINDS）。
    # 類別軸圖型寫了 marker 不會報錯、也不會畫出來——**規則要求標記卻靜默丟掉**，
    # 比沒有 marker 更糟，因為 reading 會照著寫「已標在圖上」。
    if c.get('markers') and _kind not in ('timeseries', 'range_area'):
        bad(f'{p} kind={_kind} 是類別軸，標不出日期 marker——'
            f'請改把錨點寫進 note，或換成有日期軸的圖型')
    if _kind not in _NEED:
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

# 序列新鮮度：拿兩天前的收盤當「今天」講，是最容易發生也最難察覺的錯
import datetime
doc_day = datetime.date.fromisoformat(d['date'])
ends = {}
for c in d['charts']:
    for s in c.get('series', []):
        ends.setdefault(s['dates'][-1], []).append(f"{c['slug']}／{s['name']}")
print('   序列新鮮度：')
for last in sorted(ends, reverse=True):
    gap = (doc_day - datetime.date.fromisoformat(last)).days
    if gap >= 5:
        bad(f'序列已過期 {gap} 天（末日 {last}）：{"、".join(ends[last])}')
    elif gap >= 2:
        print(f'   ⚠ 落後 {gap} 天（末日 {last}）：{"、".join(ends[last])}'
              '｜凡以此序列計算的「今天」數字，subtitle 或 note 必須寫出實際基準日')
    else:
        print(f'     {gap} 天（末日 {last}）：{len(ends[last])} 條序列')

# window.note 必須與實際末日相符——寫錯比不寫更糟，它會讓讀者以為資料是新的
# 一律比對 MM-DD：note 常把年份省略成「2026-08-04／08-05」。
# 前面的 (?<!\d) 與可選年份是為了不讓 '2026-08-03' 被誤切成 '26-08'。
DATE_RE = r'(?<!\d)(?:\d{4}-)?(\d{2}-\d{2})(?!\d)'
note_md = set(re.findall(DATE_RE, d.get('window', {}).get('note', '')))
ends_md = {x[-5:] for x in ends}
for nd in sorted(note_md - ends_md):
    print(f'   ⚠ window.note 提到 {nd}，但沒有任何序列以該日結束——寫錯比不寫更糟')
for ed in sorted(ends_md - note_md):
    print(f'   ⚠ 有序列末日為 {ed}，window.note 未提及')

# QA 旗標必須在 about.run 留下處置紀錄（警示級，不擋發布，但看到就要補）
# repo 內不得有符號連結——**它會讓 GitHub Pages 的打包整個失敗**。
# 2026-08-10 實測：維護時測試留下 charts/2026-08-11 -> 沙箱絕對路徑的連結，
# dashpush 照常 commit、照常推送成功，但 `upload-pages-artifact` 打包時
# 遇到指向樹外的連結就 exit 1——8 秒失敗、artifact 完全沒產生。
# **推送成功不等於上線成功**，而這一層之前完全沒有防線。
import os as _os
_links = []
for _root, _dirs, _files in _os.walk(REPO):
    if '.git' in _root.split(_os.sep):
        continue
    for _n in _dirs + _files:
        _p = _os.path.join(_root, _n)
        if _os.path.islink(_p):
            _links.append(_os.path.relpath(_p, REPO))
if _links:
    bad(f'repo 內有符號連結，GitHub Pages 打包會失敗：{_links}。'
        '**維護測試時不要在指向真實 repo 的暫存目錄裡建立新項目**——'
        '那會寫進真的 repo。')

# 圖型多樣性：每期至少一張非折線。
# 2026-08-09 量測：前五期 25 張圖有 24 張是 timeseries、53 條序列 52 條是折線，
# 而 `bar` 明明早就支援卻五天沒被用過一次。**規則沒有守門就是交給運氣。**
# **規則有生效日。** 對規則訂立前的舊期硬失敗，只會製造一堆「不該修也修不了」的紅字，
# 久了就會讓人習慣忽略紅字——那比沒有檢查更糟。
DIVERSITY_FROM = '2026-08-10'
LINEY = ('timeseries',)
nonline = [c for c in d['charts'] if c.get('kind') not in LINEY]
if d['date'] < DIVERSITY_FROM:
    print(f'   圖型多樣性：{len(nonline)} 張非折線（本期早於規則生效日 {DIVERSITY_FROM}，不列入檢查）')
elif not nonline:
    bad('五張圖全是折線——每期至少要有一張非折線（見 AGENT_BRIEF 第 4 節「圖型跟著問題走」）。'
        '**若當天真的每個題目都是「兩條線的關係」，那要換的是選題角度，不是硬換圖型。**')
else:
    print(f'   非折線 {len(nonline)} 張：{"、".join(c.get("kind","?") for c in nonline)}')

# 三大數據發布日：slot 1 必須是該數據。靠 about.macro_release 守門——
# 規則沒有守門就是交給運氣，而這條規則一個月只觸發約三次，漏掉不會有人發現。
mr = d.get('about', {}).get('macro_release')
if mr is None:
    print('   ⚠ about.macro_release 未寫入——沒跑過 macro_release.py --check？'
          '（發布日漏圖將無法被偵測）')
else:
    fresh = [r for r in mr if r.get('fresh')]
    slot1 = next((c for c in d['charts'] if c.get('slot') == '當日主圖'), {})
    for r in fresh:
        want = f"{r['kind'].lower()}-release"
        if slot1.get('slug') != want:
            bad(f"{r['label']}（{r['kind']}）今日發布，當日主圖必須是它："
                f"預期 slug `{want}`，實際 `{slot1.get('slug')}`")
    if fresh and slot1.get('theme') != '央行、利率與匯率':
        bad(f"發布日的當日主圖 theme 應為「央行、利率與匯率」，實際「{slot1.get('theme')}」")
    print(f'   三大數據發布：{"、".join(r["label"] for r in fresh) if fresh else "今日無"}')

# 頁尾寬度：PNG 的 source／note 會依視覺寬度斷行，但頁尾最多三行，再多就截斷。
# 2026-08-08 前沒有換行機制，超出圖框直接被裁且不留痕跡——
# 而 PNG 正是 House View 月報直接取用的檔案。既有 2026-08-05 有一筆視覺寬 224。
_vis = lambda s: sum(2 if ord(ch) > 0x2E80 else 1 for ch in s or '')
for i, c in enumerate(d['charts'], 1):
    ls = -(-_vis(c.get('source')) // 120) + -(-_vis(c.get('note')) // 120)
    if ls > 3:
        bad(f'[{i}] {c.get("slug")} 頁尾需 {ls} 行（上限 3），PNG 會截斷；請縮短 source／note')
    elif ls == 3:
        print(f'   ⚠ [{i}] {c.get("slug")} 頁尾佔滿 3 行——能縮就縮，頁尾越長越沒人讀')

# 體積守門：不會隨天數累積（每天獨立檔、前端一次只載一天），只隨序列長度成長
kb = os.path.getsize(DAY) / 1024
if kb > 600:   bad(f'單日 JSON {kb:.0f}KB 過大，前端載入會明顯卡頓')
elif kb > 250: print(f'   ⚠ 單日 JSON {kb:.0f}KB 偏大，檢查是否有圖用了過長的序列')
else:          print(f'   單日 JSON {kb:.0f}KB')

q   = d.get('about',{}).get('qa_flags',[])
run = d.get('about',{}).get('run','') or ''
plain   = [f for f in q if not f.get('derived')]
derived = [f for f in q if f.get('derived')]
print(f'   QA 旗標 {len(q)} 筆'
      + (f'（其中衍生序列 {len(derived)} 筆，整條說明一次即可）' if derived else ''))
# 一般旗標：逐筆都要在 about.run 點名
for f in plain:
    if (f.get('series') or '') not in run and (f.get('date') or '') not in run:
        print(f'   ⚠ 旗標未在 about.run 說明處置：{f.get("chart")}／{f.get("series")}／{f.get("date")}')
# 衍生序列：窗口進出造成的階梯跳動，逐筆要求只會逼出罐頭文字。
# 改成「每條序列至少要被提到一次」——說明一次，但不能完全不說。
for name in sorted({f.get('series', '') for f in derived}):
    if name and name not in run:
        n = sum(1 for f in derived if f.get('series') == name)
        print(f'   ⚠ 衍生序列「{name}」有 {n} 筆旗標，about.run 完全沒提到')

# 判讀文字不可引用「本圖序列涵蓋不到的日期」。
# 這條來自 2026-08-05 的實例：sox-vs-twse 的 reading 引用 8/4 費半 +6.55%，
# 但該圖的 ^SOX 序列止於 08-03——那個數字只能是抄來的，違反
# 「數字一律來自我們自己算出來的序列」。**抄來的數字沒有任何機制擋得住，
# 但「引用了序列涵蓋不到的日期」抓得到，而且那正是它的特徵。**
import datetime as _dt
DATE_TOK = re.compile(r'(?<![\d.])(\d{1,2})[/月](\d{1,2})(?![\d%])')
for i, c in enumerate(d['charts'], 1):
    if not c.get('series'):
        continue                                   # scatter 沒有 series，照不到
    # 取各序列末日的 min 並點名那條最短的序列。
    #
    # **這是提示不是指控。** 檢查無從得知文字裡的某個日期講的是哪一條序列：
    #   · 2026-08-05 sox-vs-twse 是真違規——台股到 08-05、費半只到 08-03，
    #     而文字講的是「8/4 費半 +6.55%」，那個數字只能是抄來的。
    #   · 2026-08-06 oil-vs-energy-equity 則不是——「到 8/6 的 79.65」講的是布蘭特，
    #     布蘭特確實有 08-06，短的是 XLE，而 note 已寫明「XLE 止於 08-05」。
    # 用 max 會漏掉前者，用 min 會誤報後者。**選 min 並降級為提示**，
    # 因為它的價值是逼作者確認歸屬，不是替作者下判斷。
    short = min(c['series'], key=lambda s: s['dates'][-1])
    last = short['dates'][-1]
    ly, lm, ld = (int(x) for x in last.split('-'))
    # **不掃 `watch`**：觸發條件本來就該指向未來日期，那是它的用途不是違規。
    text = ' '.join(str(c.get(f, '')) for f in ('title','subtitle','takeaway','reading','so_what'))
    for mm, dd in sorted({(int(a), int(b)) for a, b in DATE_TOK.findall(text)}):
        if not (1 <= mm <= 12 and 1 <= dd <= 31):
            continue
        if (mm, dd) > (lm, ld) and abs(mm - lm) <= 2:   # 只比對同期附近，避免誤判去年的日期
            print(f'   ⚠ [{i}] {c.get("slug")} 文字提到 {mm}/{dd}，但序列「{short["name"]}」只到 {last}'
                  f'——確認該數字出自涵蓋當日的序列，並在 note 標明各序列末日；'
                  f'若是抄來的就刪掉，違反「數字一律來自自己的序列」')

for m in KNOWN.get(d.get('date',''), []):
    print(f'   · 已知歷史例外（不必修）：{m}')

print('全部通過 ✓' if ok else '★ 有問題，不要發布')
