# -*- coding: utf-8 -*-
"""
prefetch.py — 在「網路通得出去的那台機器」上預抓序列，寫進 data/series 快取。

【為什麼需要這支】
2026-08-06 起，執行輪次所在的沙箱對外連線被出口代理擋掉（FRED／Yahoo／證交所
一律 Tunnel 403，只有 pypi 通）。**連續九天每一輪都靠瀏覽器同源備援取數**，
而那條路需要有 Chrome 執行個體在線 —— 2026-08-14 11:30 那輪剛好沒有，整輪沒有產出。

問題不在那天失敗，**在前八天的成功**：每天都「降級但成功」，於是一個持續九天的
結構性故障從來沒有被當成故障。**降級若每天都成功，就不會有人把它升級成問題。**

這支的角色是把取數移回網路正常的本機（使用者的 Mac），由 launchd 每天在
執行輪次之前跑一次，把常用序列寫進快取。執行輪次讀快取即可，
**不再依賴沙箱網路，也不再依賴 Chrome 有沒有開著。**

【明確的限制 —— 不要誤以為它解決了全部】
只預抓「核心清單 ∪ 近 14 天用過的序列」。當天臨時想到的新序列它抓不到，
那種情況仍要走瀏覽器備援。**它把常態變成不需要人，不是把例外也變成不需要人。**

用法：
    python3 tools/prefetch.py              預抓並寫快取
    python3 tools/prefetch.py --list       只印出這次會抓哪些，不連外
    python3 tools/prefetch.py --quiet      只印摘要（launchd 用）

狀態會寫進 data/_prefetch_status.json，執行輪次與 check_day 靠它判斷
快取是不是新鮮、有沒有哪幾條沒抓到。**沒有狀態檔＝預抓沒跑，不是「都成功」。**
"""
from __future__ import annotations
import json, os, sys, time, datetime, glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch as F

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = os.path.join(REPO, "data", "_prefetch_status.json")
RECENT_DAYS = 14

# 核心清單：即使近期沒用到也維持新鮮的序列。
# 挑選依據是「軌道輪盤五條軌道各自的骨幹」＋三大數據，
# 這些是不論當天選什麼題目都很可能需要的。
CORE = [
    # 利率與匯率
    "DGS2", "DGS10", "DGS30", "^TNX", "^TYX", "^IRX", "JPY=X", "DTWEXBGS",
    # 信用與風險偏好
    "BAMLH0A0HYM2", "BAMLC0A0CM", "BAMLH0A3HYC", "BAMLH0A1HYBB", "^VIX",
    # 美股與 AI 半導體
    "^GSPC", "^SOX", "^IXIC",
    # 台股與資金流
    "^TWII", "2330.TW", "2317.TW",
    # 原物料與能源
    "BZ=F", "GLD", "HG=F", "XLE",
    # 三大月度數據
    "CPIAUCSL", "CPILFESL", "PAYEMS", "PCEPI", "PCEPILFE",
]


def recent_ids(days: int = RECENT_DAYS) -> list:
    """近 N 期實際用過的序列 id。

    **清單自己維護自己**：任何被用過一次的序列會在接下來 N 天保持新鮮，
    之後自然淘汰。硬寫死一份清單一定會爛掉，因為選題每天都在變。
    """
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    ids = set()
    for p in sorted(glob.glob(os.path.join(REPO, "data", "20*.json"))):
        day = os.path.basename(p)[:10]
        if day < cutoff:
            continue
        try:
            doc = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        for ch in doc.get("charts", []):
            for s in ch.get("series_spec") or []:
                if s.get("id"):
                    ids.add(s["id"])
    return sorted(ids)


def targets() -> list:
    seen, out = set(), []
    for i in CORE + recent_ids():
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def main(argv):
    quiet = "--quiet" in argv
    ids = targets()

    if "--list" in argv:
        print(f"這次會抓 {len(ids)} 條（核心 {len(CORE)} ＋ 近 {RECENT_DAYS} 天用過）：")
        for i in ids:
            print(f"  {i}")
        return 0

    started = datetime.datetime.now().astimezone()
    ok, failed = [], {}
    for n, ident in enumerate(ids, 1):
        try:
            # use_cache=False：預抓的重點就是刷新，讀快取等於什麼都沒做
            s = F.get(ident, use_cache=False)
            last = s["d"][-1] if s.get("d") else "?"
            ok.append({"id": ident, "n": len(s.get("d") or []), "last": last})
            if not quiet:
                print(f"  [{n}/{len(ids)}] {ident:<16} {len(s.get('d') or []):>5} 點，末日 {last}")
        except Exception as e:
            # **失敗要逐條記下來，不要整批 abort** —— 一條抓不到不該讓其餘 30 條也沒有
            failed[ident] = f"{type(e).__name__}: {e}"[:200]
            if not quiet:
                print(f"  [{n}/{len(ids)}] {ident:<16} ✗ {failed[ident]}")
        time.sleep(1.0)          # 逐標的間隔，見 brief §3.2：429 是等不是繞

    status = {
        "started": started.isoformat(timespec="seconds"),
        "finished": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "host": os.uname().nodename,
        "requested": len(ids),
        "ok": len(ok),
        "failed": failed,
        "series": ok,
    }
    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=1)

    print(f"預抓完成：{len(ok)}/{len(ids)} 成功"
          + (f"，{len(failed)} 條失敗：{', '.join(list(failed)[:6])}" if failed else ""))
    # 全部失敗＝網路整條不通，要讓 launchd 的錯誤日誌看得出來
    return 1 if not ok else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
