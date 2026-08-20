# 這裡的東西已經沒有在跑了 —— 可以整個資料夾刪掉

2026-08-20 把每日五圖接上 kb-core 之後，程式的家換了。**這個資料夾是搬家的殘骸**，
留在這裡只是因為工具刪不了檔案，不是因為還有用。確認過再整個刪。

## 為什麼不留一份「以防萬一」

因為留下來的那一份不會被更新，而它跟真正在跑的那一份長得一模一樣。
下一個人（或下一個我）改到哪一份是擲骰子，
**而改錯的那一次不會有任何徵兆** —— 檔案存在、語法正確、跑得動、答案是舊的。

## 東西搬去哪了

| 這裡的檔案 | 現在的家 |
|---|---|
| `chartkit.py`、`fetch*.py`、`build_series.py`、`macro_release.py`、`prefetch.py`、`rebuild_*.py`、`render_day.py` | `kb-core/scripts/chart/`（多了 `_repo.py`：repo 路徑改成明確傳入，**刻意不猜**） |
| `check_day.py` | `kb-core/checks/chart.py`（18 條檢查，走 Check 契約，每條有 fixture 與 near_miss） |
| `prefetch-launchd.sh`、`com.kenny.chartfetch.plist` | `kb-core/launchd/kbprefetch-chart.sh`、`com.kenny.kbprefetch.chart.plist` |
| `dashpush-auto-push.sh`、`dashpush-repos.txt` | 沒有家 —— 推送改由 `kb-core/tools/publish.py` 做，走 outbox 草稿與回執 |

## `check_day.py` 退休前補上的六條

搬家時逐條比對過它的每一個 `bad()`，**有六條在新檢查裡沒有對應的**，
當天補進 `checks/chart.py`：`provenance`、`series_wellformed`、`png_present`、
`prefetch_fresh`、`data_path_streak`、`release_day`。

沒有那次比對的話，這六條會跟著這個資料夾一起安靜消失 ——
**而少掉的檢查不會報錯，只會全綠。**
