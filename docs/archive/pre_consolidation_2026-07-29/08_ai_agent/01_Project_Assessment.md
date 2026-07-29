# Project Quick Assessment（專案快速評估）

**建立日期**: 2026-07-03（Fable 5 Project Intelligence Session）
**驗證基準**: 以工作目錄程式碼為準（commit `5d2f4d7`），全部證據標註檔案路徑
**標記說明**: ✅ 已驗證（讀過程式碼/設定）｜⚠ 推測（有間接證據）｜❓ 尚未確認（需人工或連線驗證）

---

## 1. 專案目的與定位

| 項目 | 內容 | 狀態 |
|------|------|------|
| **專案目的** | 將 Flowable BPM（MSSQL）的流程簽核數據，經 ETL 整合至 ClickHouse 三層數據倉儲（Bronze/Silver/Gold），產出製造業產線管理指標（L5 任務完成率、7 日滾動積壓量 ACC 等），供 BI Dashboard 即時決策 | ✅ |
| **商業定位** | 企業內部 AIT / Data Engineering 的製造數據中台專案，服務對象為產線管理層 | ✅ |
| **系統定位** | 分析型（OLAP）旁路系統：**唯讀**抽取生產 MSSQL，不回寫來源；查詢流量一律經 Cube.js 語意層，ClickHouse 不直接對外 | ✅ |
| **成熟度** | 生產運作中（每日自動排程），架構版本 V4.4（Phase 4 預聚合 + 監控建置完成） | ✅ |

## 2. Repository Structure（一句話版）

```
scripts/etl/     三支核心引擎：setup_schema.py（DDL 部署）→ sync_unified_odbc.py（MSSQL→Bronze）→ execute_etl.py（Silver/Gold 運算）
scripts/etl/config/  三個 YAML：infra_config / sync_tables（19 張表）/ pipeline_config（8 個 phase）
sql/etl/schema/  ClickHouse DDL（00~06；05/07 為空殼 DDL 檔案，2026-07 已刪除，L7 待重新設計）
sql/etl/dml/     8 支業務邏輯 SQL 模板（{start_ts}/{end_ts} 佔位符）
cube/model/cubes/  Cube.js 語意模型（L5TaskPeriodic / Pivot / Details）
api/             FastAPI（L5 報表 API，main.py）
infra/           docker-compose：api / cube / monitoring(Grafana+Prometheus) / clickhouse 設定
tests/           pytest 單元測試（6 個測試檔）
docs/            人類向技術文件庫（00~07 編號體系）
memory-bank/     AI 工作記憶（activeContext / progress 為最即時的狀態來源）
.kiro/specs/     歷史需求規格（部分與現行程式碼不一致，見 §6）
prd_audit/       對帳明細匯出產物（未追蹤，中信心暫留）
```
> 2026-07 清理：未追蹤的一次性/暫存內容（`logs/output/`、`archive/`、`prd_mssql/`、`.pytest_cache/`、`__pycache__/`、`.deltacoder/`、`api/reports.js`、`cube/model/cubes/staff_usage.js`）已從工作目錄移除，皆非 git 追蹤內容，刪除不影響版本歷史。

## 3. 技術架構摘要（詳見 [02_Code_Intelligence.md](02_Code_Intelligence.md)）

- **資料流**: MSSQL（`_0503` 後綴表）→ ODBC Table Engine → `bronze`（19 表）→ `silver.mv_varinst_pivoted` + `silver.mv_fact_task_vx`（Super Silver 統一事實表）→ `gold` 4 張物理表 → `gold.rmv_l5_task_summary`（預聚合整數，Cube.js 唯一入口）✅
- **所有層皆為 ReplacingMergeTree** 物理表 + 時間視窗批次 INSERT，沒有任何即時 Materialized View（名稱裡的 `mv_`/`rmv_` 是歷史命名殘留）✅
- **雙管線 Gold Summary**: `≤2026-03-31` 走 V3 歷史邏輯（`backfill_gold_summary_historical.sql`）、`≥2026-04-01` 走 V4 Cohort 邏輯（`backfill_gold_summary.sql`），以日期硬邊界分流 ✅
- **記憶體防禦體系**: 低記憶體模式（1 thread、spill to disk、grace_hash join）+ OOM 自動視窗切半遞迴 + 空窗跳過不標記成功（自癒）✅

## 4. 相依服務

| 服務 | 角色 | 位置 | 狀態 |
|------|------|------|------|
| MSSQL `APP_SRV_BPM` / `APP_SRV_COMMON` | 唯一資料來源（生產庫，**嚴禁寫入/刪表**） | DSN `MSSQL_DSN`（`infra/clickhouse/odbc/odbc.ini`） | ✅ |
| ClickHouse v25.8 | 數倉本體（Server 76，Docker 11GiB / 可用約 6GiB） | host 由 `infra/.env` 提供 | ✅ |
| Cube.js | 語意層閘道（port 4002 REST / 4003 Playground） | `infra/cube/docker-compose.yml` | ✅ |
| FastAPI | L5 報表 API（port 7088→8000） | `infra/api/docker-compose.yml` | ✅ |
| Node.js BFF | Auth + Cube 轉發（機制詳見 [Troubleshooting C2](05_Troubleshooting.md)） | 部署在另一個前端專案，**不在本 repo**（曾有的參考副本 `api/reports.js` 已於 2026-07 清理移除） | ⚠ |
| Grafana + Prometheus | 監控（Server 207，port 9003/9011） | `infra/monitoring/docker-compose.yml` | ✅ |
| 排程器 | 每日 00:00 執行 `daily_etl_wrapper.sh` | **排程機制與所在主機未寫入 repo** | ❓ |

## 5. 最大技術風險（依嚴重度排序）

### 🟠 R1: 機敏資訊回流版控（2026-07-06 已清洗至 tip，歷史分叉風險仍在）
- **原況**: HEAD 曾有 5 個追蹤檔含內部 IP（`memory-bank/progress.md` 另含已退役 ClickHouse 舊密碼）——2026-06-29 filter-repo 清洗後的新 commit 又寫回。
- **已處理（commit `263dfa1`）**: 5 檔改用 `<CLICKHOUSE_HOST>`/`<MONITOR_HOST>` 佔位符；monitoring compose 參數化（必填 env，值在未追蹤的 `infra/monitoring/.env`）；並還原被誤刪的 `.gitignore`（其缺失曾使 `infra/.env` 失去忽略保護）。
- **殘留風險**: 本地 master（未改寫歷史，歷史層仍含舊機敏字串）與 origin/master（GitHub 上 filter-repo 清洗後的乾淨歷史）**完全分叉**。**嚴禁直接 push/force-push 本地 master 到 GitHub**；正確流程=從 origin/master 建分支 cherry-pick 新 commits 後推送（見 [06_AI_Agent_Workflow.md](06_AI_Agent_Workflow.md) §禁區）。

### 🔴 R2: `sync_full_table` TRUNCATE-before-INSERT 無回滾（結構性）
- **證據**: `scripts/etl/sync_unified_odbc.py:334`（`TRUNCATE TABLE` 後直接 INSERT，任何失敗留空表）。2026-06-17/29/30 三次事故根因（`MSSQL_PASSWORD` 缺失時 15 張維度表被清空）。
- **現況**: 已加 fail-loud（`sys.exit(1)`，`sync_unified_odbc.py:518-524`）讓失敗可見，但**結構性風險未修**——非密碼類的 INSERT 失敗仍會留空表。
- **建議**: 改為「寫入暫存表 → 驗證筆數 → `EXCHANGE TABLES`」原子替換。已在 memory-bank 待辦中。

### 🟠 R3: Gold Summary 為管線最後階段，ETL 執行期間 Cube 查詢短暫落後
- **證據**: `pipeline_config.yaml` 中 `gold_summary` 為最後 phase；`memory-bank/techContext.md` 明載此已知風險，目前接受。✅

### 🟠 R4: 單機無 HA、無備份策略文件
- ClickHouse 單節點（Server 76），repo 內找不到備份/還原 SOP。❓（可能存在於 infra 團隊，repo 未記載）

### 🟠 R5: Bronze `full` 策略表無歷史保留
- 每日 TRUNCATE 重寫，維度表（HR/MDM）的歷史版本不可回溯；若需做 SCD 分析將無資料。⚠（目前業務未要求，屬設計取捨）

## 6. 已知不一致與技術債（AI 最容易誤判的地方）

| # | 項目 | 事實（以程式碼為準） | 誤導來源 |
|---|------|---------------------|----------|
| 1 | **315 工單規則（已決策，2026-07-06）** | `backfill_silver.sql:75` 的 V1 強制歸類前綴**只有** `196,199,200,210,212,213`，**不含 315**——經查證 Silver 表 mo_number 前綴 315 共 69 萬筆（88.5% 現為 V3），套用 `.kiro` spec 會造成大規模重新分類，且與既有變更記錄「315% 規則致跨流程誤判」吻合，**維持現狀不套用**，`.kiro` spec 視為過時歷史規格 | `memory-bank/systemPatterns.md` 已修正錯誤記錄（原誤稱已含 315） |
| 2 | **`sql/etl/dml/README.md` 失真** | 引用不存在的 `sync_gold_unified.sql`；宣稱 `backfill_gold.sql` 已棄用（實際上 `pipeline_config.yaml:40` 仍在用）；未提及兩支 summary SQL | 本次已修正 ✅ |
| 3 | **Bronze 表數** | `sync_tables.yaml` 實為 **19** 張（18 + 2026-06 新增 `kpi_user_config_log`） | `docs/01_architecture/Architecture_Overview.md` 與 README 寫 18 張 |
| 4 | **`mv_`/`rmv_` 前綴** | 全部是普通 ReplacingMergeTree 物理表，**不是** Materialized View / Refreshable MV | 命名歷史殘留（Server 207 時代曾是 RMV） |
| 5 | **ClickHouse port** | Python 腳本預設 8123；`infra/cube/docker-compose.yml` 與 `init_pipeline.sh` 預設 8121。實際依 `infra/.env` | ❓ 8121/8123 對應哪台伺服器的哪個 mapping 未在 repo 記載 |
| 6 | **根目錄 `claude.md`（舊）已在工作目錄刪除** | 其內容嚴重過時（引用不存在的 `sync_batches_consolidated.py`、`execute_ui_v2.py`、`scripts/validation/`），刪除合理；本次以新 `CLAUDE.md` 取代 | 舊 commit 中的 claude.md |
| 7 | **`.kiro/specs/` 整體** | 為歷史規格快照，未隨程式碼演進更新 | 直接照 spec 實作會與現行邏輯衝突 |
| 8 | **`memory-bank/productContext.md`** | 引用已改名的 `cube_l5_task_periodic_v2.js`（現為 `cube_l5_task_periodic.js`）、過時的 `_0108` 表後綴（現為 `_0503`） | 該檔案部分段落停留在早期版本 |
| 9 | **`docs/00_INDEX.md` 連結** | 部分連結檔名與實際檔名不符（如 `ETL_Transformation_Pipeline.md` 實為 `02_ETL_Transformation_Pipeline.md`） | ⚠ 點連結會 404，需按 `docs/03_metrics/` 實際檔名對照 |
| 10 | **task_status / task_create_date 欄位** | Silver 兩欄位已確認下游無引用（可清理候選），但仍在 schema 與 DML 中 | `memory-bank` 記載，尚未執行清理 |
| 11 | **Cohort 邏輯雙處維護** | 日/週/月結算條件同時存在於 `backfill_silver.sql`（status_* 欄位，供明細顯示）與 `backfill_gold_milestone.sql`（內聯條件，供 KPI 計算），並非共用 | 改其中一處而漏另一處會造成明細與 KPI 口徑漂移 |

## 7. 文件缺口

| 缺口 | 影響 | 建議 |
|------|------|------|
| 排程機制未文件化（誰在跑 `daily_etl_wrapper.sh`、哪台主機、cron 還是其他） | 事故時無法快速定位執行環境（6 月密碼事故即是排程環境變數缺失） | ❓ 需使用者補充，建議寫入 `docs/02_deployment/` |
| 備份/災難復原 SOP 缺失 | 單節點資料遺失無程序可循 | 建議建立 |
| Node.js BFF 的完整專案位置與部署方式 | 不在本 repo，僅間接記載於 Troubleshooting | ❓ 需使用者補充 |
| L7 人員使用率（`gold.tb_active_user_metrics`）狀態不明 | 來源表 DDL 不在 `sql/etl/schema/`（舊版 05/07 為引用已棄用表名 `gold.rmv_user_utilization` 的空殼檔案，2026-07 已刪除），對應 cube 檔案也已於 2026-07 清理移除 | ❓ 進行中功能，需向使用者確認現況與正式檔案位置 |

## 8. 綜合結論

本專案**程式碼品質與文件量高於平均**：三段式引擎 + YAML 設定驅動 + SQL 模板分離的架構清晰，`docs/` 有系統化的人類向文件，`memory-bank/` 有即時的狀態記錄。主要弱點是：(1) 文件間**版本漂移**（多處敘述落後程式碼，見 §6）、(2) 機敏資訊再次進入版控（R1）、(3) full sync 無原子性（R2）。

**未來 AI Session 的首要原則：程式碼與 YAML 是唯一真相；文件（含本知識庫）用於導航與背景，衝突時以程式碼為準並回頭修文件。**
