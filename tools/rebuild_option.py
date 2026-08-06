# -*- coding: utf-8 -*-
"""
rebuild_option.py — 只重建既有某一天 JSON 裡的 `option` 欄位，其餘一律不動。

**為什麼不能用 `render_day.py` 回補舊期**：它會順便重新計算 `qa_flags` 並覆寫。
旗標門檻改過（6σ→5σ、加連續日合併）之後，重跑會產生與當初不同的旗標，
而 `about.run` 裡已經寫好的處置說明是對著**當初那組旗標**寫的——兩者一旦對不上，
歷史紀錄就從「誠實回報」變成「說明與資料不符」。**修渲染不該動到紀錄。**

本工具只碰 `charts[].option`：
    不動 series（事實）、不動 about.run 與 qa_flags（紀錄）、不動 files（產物路徑）、
    不動 headline / standfirst / window 等任何其他欄位。
執行前後會逐欄位比對並印出差異，確認真的只有 option 變了才寫檔。

用法：
    python3 tools/rebuild_option.py 2026-08-05 2026-08-06
    python3 tools/rebuild_option.py --all
    python3 tools/rebuild_option.py --dry-run 2026-08-05      # 只看差異不寫檔

何時該用：`chartkit.echarts_option()` 修了會影響既有圖表呈現的缺陷時。
2026-08-06 首次使用，原因是 ECharts category 軸的位置對應 bug——
序列長度不同就整條位移，網頁錯而 PNG 對（見 AGENT_BRIEF 第 8 節第 7 版）。
"""
from __future__ import annotations
import glob, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import chartkit as ck                                    # noqa: E402
from render_day import to_chart                          # noqa: E402


def rebuild(day: str, dry: bool = False) -> bool:
    path = os.path.join(REPO, "data", f"{day}.json")
    if not os.path.exists(path):
        print(f"✗ {day}：找不到 {path}")
        return False
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)

    before = json.dumps(doc, ensure_ascii=False, sort_keys=True)
    changed = []
    for c in doc.get("charts", []):
        old = c.get("option")
        new = ck.echarts_option(to_chart(c))
        if old != new:
            changed.append(c.get("slug", "?"))
        c["option"] = new

    # 守門：把 option 全部挖掉之後，其餘內容必須與原檔逐字相同。
    # 這是「只動 option」這句話的實際驗證，不是靠相信自己寫對了。
    def strip(d):
        d = json.loads(json.dumps(d))
        for ch in d.get("charts", []):
            ch.pop("option", None)
        return json.dumps(d, ensure_ascii=False, sort_keys=True)

    if strip(json.loads(before)) != strip(doc):
        print(f"✗ {day}：option 以外的欄位也變了，已中止，未寫檔")
        return False

    if not changed:
        print(f"·  {day}：option 已是最新，無需變更")
        return True
    if dry:
        print(f"·  {day}：（dry-run）會更新 {len(changed)} 張圖的 option：{changed}")
        return True

    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✓  {day}：已更新 {len(changed)} 張圖的 option：{changed}")
    return True


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if "--all" in sys.argv:
        args = sorted(os.path.basename(p)[:-5]
                      for p in glob.glob(os.path.join(REPO, "data", "2*.json")))
    if not args:
        print(__doc__)
        sys.exit(1)
    ok = all(rebuild(d, dry) for d in args)
    print("\n提醒：本工具不跑 git。dashpush 會在 180 秒內自動推送，"
          "再抓 Pages 確認一次。")
    sys.exit(0 if ok else 1)
