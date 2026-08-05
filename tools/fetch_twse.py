# -*- coding: utf-8 -*-
"""
fetch_twse.py — 台股籌碼取數（三大法人買賣超、融資融券餘額）。

狀態（2026-08-05 實測）：
   ✅ `bfi82u`（三大法人）**已實測可用**，欄位與聚合口徑都對過帳。
   ⚠ `margin`（融資融券）**尚未取得成功回應**——首次實測時因日期參數無效而回空，
      需以有效交易日重測。參數 `selectType=MS` 也還沒驗證過。

兩個實測踩到的坑（都寫進 MAINTENANCE 第 2 節）：
   1. **證交所會安靜地吞掉無效的日期參數**：`dayDate=#` 不報錯、不回 stat 失敗，
      直接回傳「最近一個交易日」。本模組已在送出前擋掉非 YYYYMMDD 的輸入，
      並要求呼叫端核對回傳 `title` 裡的民國日期。
   2. **三大法人是六列不是三列**，自營商拆自行買賣與避險、外資拆外資及陸資與外資自營商。
      只取單一列會少算——避險部位的量級與自行買賣相當。

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
import json, os, re, sys, urllib.request

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


_DAY_RE = re.compile(r"^\d{8}$")


def fetch(kind: str, day: str) -> dict:
    """kind ∈ {'bfi82u','margin'}，day 格式 YYYYMMDD。回傳原始 JSON。

    ⚠ **證交所會安靜地吞掉無效的日期參數。** 2026-08-05 實測：`dayDate=#` 不會
      報錯、不會回 stat 失敗，而是直接回傳「最近一個交易日」的資料（當時是 08-04）。
      呼叫端若沒發現，就會拿到一份日期不是自己要的資料，而且完全沒有跡象。
      因此這裡在送出前先擋掉不是 YYYYMMDD 的東西，並在回傳中附上 `title`，
      **呼叫端務必核對 title 裡的民國日期是不是你要的那天。**
    """
    if kind not in ENDPOINTS:
        raise ValueError(f"未知的端點 {kind}，可用：{list(ENDPOINTS)}")
    if not _DAY_RE.match(str(day)):
        raise ValueError(f"day 必須是 YYYYMMDD，收到 {day!r}。"
                         "證交所收到爛日期不會報錯，會安靜回最近一個交易日。")
    raw = _get(ENDPOINTS[kind].format(day=day))
    doc = json.loads(raw.decode("utf-8"))
    # 證交所在非交易日會回 stat != 'OK'（例如 '很抱歉，沒有符合條件的資料!'）。
    # **這不是錯誤，是週末或假日。** 呼叫端要能分辨「沒開市」與「抓失敗」。
    if doc.get("stat") != "OK":
        return {"ok": False, "stat": doc.get("stat"), "day": day, "kind": kind}
    # 證交所 RWD 端點有兩種回應形狀，同一支 API 家族內並不一致：
    #   (a) 頂層 fields / data              —— bfi82u 屬此（2026-08-05 實測）
    #   (b) tables: [{fields, data, title}] —— 多表端點屬此
    # 只吃 (a) 的話，(b) 會表現成「stat=OK 但 data 為空」，看起來像沒資料其實是形狀不對。
    if doc.get("data"):
        return {"ok": True, "day": day, "kind": kind, "shape": "flat",
                "fields": doc.get("fields", []), "data": doc["data"],
                "title": doc.get("title", "")}

    tables = [t for t in (doc.get("tables") or []) if t.get("data")]
    if tables:
        return {"ok": True, "day": day, "kind": kind, "shape": "tables",
                "tables": [{"title": t.get("title", ""), "fields": t.get("fields", []),
                            "data": t["data"]} for t in tables],
                # 便利欄位：預設攤平第一張表，呼叫端要別張自己從 tables 取
                "fields": tables[0].get("fields", []), "data": tables[0]["data"],
                "title": doc.get("title", "") or tables[0].get("title", "")}

    # 兩種形狀都不是——把頂層鍵帶回去，下次一眼就知道該怎麼解，不必再猜一輪。
    # **「成功但空」是最容易被當成成功的失敗。**
    return {"ok": False, "stat": "stat=OK 但找不到資料（頂層 data 與 tables 都空）",
            "day": day, "kind": kind, "title": doc.get("title", ""),
            "keys": sorted(doc.keys())}


# 證交所把三大法人拆成六列，不是三列（2026-08-05 實測的實際 data）：
#   自營商(自行買賣) / 自營商(避險) / 投信 / 外資及陸資(不含外資自營商) / 外資自營商 / 合計
# 媒體講的「三大法人」是聚合後的口徑，直接拿某一列會少算。
_ROLLUP = {
    "自營商": ("自營商(自行買賣)", "自營商(避險)"),
    "投信":   ("投信",),
    "外資":   ("外資及陸資(不含外資自營商)", "外資自營商"),
}


def parse_bfi82u(doc: dict) -> dict:
    """三大法人買賣超 → {外資, 投信, 自營商, 合計} 單位：億元。

    ✅ 欄位已於 2026-08-05 實測：fields ＝
       ['單位名稱', '買進金額', '賣出金額', '買賣差額']，金額為元、字串含逗號。

    **聚合口徑**：自營商要把自行買賣與避險相加，外資要把外資及陸資與外資自營商相加。
    只取單一列會少算——避險部位的金額量級與自行買賣相當，漏掉會差很多。
    回傳同時保留 `raw` 原始六列，數字被質疑時可以直接攤開對帳。
    """
    if not doc.get("ok"):
        return {"ok": False, "stat": doc.get("stat")}
    raw = {}
    for row in doc["data"]:
        name = str(row[0]).strip()
        try:
            raw[name] = round(float(str(row[-1]).replace(",", "")) / 1e8, 2)   # 元 → 億元
        except (ValueError, IndexError):
            continue
    agg = {k: round(sum(raw.get(n, 0.0) for n in names), 2)
           for k, names in _ROLLUP.items()}
    agg["合計"] = round(sum(agg.values()), 2)
    # 與證交所自己那列「合計」對帳；對不上代表列名變了，寧可吵也不要安靜地錯
    stated = raw.get("合計")
    if stated is not None and abs(stated - agg["合計"]) > 0.5:
        return {"ok": False, "stat": f"合計對不上：證交所 {stated} vs 加總 {agg['合計']}，"
                                     "可能是列名改了，請核對 raw", "raw": raw}
    return {"ok": True, "unit": "億元", "title": doc.get("title", ""),
            "three_majors": agg, "raw": raw}


def selftest(day: str | None = None) -> int:
    import datetime
    # 預設抓「昨天」而不是今天：09:00 那輪執行時當日盤還沒收，
    # 抓今天必然無資料，看起來像壞掉其實只是還沒開盤。
    day = day or (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")
    print(f"測試日期：{day}（YYYYMMDD）")
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
            print(f"  · 無資料：{doc['stat']}")
            if doc.get("title"):
                print(f"    title={doc['title']!r}")
            if doc.get("keys"):
                print(f"    回應頂層鍵：{doc['keys']}")
                print("    ↑ 把這行貼出來，就能判斷該端點的資料放在哪個鍵底下")
            rc = 1
            continue
        print(f"  title : {doc['title']}   ← **核對這裡的民國日期是不是你要的那天**")
        print(f"  shape : {doc['shape']}")
        if doc["shape"] == "tables":
            for t in doc["tables"]:
                print(f"  ── 表「{t['title']}」 fields={t['fields']}")
                for row in t["data"][:6]:
                    print(f"       {row}")
            continue
        print(f"  fields: {doc['fields']}")
        for row in doc["data"]:
            print(f"    {row}")
        if kind == "bfi82u":
            r = parse_bfi82u(doc)
            print(f"  解析後：{json.dumps(r, ensure_ascii=False)}")
            if not r.get("ok"):
                rc = 1
    print("\n核對重點：title 的日期是否正確、fields 順序是否為"
          "['單位名稱','買進金額','賣出金額','買賣差額']、三大法人加總是否與證交所的合計列相符。")
    return rc


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "--selftest":
        sys.exit(selftest(a[1] if len(a) > 1 else None))
    print(json.dumps(fetch(a[0], a[1]), ensure_ascii=False, indent=1))
