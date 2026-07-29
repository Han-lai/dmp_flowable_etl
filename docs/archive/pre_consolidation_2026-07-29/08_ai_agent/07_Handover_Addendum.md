# 交接補充文件（Handover Addendum）

**建立日期**: 2026-07-03
**定位**: 完整的開發維運交接手冊已存在——[docs/06_Data_Engineer_Handover.md](../06_Data_Engineer_Handover.md)（10 個部分，含快速開始/架構/各層邏輯/監控/擴充 SOP/練習/FAQ）。本文**不重複**其內容，只補充該手冊未涵蓋、本次 Intelligence Session 確認的事項。

---

## 1. 接手第一天路線圖

1. `CLAUDE.md`（根目錄）→ 5 分鐘掌握規則與指令。
2. `docs/08_ai_agent/01_Project_Assessment.md` → 知道風險與文件哪裡不可信。
3. `docs/06_Data_Engineer_Handover.md` 第零~二部分 → 環境準備與架構。
4. `memory-bank/activeContext.md` → 當前進行中/未完成事項。
5. 跑 `python scripts/etl/execute_etl.py --status` 確認生產健康。

## 2. 日常維運節奏（✅ 已驗證）

| 頻率 | 事項 | 工具 |
|---|---|---|
| 每日（自動 00:00） | Bronze 同步 + Silver/Gold 增量 | `daily_etl_wrapper.sh`（排程主機 ❓ repo 未記載） |
| 每日（被動） | Grafana 告警郵件（Bronze Sync Monitoring） | Server 207 Grafana :9003 |
| 異常時 | 手動補跑 sync / backfill | Troubleshooting A1 恢復程序 |
| 對帳需求時 | CH vs MSSQL 對帳 | `audit_done_details.py` + Troubleshooting §E 判讀基準 |

## 3. 本次 Session 新確認的交接要點（既有手冊沒寫的）

- **雙 remote 雙身份**: GitLab（公司身份，日常）+ GitHub（個人身份 Han-lai，鏡像）。GitHub push 有三條強制規則（見 CLAUDE.md）。目前 5 個追蹤檔含 IP/舊密碼，**GitHub push 被此問題阻塞中**。
- **排程環境的環境變數是單點故障**: 6 月三次事故都是排程環境缺 `MSSQL_PASSWORD`。交接時必須確認排程主機上 `MSSQL_PASSWORD`、`CLICKHOUSE_HOST`、`CLICKHOUSE_PASSWORD` 的設定方式與位置。❓ 排程主機資訊需向前任確認並補寫入 `docs/02_deployment/`。
- **`_0503` 表後綴會再改版**: DBA 更版來源表時，只改 `sync_tables.yaml` 的 `source` 欄位（歷史: _0108→_0202→_0503）。
- **V3/V4 邊界 2026-04-01 是硬編碼**: 在兩支 summary SQL 內。任何「歷史數字不對」的問題先確認落在哪側管線。
- **檔案已刪未 commit**: 工作目錄中 README.md、claude.md（舊版，內容過時）、兩個 pptx、requirements-dev.txt、cube archive 等處於已刪除未 commit 狀態——commit 前需使用者確認刪除意圖。❓
- **未 commit 修改清單**: 見 `memory-bank/activeContext.md`「待辦」最末段（環境變數化 5 檔 + fail-loud + monitoring compose + 本知識庫）。

## 4. 需要業務決策的懸案（不要擅自決定）

| 懸案 | 選項 | 影響 |
|---|---|---|
| memory-bank 的 GitHub 去留 | A. 從 GitHub 追蹤移除（.gitignore）；B. 每次 push 前人工清洗 | 機敏資訊暴露面 |
| full sync 原子化改造 | 暫存表+EXCHANGE TABLES 方案的實施時點 | 停機窗口與測試成本 |
| L7 人員使用率是否轉正 | 對應 cube 檔案 + 來源表 DDL 補進 schema/（cube 檔案曾為 untracked 副本，2026-07 清理暫存檔時已移除） | 第二 KPI 上線 |
