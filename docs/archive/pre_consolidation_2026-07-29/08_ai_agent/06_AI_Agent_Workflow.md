# AI Agent Working Guide（未來 AI Session 工作流程）

**建立日期**: 2026-07-03｜**讀者**: 之後接手本專案的 AI 模型（Sonnet/Opus/Haiku 等）

---

## 1. Session 開場儀式（依序，約 5 分鐘）

1. 讀根目錄 `CLAUDE.md`（規則+導航，自動載入）。
2. 讀 `memory-bank/activeContext.md` 的「當前焦點」與「待辦」→ 這是**最即時**的專案狀態。
3. 若任務涉及某模組，查 [02_Code_Intelligence.md](02_Code_Intelligence.md) 找到職責與注意事項，再開檔。
4. 動手前搜 [05_Troubleshooting.md](05_Troubleshooting.md) 是否踩過同樣的坑。

## 2. 真相優先序（衝突時誰說了算）

```
程式碼與 YAML 設定（唯一真相）
  > memory-bank/activeContext.md、progress.md（最即時的意圖與狀態）
  > docs/08_ai_agent/（本知識庫，2026-07-03 快照）
  > docs/00~07（人類向文件，可能落後數週）
  > .kiro/specs/、archive/、memory-bank/productContext.md（歷史，僅供考古）
```
發現文件與程式碼矛盾：以程式碼為準，**順手修文件**，並在 activeContext 記一筆。

## 3. 如何搜尋這個專案

| 想找什麼 | 去哪裡 |
|---|---|
| 某 KPI 怎麼算 | `sql/etl/dml/backfill_*.sql`（業務規則全在 SQL，不在 Python） |
| 某表哪來的 | `scripts/etl/config/sync_tables.yaml`（bronze）或 `pipeline_config.yaml`（silver/gold） |
| 某表結構 | `sql/etl/schema/`（比連 DB describe 快且含註解） |
| 前端看到的數字 | `cube/model/cubes/*.js` 的 measure 定義 |
| 為什麼這樣設計 | 本知識庫 KB §1、`memory-bank/systemPatterns.md`、`docs/06_Data_Engineer_Handover.md` |
| 最近改了什麼 | `git log --oneline -20` + `memory-bank/progress.md` |
| 生產環境狀態 | `python scripts/etl/execute_etl.py --status`（需 `infra/.env` 環境變數） |

## 4. 修改的標準迴圈

```
理解（讀 02/03/05 對應章節）→ 定位（規則在 SQL、執行在 Python、呈現在 Cube）
→ 修改（遵守 04_Development_Guide checklist）→ 測試（pytest + --status + 對帳）
→ 文件（更新受影響的 docs 與 memory-bank/activeContext）→ commit（英文，不 push）
```

**驗證資料正確性的黃金基準**（歷史已驗證數值，回歸測試可比對）:
- 2025-12-31 WJ2 WJ-S28: Todo 9 / Doing 5 / Done 186 / Total 200
- 2025-12 月結: total=2294, todo=12, doing=93, done=2189
- W51=502/31, W52=583/46, 2026-W01=12/5（total/acc）
- 2026-04 V3 全月（MSSQL PRD）: Total=1825 / Done=1800（98%）

## 5. 禁區與確認點（違反=事故）

| 級別 | 規則 |
|---|---|
| 🔴 絕對禁止 | 對 MSSQL 來源庫任何寫入/DDL（生產庫） |
| 🔴 絕對禁止 | 自動 `git push`（必須等使用者說「推送」）；push GitHub 用公司身份、或帶 IP/密碼 |
| 🔴 push GitHub 前 | 檢查 diff 無 IP/密碼（工作樹已於 2026-07-06 commit `263dfa1` 清洗乾淨）。**更大的地雷**: 本地 master 歷史未經 filter-repo 改寫、歷史層仍含舊機敏字串，與 GitHub 的乾淨歷史完全分叉——**嚴禁直接 push/force-push master 到 GitHub**，必須從 origin/master 建分支 cherry-pick 新 commits |
| 🟠 先問使用者 | `--reset`、TRUNCATE、DROP、`ALTER DELETE`、改 `infra/.env`、大範圍歷史回填（>1 個月） |
| 🟠 執行 sync 前 | 確認 `MSSQL_PASSWORD` 環境變數存在（空字串會清空維度表，見 Troubleshooting A1） |
| 🟡 注意 | Windows 開發機（PowerShell 5.1）；生產腳本在 Linux 容器環境跑 bash wrapper |

## 6. 文件維護協議（讓知識庫不腐化）

- **改了行為** → 同 PR 更新 `docs/08_ai_agent/02`（模組地圖）與受影響的 docs/00~07。
- **踩了新坑** → 在 `05_Troubleshooting.md` 加一條（症狀/根因/解法/證據位置）。
- **完成一件事** → `memory-bank/activeContext.md` 待辦打勾 + 「近期已解決」加段落（保持該檔案 <250 行，舊段落移去 progress.md）。
- **發現文件錯誤** → 立即修，不要留「注意這裡文件是錯的」之類的註記債。
- 所有新增敘述標 ✅/⚠/❓，不確定就標 ❓ 並寫下驗證方法。

## 7. 目前開放中的工作（2026-07-03 快照，接手先看這裡）

1. 未 commit 的工作目錄修改待推 GitLab：環境變數化 5 檔 + sync fail-loud + monitoring compose（activeContext 記載）。
2. `sync_full_table` TRUNCATE 無回滾 → 暫存表原子替換方案（Assessment R2）。
3. L7 人員使用率：`gold.tb_active_user_metrics`，狀態 ❓（對應 cube 檔案曾以 untracked 副本存在，2026-07 清理暫存檔時已移除）。
4. ~~315 工單規則不一致~~ → 已於 2026-07-06 決策維持現狀（69 萬筆影響量過大，`.kiro` spec 視為過時，詳見 Assessment §6.1）。
5. 清理暫存驗證腳本（check_gold_region.py 等 4 支，activeContext 記載，目前目錄已不見 ❓ 可能已清）。2026-07 已另清理 `logs/output/`、`archive/`、`prd_mssql/`、`.pytest_cache/`、`__pycache__/`、`.deltacoder/` 等未追蹤暫存內容。
6. Silver 可清理欄位: `task_status`、`task_create_date`（無下游引用）。
7. GitHub `main` 分支待刪（預設已switched to master）。
