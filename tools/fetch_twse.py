# -*- coding: utf-8 -*-
"""
fetch_twse.py — 台股籌碼取數（三大法人買賣超、融資融券餘額）。

⚠ 狀態：**尚未在有網路的環境實測過。** 端點與參數取自 `advisory-dashboard-daily`
   的實測紀錄（那條產線每天實際在打這幾支），但本模組的解析邏輯還沒跑過真實回應。
   **第一次使用前務必先跑 `python3 tools/fetch_twse.py --selftest` 並看輸出對不對。**
   確認可用後，把本說明改成「已實測」並在 AGENT_BRIEF 第 3.1 節登錄。

為什麼獨立成一個模組而不是塞進 fetch.py：
   fetch.py 是每天 09:00 那輪的關鍵路徑，明早第一次無人值守執行就要用。
   把未實測的程式碼加進去，萬一 import 期就出錯，會讓整輪產不出東西。
   實測穩定後再決定要不要併回去。

用法：
    python3 tools/fetch_twse.py --selftest              # 打一次今天，印出解析結果
    python3 tools/fetch_twse.py bfi82u 20260805         # 三大法人買賣超
    python3 tools/fetch_twse.py margin 20260805         # 融資融券餘額

──────────────────────────────────────────────────────────────
來自 advisory 產線的實測結論（2026-08-05，不要重踩）：

  可用：bfi82u（三大法人）、mi-margn（融資融券）、mi-index、mi-5min-hist
  不可用：MOPS 的 t21sc03_ifrs（月營收）與 t100sb02_1（法說會行事曆）
          會被重導到新版 SPA 首頁，連兩輪確認，屬結構性問題。
          需要月營收就走鉅亨／MoneyDJ 媒體轉引並標明。
  櫃買（TPEx）收盤指數同屬 SPA 被重導，媒體盤後彙整也常未載。

  **證交所的 CORS 不允許跨源**，所以 AGENT_BRIEF 第 3.3 節那條瀏覽器備援路徑
  對這幾支端點無效——只能走本機直連。公司網路擋掉的話這些圖就做不出來，
  如實記錄在 about.run，不要用媒體轉引的數字冒充官方數據。

  **每日重複抓的官方數據頁一律要帶日期參數。** 表單頁網址每天都一樣，
  advisory 那邊就因此撞上跨版去重被擋掉，改帶 dayDate 才過。
"""
from __future__ import annotations
import json, os, sys, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, "data", "series")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}

ENDPOINTS = {
    # 三大法人買賣超日報。回傳單位是「元」，寫卡前換算成億元。
    "bfi82u": "https://www.twse.com.tw/rwd/zh/fund/BFI82U?dayDate={day}&type=day&response=json",
    # 融資融券餘額。
    "margin": "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={day}&selectType=MS&response=json",
}


def _get(url: str, tries: int = 3) -> bytes:
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception as e:                       # noqa: BLE001
            last = e
    raise RuntimeError(f"取數失敗 {url}：{last}")


def fetch(kind: str, day: str) -> dict:
    """kind ∈ {'bfi82u','margin'}，day 格式 YYYYMMDD。回傳原始 JSON。"""
    if kind not in ENDPOINTS:
        raise ValueError(f"未知的端點 {kind}，可用：{list(ENDPOINTS)}")
    raw = _get(ENDPOINTS[kind].format(day=day))
    doc = json.loads(raw.decode("utf-8"))
    # 證交所在非交易日會回 stat != 'OK'（例如 '很抱歉，沒有符合條件的資料!'）。
    # **這不是錯誤，是週末或假日。** 呼叫端要能分辨「沒開市」與「抓失敗」。
    if doc.get("stat") != "OK":
        return {"ok": False, "stat": doc.get("stat"), "day": day, "kind": kind}
    return {"ok": True, "day": day, "kind": kind,
            "fields": doc.get("fields", []), "data": doc.get("data", []),
            "title": doc.get("title", "")}


def parse_bfi82u(doc: dict) -> dict:
    """三大法人買賣超 → {外資, 投信, 自營商, 合計} 單位：億元。

    ⚠ 欄位順序未實測。證交所這支的 data 每列形如
      [單位名稱, 買進金額, 賣出金額, 買賣差額]，金額為字串含逗號。
      跑 --selftest 時務必核對印出來的 fields 與實際欄位是否一致。
    """
    if not doc.get("ok"):
        return {"ok": False, "stat": doc.get("stat")}
    out = {}
    for row in doc["data"]:
        name = str(row[0]).strip()
        try:
            net = float(str(row[-1]).replace(",", "")) / 1e8     # 元 → 億元
        except (ValueError, IndexError):
            continue
        out[name] = round(net, 2)
    return {"ok": True, "unit": "億元", "by_investor": out}


def selftest(day: str | None = None) -> int:
    import datetime
    day = day or datetime.date.today().strftime("%Y%m%d")
    rc = 0
    for kind in ENDPOINTS:
        print(f"\n=== {kind} @ {day} ===")
        try:
            doc = fetch(kind, day)
        except Exception as e:                        # noqa: BLE001
            print(f"  ✗ 取數失敗：{e}")
            rc = 1
            continue
        if not doc["ok"]:
            print(f"  · 非交易日或無資料：stat={doc['stat']}")
            continue
        print(f"  title : {doc['title']}")
        print(f"  fields: {doc['fields']}")
        for row in doc["data"][:5]:
            print(f"    {row}")
        if kind == "bfi82u":
            print(f"  解析後：{parse_bfi82u(doc)}")
    print("\n核對重點：fields 的欄位順序與 parse_bfi82u 的假設是否一致；"
          "金額單位是不是元。對了才把本模組標為已實測。")
    return rc


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "--selftest":
        sys.exit(selftest(a[1] if len(a) > 1 else None))
    print(json.dumps(fetch(a[0], a[1]), ensure_ascii=False, indent=1))
