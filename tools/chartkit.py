# -*- coding: utf-8 -*-
"""
chartkit — 每日五圖的繪圖引擎。

單一事實來源原則：每張圖只寫一次「資料 + 語意」，
本模組同時吐出 (a) 靜態 PNG/SVG（matplotlib）與 (b) ECharts option（互動網頁）。
兩軌若不同源就會漂移，所以永遠只從同一個 Series 物件出發。
"""
from __future__ import annotations
import json, os, datetime as dt
from dataclasses import dataclass, field, replace as ck_replace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import matplotlib.dates as mdates

# ---------------------------------------------------------------- 樣式
INK      = "#14161A"
MUTED    = "#6B7076"
FAINT    = "#9BA0A6"
GRID     = "#E7E5E2"
RULE     = "#C9C5C0"
BG       = "#FFFFFF"
# ── 序列色：角色制，不是編號制 ────────────────────────────────
# 顏色回答的是「你在這張圖的論證裡是什麼角色」，不是「你是第幾條序列」。
# 每張圖都有 takeaway 與 so_what，也就是每張圖都在講一句話——
# 顏色的工作是讓人一眼看出那句話講的是哪一條線。
#
# ACCENT 的舊值 #C8102E 註解寫著「台新紅」，但那不是台新紅。
# 品牌紅取自 tsholdings.com.tw 的 logo SVG fill（全站計算樣式 86 處）＝ #D70C18。
# #C8102E 接近 Pantone 186，是當初挑錯的；#C00000 則是 PowerPoint 標準色盤的
# Dark Red，House View 模板用的是那個。三者兩兩相距 ΔE 6～8——
# 都在「太近讀不出是刻意的、太遠又不像同一個顏色」的最糟區間。
# 這裡與 House View 月報統一到品牌紅，下游貼 PNG 時才不會出現兩種紅。
ACCENT   = "#D70C18"        # 主角：品牌紅。只留給主角線／今日點，一張圖只有一個
REF      = "#1F4E79"        # 對照：深藍。前期、對手、共識
ALT      = "#8A8F95"        # 溢出：中灰。第三條。用到就代表該考慮拆圖了
DIM      = "#B8BBBE"        # 背景：淺灰。其餘所有東西，低對比是刻意的
PALETTE  = [ACCENT, REF, ALT, DIM]
# 原本的土黃 #D9942B／綠 #3F7D5C／紫 #7A6BA8 已移出工作集：
#   土黃對白底只有 2.6:1，2pt 細線會偏淡；綠與 ACCENT 在紅綠色盲下只差 17。
#   更重要的是，一張圖需要第 5、6 個顏色時，該修的是圖不是色。
#
# 正負值不分色。原本的 POS/NEG 是死碼——全 repo 從未被引用，
# 而且 NEG 的值與 ACCENT 完全相同，真用起來會讓紅同時代表「重點」與「下跌」。
# 正負一律靠 zero_line（見 Chart.zero_line）與資料標籤表達，
# 紅只保留給主角。這也順帶避開台灣紅漲綠跌與西方慣例相反的問題。

CJK = ["PingFang TC", "Noto Sans CJK TC", "Noto Sans TC", "Heiti TC",
       "Microsoft JhengHei", "Noto Sans CJK JP", "DejaVu Sans"]

_FONT_READY = False
_CACHE = os.path.expanduser("~/.cache/chart-of-the-day/fonts")


def _ensure_cjk_font():
    """確保 matplotlib 找得到繁中字型。

    macOS 有 PingFang TC，直接可用。Linux 通常只有 Noto Sans CJK 的 .ttc 集合檔，
    而 matplotlib 只會登記 .ttc 的第一個 face（日文），造成繁中字形被日文字形取代。
    因此在找不到繁中字型時，用 fontTools 把 TC face 抽出到使用者快取目錄再登記。
    **抽出的檔案放快取、不放 repo**——單檔 17MB，不應進版控。
    """
    global _FONT_READY
    if _FONT_READY:
        return
    import matplotlib.font_manager as fm
    have = {f.name for f in fm.fontManager.ttflist}
    if have & {"PingFang TC", "Noto Sans CJK TC", "Noto Sans TC", "Heiti TC"}:
        _FONT_READY = True
        return
    os.makedirs(_CACHE, exist_ok=True)
    for cached, src, idx in [
        (f"{_CACHE}/NotoSansCJKtc-Regular.otf",
         "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 3),
        (f"{_CACHE}/NotoSansCJKtc-Bold.otf",
         "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 3),
    ]:
        try:
            if not os.path.exists(cached):
                if not os.path.exists(src):
                    continue
                from fontTools.ttLib import TTCollection
                TTCollection(src).fonts[idx].save(cached)
            fm.fontManager.addfont(cached)
        except Exception as e:                       # 抽不出來就退回泛 CJK face
            print(f"  [font] 繁中字型準備失敗，改用備援：{e}")
    _FONT_READY = True


def apply_style():
    _ensure_cjk_font()
    plt.rcParams.update({
        "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
        "font.family": "sans-serif", "font.sans-serif": CJK,
        "axes.edgecolor": RULE, "axes.linewidth": 0.9,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
        "xtick.color": MUTED, "ytick.color": MUTED,
        "xtick.labelsize": 9, "ytick.labelsize": 9,
        "axes.labelcolor": MUTED, "text.color": INK,
        "axes.unicode_minus": False, "figure.dpi": 200,
        # 讓 SVG 的內部 id 由固定 salt 產生：同一份 JSON 重畫要能位元級重現，
        # 否則「歷史可重建」無法被機械驗證，只能靠肉眼看。
        "svg.hashsalt": "chart-of-the-day",
    })

# ---------------------------------------------------------------- 資料容器
@dataclass
class Series:
    name: str
    dates: list          # 'YYYY-MM-DD'
    values: list
    color: str = None
    axis: str = "left"   # left | right
    style: str = "line"  # line | area | bar
    width: float = 1.9
    dash: bool = False
    derived: bool = False   # 滾動波動率、移動平均這類「由別的序列算出來」的量。
                            # 它們的單日跳動來自窗口進出，不是市場事件，
                            # QA 檢查會照抓但標成 derived，處置方式不同（見 qa_series）。

@dataclass
class Marker:
    date: str
    label: str
    color: str = FAINT

@dataclass
class Chart:
    slug: str
    title: str
    subtitle: str
    series: list = field(default_factory=list)
    markers: list = field(default_factory=list)
    kind: str = "timeseries"        # timeseries | scatter | dist
    y_label: str = ""
    y2_label: str = ""
    y_fmt: str = "{:,.0f}"
    y2_fmt: str = "{:,.2f}"
    source: str = ""
    note: str = ""
    zero_line: bool = False
    y_log: bool = False          # 利差、倍數這類「比例才有意義」的量請開啟
    # scatter 專用
    pts: list = field(default_factory=list)      # [(x, y), ...]
    hi_pts: list = field(default_factory=list)   # [(x, y, label), ...]
    x_label: str = ""

_label_slots: dict = {}


def _vis_len(s: str) -> float:
    """視覺寬度：CJK 與全形標點算兩格，拉丁字元算一格。用來判斷頁尾會不會壓到品牌字。"""
    return sum(2 if ord(c) > 0x2E80 else 1 for c in s)


FOOT_W = 120          # 頁尾單行可容納的視覺寬度（x 0.075→0.925、fontsize 8 實測值）
FOOT_MAX_LINES = 3    # 頁尾總行數上限，再多會吃掉圖面


def _wrap_vis(s: str, width: int = FOOT_W) -> list:
    """依視覺寬度斷行。中文沒有空白可斷，所以逐字元累加而不是用 textwrap。

    **為什麼需要這個**：頁尾原本是 `fig.text()` 單行輸出，超出圖框就被裁掉，
    而且不留任何痕跡。2026-08-08 實測抓到——`data/2026-08-05.json` 有一筆
    `note` 視覺寬 224，等於在已發布的 PNG 上被砍掉快一半，
    **而那些 PNG 正是 House View 月報直接取用的檔案**。
    """
    out, cur, w = [], "", 0
    for ch in s:
        cw = 2 if ord(ch) > 0x2E80 else 1
        if w + cw > width and cur:
            out.append(cur); cur, w = "", 0
        cur += ch; w += cw
    if cur:
        out.append(cur)
    return out or [""]


def _d(s):
    return dt.date.fromisoformat(s)

def _fmt(f):
    return FuncFormatter(lambda v, p: f.format(v))

# ---------------------------------------------------------------- PNG / SVG
def render_static(ch: Chart, outdir: str, basename: str) -> dict:
    apply_style()
    _label_slots.clear()
    fig, ax = plt.subplots(figsize=(8.6, 4.9))
    fig.subplots_adjust(left=0.075, right=0.925, top=0.80, bottom=0.17)
    ax2 = None

    if ch.kind == "scatter":
        xs = [p[0] for p in ch.pts]; ys = [p[1] for p in ch.pts]
        ax.scatter(xs, ys, s=13, c=FAINT, alpha=0.55, linewidths=0)
        ax.axhline(0, color=RULE, lw=0.9); ax.axvline(0, color=RULE, lw=0.9)
        offs = [(11, 9), (11, -15), (-14, 12), (-14, -18)]   # 交錯避免標籤互壓
        for k, (x, y, lab) in enumerate(ch.hi_pts):
            ax.scatter([x], [y], s=66, c=ACCENT, zorder=5, linewidths=0)
            dx, dy = offs[k % len(offs)]
            ax.annotate(lab, (x, y), textcoords="offset points", xytext=(dx, dy),
                        fontsize=9, color=ACCENT, fontweight="bold",
                        ha="left" if dx > 0 else "right",
                        arrowprops=dict(arrowstyle="-", color=ACCENT, lw=0.7,
                                        shrinkA=0, shrinkB=4))
        ax.set_xlabel(ch.x_label, fontsize=9)
        ax.set_ylabel(ch.y_label, fontsize=9)
        ax.grid(True, axis="both")
    else:
        # 雙軸圖不用面積填色：填到 y=0 會把兩條線壓在上緣，也會誤導比例
        dual = any(s.axis == "right" for s in ch.series)
        for i, s in enumerate(ch.series):
            col = s.color or PALETTE[i % len(PALETTE)]
            if dual and s.style == "area":
                s = ck_replace(s, style="line")
            x = [_d(d) for d in s.dates]
            tgt = ax
            if s.axis == "right":
                if ax2 is None:
                    ax2 = ax.twinx(); ax2.grid(False)
                    ax2.spines["right"].set_visible(True)
                    ax2.spines["right"].set_color(RULE)
                tgt = ax2
            if s.style == "area":
                tgt.fill_between(x, s.values, color=col, alpha=0.13, linewidth=0)
                tgt.plot(x, s.values, color=col, lw=s.width,
                         ls="--" if s.dash else "-", label=s.name)
            elif s.style == "bar":
                tgt.bar(x, s.values, color=col, width=1.0, linewidth=0, label=s.name)
            else:
                tgt.plot(x, s.values, color=col, lw=s.width,
                         ls="--" if s.dash else "-", label=s.name)
            # 末值標籤（同軸多條線時上下錯開，避免互壓）
            if s.style != "bar" and s.values:
                last = next((v for v in reversed(s.values) if v is not None), None)
                if last is not None:
                    # 以「軸內相對位置」判斷碰撞——雙軸時兩條線的絕對值不可比
                    lo_, hi_ = min(v for v in s.values if v is not None), \
                               max(v for v in s.values if v is not None)
                    frac = (last - lo_) / (hi_ - lo_) if hi_ > lo_ else 0.5
                    used = _label_slots.setdefault("all", [])
                    dy = -3
                    for prev in used:
                        if abs(prev - frac) < 0.06:
                            dy += 12
                    used.append(frac)
                    tgt.annotate(f"{last:,.2f}".rstrip("0").rstrip("."),
                                 (x[-1], last), textcoords="offset points",
                                 xytext=(5, dy), fontsize=8.5, color=col,
                                 fontweight="bold")
        if ch.zero_line:
            ax.axhline(0, color=RULE, lw=1.0)
        for m in ch.markers:
            ax.axvline(_d(m.date), color=m.color, lw=0.9, ls=":", zorder=0)
            ax.annotate(m.label, (_d(m.date), 1.005), xycoords=("data", "axes fraction"),
                        fontsize=8, color=m.color, rotation=0, ha="center")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%y/%m"))
        ax.yaxis.set_major_formatter(_fmt(ch.y_fmt))
        if ax2 is not None:
            ax2.yaxis.set_major_formatter(_fmt(ch.y2_fmt))
            ax2.tick_params(colors=MUTED, labelsize=9)

        # y 軸依資料範圍留白，不強制從 0 起（除非資料本身跨零）
        def _pad(axis, sers):
            vals = [v for s in sers for v in s.values if v is not None]
            if not vals:
                return
            lo, hi = min(vals), max(vals)
            if lo == hi:
                return
            if ch.y_log and lo > 0:
                axis.set_yscale("log")
                axis.set_ylim(lo * 0.88, hi * 1.18)
                axis.yaxis.set_major_formatter(_fmt(ch.y_fmt))
                axis.yaxis.set_minor_formatter(_fmt(ch.y_fmt))
                axis.tick_params(axis="y", which="minor", labelsize=7.5, colors=FAINT)
                return
            m = (hi - lo) * 0.10
            axis.set_ylim(min(lo - m, 0) if lo < 0 else lo - m, hi + m * 1.6)
        _pad(ax, [s for s in ch.series if s.axis != "right"])
        if ax2 is not None:
            _pad(ax2, [s for s in ch.series if s.axis == "right"])

    ax.grid(axis="x", visible=(ch.kind == "scatter"))
    ax.tick_params(length=0)

    # 標題區
    fig.text(0.075, 0.945, ch.title, fontsize=14.5, fontweight="bold", color=INK, va="top")
    fig.text(0.075, 0.868, ch.subtitle, fontsize=10, color=MUTED, va="top")
    # 圖例
    handles, labels = ax.get_legend_handles_labels()
    if ax2 is not None:
        h2, l2 = ax2.get_legend_handles_labels(); handles += h2; labels += l2
    if len(labels) > 1:
        ax.legend(handles, labels, loc="upper left", frameon=False,
                  fontsize=9, ncol=min(len(labels), 4),
                  bbox_to_anchor=(0, 1.02), handlelength=1.6)
    # 頁尾：來源與註記優先；太長時續排並讓出品牌位置，絕不互壓、**也絕不靜默裁字**。
    foot = ch.source if not ch.note else f"{ch.source}    |    {ch.note}"
    if _vis_len(foot) > 78:
        lines = _wrap_vis(ch.source) + (_wrap_vis(ch.note) if ch.note else [])
        if len(lines) > FOOT_MAX_LINES:
            # 超過上限就截斷，但**留一個看得見的刪節號**——
            # 靜默裁字會讓人以為文字本來就那麼短，是這次要修掉的正是那個行為。
            lines = lines[:FOOT_MAX_LINES]
            lines[-1] = lines[-1][:-1] + "…"
        for k, line in enumerate(reversed(lines)):      # 由下往上排，最後一行貼齊底部
            fig.text(0.075, 0.012 + k * 0.024, line, fontsize=8, color=FAINT, va="bottom")
    else:
        fig.text(0.075, 0.035, foot, fontsize=8, color=FAINT, va="bottom")
        fig.text(0.925, 0.035, "每日五圖 · Chart of the Day", fontsize=8,
                 color=FAINT, va="bottom", ha="right")

    os.makedirs(outdir, exist_ok=True)
    png = os.path.join(outdir, basename + ".png")
    svg = os.path.join(outdir, basename + ".svg")
    fig.savefig(png, dpi=200)
    fig.savefig(svg, metadata={"Date": None})      # 不寫入產生時間，同上理由
    plt.close(fig)
    return {"png": png, "svg": svg}

# ---------------------------------------------------------------- ECharts
def qa_series(ch: Chart, z: float = 5.0) -> list:
    """資料品質檢查：抓單日跳動異常大的點。

    期貨連續序列的轉倉、來源端的錯價、單位變更，都會表現成一根突兀的單日跳動。
    這些點如果沒被抓出來，會直接變成圖上的假訊號。回傳待人工覆核的清單。

    門檻為何是 5σ 而不是 6σ（2026-08-05 實測後調整）：
        6σ 漏掉了 2026-01-30 黃金單日 −11.37%（z=−5.59）。一根 11% 的單日棒子沒被
        任何機制看一眼，正是這個檢查該擋下來的東西，所以門檻本身失職。
        改 5σ 後同一份資料由 2 筆增為 7 筆，經下述連續日合併後為 5 筆。多出來的
        全是已知的真實事件（2024-08-02、2025-04-03/04、2025-05-12），依
        AGENT_BRIEF 第 3.4 節屬「保留並可在判讀中引用」。
        **多出來的不是雜訊，是本來就該被讀到的東西。**

    連續日合併：同一序列相鄰交易日的旗標會併成一筆並記 date_end。
        2025-04-03 與 04-04 是同一次關稅衝擊，算成兩筆只會讓 about.run 的處置
        說明變成流水帳，讀的人反而抓不到重點。

    衍生序列（`Series.derived=True`）的旗標會標上 `"derived": True`：
        滾動波動率、移動平均這類量的單日跳動來自「窗口進出」——某一天的極端值
        滾出 60 日窗口，指標就跳一階。**那不是市場事件、不是轉倉、也不是錯價，
        是檢查方法與衍生序列不相容。** 2026-08-06 那期 18 筆旗標裡有 13 筆是
        這一種（黃金 ETF 60 日波動率），全部要求逐筆說明只會逼出罐頭文字。
        標記後由 AGENT_BRIEF 第 3.4 節第四類統一處置：整條序列說明一次即可。
    """
    flags = []
    for s in ch.series:
        v = [x for x in s.values if x is not None]
        if len(v) < 30:
            continue
        rets = [(v[i] / v[i - 1] - 1) for i in range(1, len(v)) if v[i - 1]]
        if not rets:
            continue
        mu = sum(rets) / len(rets)
        sd = (sum((r - mu) ** 2 for r in rets) / len(rets)) ** 0.5
        if sd == 0:
            continue
        hits = [i for i, r in enumerate(rets, start=1) if abs(r - mu) > z * sd]
        run = []                      # 收集連續索引，遇到斷點就結算成一筆
        for idx in hits + [None]:
            if run and (idx is None or idx != run[-1] + 1):
                peak = max(run, key=lambda i: abs(rets[i - 1] - mu))
                r = rets[peak - 1]
                f = {"chart": ch.slug, "series": s.name,
                     "date": s.dates[run[0]] if run[0] < len(s.dates) else "?",
                     "pct": round(r * 100, 2), "z": round((r - mu) / sd, 1)}
                if s.derived:
                    f["derived"] = True
                if len(run) > 1:      # 只有跨日事件才寫 date_end 與 days
                    f["date_end"] = s.dates[run[-1]] if run[-1] < len(s.dates) else "?"
                    f["days"] = len(run)
                flags.append(f)
                run = []
            if idx is not None:
                run.append(idx)
    return flags


def echarts_option(ch: Chart) -> dict:
    """與 render_static 同源；前端直接 setOption。"""
    base = {
        "animation": False,
        "grid": {"left": 58, "right": 58, "top": 34, "bottom": 46},
        "tooltip": {"trigger": "axis" if ch.kind != "scatter" else "item",
                    "axisPointer": {"type": "line"}},
        "color": PALETTE,
        "textStyle": {"fontFamily": "'Noto Sans TC','PingFang TC',sans-serif"},
    }
    if ch.kind == "scatter":
        base.update({
            "xAxis": {"type": "value", "name": ch.x_label, "nameLocation": "middle",
                      "nameGap": 26, "splitLine": {"lineStyle": {"color": GRID}}},
            "yAxis": {"type": "value", "name": ch.y_label,
                      "splitLine": {"lineStyle": {"color": GRID}}},
            "series": [
                {"type": "scatter", "symbolSize": 6, "data": [list(p) for p in ch.pts],
                 "itemStyle": {"color": FAINT, "opacity": 0.55}, "name": "歷史交易日"},
                {"type": "scatter", "symbolSize": 13,
                 "data": [{"value": [p[0], p[1]], "name": p[2]} for p in ch.hi_pts],
                 "itemStyle": {"color": ACCENT}, "name": "同步上漲日",
                 "label": {"show": True, "formatter": "{b}", "position": "top",
                           "color": ACCENT, "fontWeight": "bold"}},
            ],
        })
        return base

    # x 軸取所有序列日期的聯集，不是 series[0] 的日期。
    #
    # **ECharts 的 category 軸是按「位置」貼資料，不是按日期。** 原本用 series[0].dates
    # 當軸、每條序列直接丟 s.values，只要某條序列長度不同，整條線就會靜默位移——
    # 而且靜態軌（matplotlib 用真實日期畫）完全正確，所以兩軌會不一致，網頁錯、PNG 對。
    #
    # 2026-08-06 實測到的兩個實例：
    #   · 08-06 圖 2 的「2016–2025 中位數」只有 42 點、軸有 2,452 點，
    #     那條參考線被畫在最左邊 1.7% 的寬度裡，看起來像沒畫出來。
    #   · 08-05 圖 5 的「台股加權」有 140 點、軸有 146 點，末端被畫在 2026-07-24
    #     的位置（實際是 08-05），**整條位移八個交易日**——而那張圖的判讀正是在
    #     比較台股與費半的相對走勢。
    #
    # 取聯集並依日期補 None，再開 connectNulls，稀疏序列（例如常數參考線）
    # 就會連成一條完整的橫線，長度不同的序列也會各自落在正確的日期上。
    dates = sorted({d for s in ch.series for d in s.dates})
    ys = [{"type": "log" if ch.y_log else "value", "scale": True, "name": ch.y_label,
           "splitLine": {"lineStyle": {"color": GRID}},
           "axisLabel": {"color": MUTED}}]
    if any(s.axis == "right" for s in ch.series):
        ys.append({"type": "value", "scale": True, "name": ch.y2_label,
                   "splitLine": {"show": False}, "axisLabel": {"color": MUTED}})
    base.update({
        "legend": {"top": 2, "textStyle": {"color": MUTED}},
        "xAxis": {"type": "category", "data": dates, "boundaryGap": False,
                  "axisLabel": {"color": MUTED,
                                "formatter": "{value}"},
                  "axisLine": {"lineStyle": {"color": RULE}}},
        "yAxis": ys,
        "series": [],
    })
    for i, s in enumerate(ch.series):
        col = s.color or PALETTE[i % len(PALETTE)]
        # 依日期對位到聯集軸上，缺的補 None。**不要直接丟 s.values**——那是位置對應。
        by_date = dict(zip(s.dates, s.values))
        item = {
            "name": s.name, "type": "bar" if s.style == "bar" else "line",
            "showSymbol": False, "smooth": False,
            "connectNulls": True,       # 稀疏序列（常數參考線）要連成完整一條
            "yAxisIndex": 1 if s.axis == "right" else 0,
            "lineStyle": {"width": s.width, "type": "dashed" if s.dash else "solid"},
            "itemStyle": {"color": col},
            "data": [by_date.get(d) for d in dates],
        }
        if s.style == "area":
            item["areaStyle"] = {"opacity": 0.13}
        base["series"].append(item)
    if ch.markers and base["series"]:
        base["series"][0]["markLine"] = {
            "silent": True, "symbol": "none",
            "lineStyle": {"color": FAINT, "type": "dotted"},
            "data": [{"xAxis": m.date, "label": {"formatter": m.label,
                      "color": FAINT, "fontSize": 10}} for m in ch.markers],
        }
    # 零線：靜態軌在 render_static() 用 axhline 畫，互動軌原本完全沒有這件事。
    # 正負值不分色之後，零線是唯一區分正負的視覺元素——兩軌都要有，否則
    # 網頁上的讀者看不出正負的分界，而 PNG 上看得出來。
    if ch.zero_line and base["series"]:
        s0 = base["series"][0]
        ml = s0.get("markLine") or {"silent": True, "symbol": "none", "data": []}
        ml.setdefault("data", [])
        ml["data"] = list(ml["data"]) + [{
            "yAxis": 0, "lineStyle": {"color": RULE, "width": 1.0, "type": "solid"},
            "label": {"show": False},
        }]
        s0["markLine"] = ml
    return base
