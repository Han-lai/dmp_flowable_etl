# Project Context

## 用途
記錄專案的「現狀」，讓 AI Agent 快速理解背景。

## 何時更新
- 專案目標改變時
- 資料來源改變時
- 技術棧改變時

## ❌ 不該寫的內容
- 未來計畫
- 可能的需求
- 優化方向

---

## 專案名稱
DMP Flowable 資料同步

## 當前階段
🎉 **已完成** (MVP Complete)

## 專案目標
1. ~~探索真實 MSSQL 資料表結構~~ ✅
2. ~~建立本機 MSSQL Docker Sandbox 測試環境~~ ✅
3. ~~將 MSSQL 資料同步到 ClickHouse Bronze 層~~ ✅
4. ~~建立 Silver 層 RMV（每日自動刷新）~~ ✅
5. ~~建立 Gold 層快照表（歷史趨勢）~~ ✅
6. ~~建立 Cube.js 語意層 API~~ ✅
7. ~~驗證 11 個業務指標~~ ✅

## 資料來源

| Database | 用途 | 表數量 |
|----------|------|--------|
| APP_SRV_BPM | Flowable 流程資料 | 5 |
| APP_SRV_COMMON | DMP 人員/組織資料 | 13 |

## 技術棧
- 來源：MSSQL Server（真實 + Mock Docker）
- 目標：ClickHouse
- 同步方式：JDBC Bridge
- 部署：Docker Compose / Portainer

## Docker 服務

| 服務 | 位置 | 用途 |
|------|------|------|
| ClickHouse + JDBC Bridge | `docker/docker-compose.yml` | 資料倉儲 |
| MSSQL Mock | `docker/mssql-mock/docker-compose.yml` | 本機測試 |

## 連線資訊

### ClickHouse（VM）
- Host: REDACTED_IP
- Port: 8123
- User: default
- Password: clickhouse123

### MSSQL Mock（本機）
- Host: localhost
- Port: 1433
- User: sa
- Password: YourStrong@Passw0rd

## 目前狀態
- [x] MSSQL 連線測試完成
- [x] 資料表結構探索完成（16 張表，完整 schema）
- [x] Bronze 層 DDL 建立完成
- [x] 同步 SQL 腳本建立完成
- [x] ClickHouse Docker 部署完成（本機 Portainer）
- [x] MSSQL Mock Docker 部署完成（本機）
- [x] MSSQL Mock 資料複製完成（每表 10 筆測試資料）
- [x] JDBC Bridge Docker 部署完成
- [x] JDBC Bridge datasource 設定完成（指向真實 MSSQL）
- [x] JDBC Bridge 與 ClickHouse 整合測試完成
- [x] 首次全量同步執行完成（16 張表，2,134,433 筆）
- [x] 資料驗證完成（MSSQL vs ClickHouse 比對）
- [x] JDBC Bridge vs Airbyte 方案比較完成

## 第一階段完成狀態
**完成日期**：2024-12-18

### 同步成果
| 指標 | 數值 |
|------|------|
| 同步表數 | 16 張 |
| 總筆數 | 2,134,433 筆 |
| 同步時間 | 1 分 5 秒 |
| 平均速度 | 32,837 筆/秒 |
| 儲存空間 | ~137 MB |

### 方案比較結論
- JDBC Bridge 同步速度為 Airbyte 的 **7.7 倍**
- JDBC Bridge 儲存空間節省 **30%**
- 建議採用「混合式方案」：大表用 Airbyte 增量同步，小表用 JDBC Bridge 全量同步

## 已建立的腳本 (2024-12-24 整理後)

### 正式工具 (12 個，2024-12-24 二次整理後)

| 類別 | 腳本 | 用途 |
|------|------|------|
| 環境檢查 | `check_my_env.py` | 環境診斷工具 |
| | `check_benchmark_tables.py` | Benchmark 資料範圍驗證 |
| | `check_rmv_status.py` | RMV 刷新狀態監控 |
| | `check_silver_tables.py` | Silver 層表格列表 |
| | `check_view_rmv_consistency.py` | View vs RMV 一致性驗證 |
| 比對驗證 | `compare_data_accuracy.py` | View vs RMV 資料正確性 |
| | `compare_view_rmv.py` | View vs RMV 效能比較 |
| | `compare_with_benchmark.py` | Benchmark 比對驗證 |
| 建置/查詢 | `create_rmv.py` | RMV 建置工具 |
| | `query_metrics.py` | 指標查詢工具 (View) |
| | `query_metrics_rmv.py` | 指標查詢工具 (RMV) |
| | `update_silver_views.py` | View 更新工具 |

### 歸檔腳本 (scripts/archive/)

| 腳本 | 原因 |
|------|------|
| `check_clickhouse.py` | 早期 POC 測試 |
| `check_jdbc_bridge.py` | 早期 POC 測試 |
| `check_pk.py` | 一次性 PK 探索 |
| `check_target_data.py` | Mock 環境測試 |
| `compare_databases.py` | Airbyte vs JDBC 比較 |
| `copy_data_to_mock.py` | Mock 環境建置 |
| `explore_mssql.py` | 早期 MSSQL 探索 |
| `test_target_connection.py` | Mock 連線測試 |
| `compare_17_metrics.py` | 邏輯驗證已完成 |
| `compare_formula.py` | 邏輯驗證已完成 |
| `logic_audit.py` | 邏輯驗證已完成 |
| `logic_audit_detail.py` | 邏輯驗證已完成 |
| `metric_level_audit.py` | 被 v2 取代 |
| `metric_level_audit_v2.py` | 邏輯驗證已完成 |
| 其他 6 個 | 一次性驗證/已整合 |

## 第二階段：Silver Layer 建立

### 完成日期：2024-12-23

### 表格統計

| 層級 | 類型 | 數量 |
|------|------|------|
| Bronze | Table | 16 張 (使用 5 張) |
| Silver | View | 4 張 (V_*) |
| Silver | RMV | 4 張 (RMV_*) |

### 使用的 Bronze 表 (5 張)

| 表 | 用途 |
|-----|------|
| `bpm_act_hi_procinst` | 流程實例歷史 |
| `bpm_act_hi_taskinst` | 任務實例歷史 |
| `bpm_act_hi_varinst` | 流程變數 (plant/factory/region) |
| `bpm_act_re_procdef` | 流程定義 (流程名稱) |
| `common_hr_employee` | 員工資料 (部門) |

### 已建立的 Silver Views (4 張)

| View | Grain | 用途 |
|------|-------|------|
| `silver.V_PROC_VARIABLES_PIVOTED` | PROC_INST_ID | 流程變數樞紐化 |
| `silver.V_HI_PROC_TASK_NODE` | Task ID | 任務節點層，含狀態/時長/部門/廠區 |
| `silver.V_HI_PROCINST_NODE` | PROC_INST_ID | 流程實例層，含階層/狀態 |
| `silver.V_HI_BIZ_EVENT_INFO` | BUSINESS_KEY | 業務事件層，聚合統計 |

### 已建立的 Silver RMV (4 張)

| RMV | 筆數 | 刷新頻率 |
|-----|------|----------|
| `silver.RMV_PROC_VARIABLES_PIVOTED` | 12,922 | 每天 |
| `silver.RMV_HI_PROC_TASK_NODE` | 48,034 | 每天 |
| `silver.RMV_HI_PROCINST_NODE` | 16,075 | 每天 |
| `silver.RMV_HI_BIZ_EVENT_INFO` | 3,349 | 每天 |

### View vs RMV 效能比較

| 查詢 | View (ms) | RMV (ms) | 加速比 |
|------|-----------|----------|--------|
| 在途任務總數 | 147 | 15 | 10.1x |
| TASK_STATUS 分布 | 123 | 14 | 9.1x |
| 在途任務-依廠區 | 110 | 12 | 9.2x |
| 自動完成率 | 95 | 11 | 8.6x |

### View vs RMV 資料正確性

| 指標 | View | RMV | 一致 |
|------|------|-----|------|
| 總筆數 - TASK_NODE | 48,034 | 48,034 | ✅ |
| 總筆數 - PROCINST_NODE | 16,075 | 16,075 | ✅ |
| 總筆數 - BIZ_EVENT_INFO | 3,349 | 3,349 | ✅ |
| 在途任務數 | 10,314 | 10,314 | ✅ |
| DONE 任務數 | 13,744 | 13,744 | ✅ |
| DONE_AUTO 任務數 | 20,849 | 20,849 | ✅ |
| CANCELLED 任務數 | 3,127 | 3,127 | ✅ |
| 在途業務事件數 | 2,284 | 2,284 | ✅ |
| 自動完成率 | 60.27% | 60.27% | ✅ |

### View 建立順序

```
1. V_PROC_VARIABLES_PIVOTED (無依賴)
2. V_HI_PROC_TASK_NODE (依賴 1)
3. V_HI_PROCINST_NODE (依賴 1)
4. V_HI_BIZ_EVENT_INFO (無依賴)
```

### 已驗證的指標 (17 個)

| 狀態 | 指標 |
|------|------|
| ✅ | 業務事件總歷時、流程執行總時間、任務處理總時間 |
| ✅ | 流程總歷時、任務閒置時長、個人處理時長、任務總歷時 |
| ✅ | 在途業務事件總數、在途任務總數 |
| ✅ | 平均業務事件總歷時、平均任務處理時長 |
| ✅ | 在途任務數-依部門、依廠區、依地區、依人員 |
| ✅ | 在途流程健康度快照 |
| ✅ | 事件自動完成率 |
| ⏸️ | 逾期在途業務事件數 (缺 HealthSettings 表) |

## 第三階段：邏輯等價性驗證

### 完成日期：2024-12-24

### 驗證結論

| 比較項目 | 結果 |
|---------|------|
| Benchmark vs View | ✅ 邏輯等價 |
| Benchmark vs RMV | ✅ 邏輯等價 |
| View vs RMV | ✅ 完全一致 |

### 筆數差異說明

| 環境 | TASK_NODE | PROCINST_NODE | 資料截止日 |
|------|-----------|---------------|-----------|
| Benchmark | 61,741 | 15,529 | 2025-12-10 |
| View/RMV | 48,508 | 16,431 | 2025-12-24 |

**差異原因**: 資料同步時間點不同，非邏輯問題

## 第四階段：Bronze 增量同步

### 完成日期：2026-01-02

### 增量同步架構

```
┌─────────────────────────────────────────────────────────────┐
│                    增量同步流程                              │
├─────────────────────────────────────────────────────────────┤
│  1. 讀取 Watermark (上次同步時間)                            │
│  2. 從 MSSQL 拉取增量資料 (WHERE tracking_col > watermark)   │
│  3. INSERT INTO ClickHouse (ReplacingMergeTree 處理重複)     │
│  4. 更新 Watermark                                          │
│  5. RMV 自動刷新 Silver 層                                   │
└─────────────────────────────────────────────────────────────┘
```

### 增量同步表 (5 張大表)

| 表名 | 資料量 | 追蹤欄位 | 主鍵 |
|------|--------|----------|------|
| ACT_HI_PROCINST | 17K | START_TIME_ | ID_ |
| ACT_HI_TASKINST | 50K | LAST_UPDATED_TIME_ | ID_ |
| ACT_HI_IDENTITYLINK | 598K | CREATE_TIME_ | ID_ |
| ACT_HI_VARINST | 660K | LAST_UPDATED_TIME_ | ID_ |
| FlowableTaskStats | 1.3M | LastUpdatedTime | tuple() |

### 全量同步表 (13 張小表)

- ACT_RE_PROCDEF, HR_Employee, ProcessRoleUserMapping
- ProcessRoleGroup, ProcessRoleGroupMapping, EmpNodeRoleMapping
- EmpOrgInfoMapping, EmpUserGroupMapping, UserGroup
- DMPFunctionConfig, DMPFunctionClientMapping
- MDM_FACTORY_AREA_MASTER, MDM_MFG_PLANT_MASTER

### 效能比較

| 方式 | 腳本 | 耗時 |
|------|------|------|
| 全量同步 | `sync/sync_to_clickhouse.py` | ~68 秒 |
| 增量同步 | `sync/sync_incremental.py` | ~10 秒 |

### Watermark 表

```sql
bronze._sync_watermark
├── table_name (String)
├── last_sync_time (DateTime64)
├── sync_time (DateTime64)
└── row_count (UInt64)
```

---

## 第八階段：技術驗證與專案總結

### 完成日期：2026-01-13

### ClickHouse 原生增量 MView JOIN 行為驗證

**測試腳本**：`scripts/test_imv_join_behavior.py`

**測試結果**：

| 測試場景 | 結果 |
|---------|------|
| 主表 INSERT 時 | ✅ MView 觸發，JOIN 成功 |
| JOIN 表 INSERT 後 | ❌ 已寫入的資料不會更新 |
| JOIN 表 UPDATE 後 | ❌ 已寫入的資料不會更新 |

**結論**：
- ClickHouse 原生增量 MView（TO table 語法）只監控主表
- JOIN 表的變更不會觸發已寫入資料的更新
- 因為 11 個指標都需要 JOIN 維度表，選擇全量刷新確保資料一致性

### 專案總結報告

**報告文件**：`docs/project_summary_report.md`

**專案成果**：

| 階段 | 內容 | 狀態 |
|------|------|------|
| Bronze 層 | 18 張表同步（5 大表增量 + 13 小表全量） | ✅ 完成 |
| Silver 層 | 4 張 View + 4 張 RMV（每日自動刷新） | ✅ 完成 |
| Gold 層 | 2 張每日快照表（保留 365 天） | ✅ 完成 |
| Cube.js | 語意層 API（7 個 Gold 指標 + VTeam 維度樹） | ✅ 完成 |
| 指標驗證 | 11 個指標與 Benchmark 邏輯等價 | ✅ 完成 |

**關鍵數據**：

| 指標 | 數值 |
|------|------|
| 同步資料量 | 2,134,433 筆 |
| 全量同步耗時 | ~68 秒 |
| 增量同步耗時 | ~10 秒 |
| RMV 查詢加速 | 4-10 倍 |
| 資料延遲 | 最多 24 小時 |
| Gold 快照保留 | 365 天 |

---

## 目前痛點

### 🔴 資料層面
1. **Benchmark 資料過時** - 最後同步 2025-12-10，無法做即時比對
2. **缺少 HealthSettings 表** - 無法實作逾期判斷邏輯

### 🟡 驗證層面
1. **欄位名稱不一致** - Benchmark 用 snake_case，我的用 UPPER_CASE
2. **狀態值不一致** - Benchmark 用 TERMINATE，我的用 TERMINATED
3. **無自動化比對** - 目前靠手動執行腳本比對

### 🟢 維運層面
1. **RMV 刷新監控** - 需確認每日刷新是否成功
2. **資料延遲** - RMV 資料最多延遲 24 小時

---

## 未來可能需要驗證的地方

### 短期 (下次同步後)
- [ ] Benchmark 更新後重新比對筆數
- [ ] 驗證新增資料的狀態分布是否合理
- [ ] 確認 RMV 刷新機制穩定性

### 中期 (功能擴展時)
- [ ] 新增指標時的邏輯等價性驗證
- [ ] 逾期判斷邏輯 (待 HealthSettings 表)
- [ ] 跨流程關聯分析 (SUPER_ID / DEPTH)

### 長期 (生產環境)
- [ ] 資料品質監控告警
- [ ] 效能基準線建立

---

## 第五階段：指標業務定義文件

### 完成日期：2026-01-02

### 文件內容

建立完整的指標業務定義文件（`docs/metric_definitions.md`），包含：

**維度階層關係：**
```
FACTORY (工廠)
  └── PLANT (產品線)
        └── LINE_NAME (線別)
```

**已定義的 11 個指標：**

| 分類 | 指標 | 聚合方式 |
|------|------|----------|
| 存量指標 | 在途業務事件總數、在途任務總數 | 可 SUM |
| 比率指標 | 事件自動完成率 | 需重新計算 |
| 分布指標 | TASK_STATUS 分布 | 可 SUM |
| 維度分析 | 在途任務數（依廠區/部門/人員）、在途流程健康度快照 | 可 SUM |
| 時長指標 | 平均業務事件總歷時、平均任務處理時長 | 需重新計算 |
| 健康度指標 | 依流程的自動完成率 | 需重新計算 |

**關鍵設計原則：**
- 快照指標：不可跨時間加總，需每日快照
- 比率指標：不可直接平均，需用分子分母重新計算
- 維度聚合：明確標示可 SUM 或需重新計算
- 去重邏輯：按 BUSINESS_KEY 或 TASK_ID 去重

**Gold 層建議：**
- 建立每日快照表
- 分子分母分開存
- 支援任意維度重新計算

---

## 第六階段：Cube.js 語意層

### 完成日期：2026-01-12

### Cube.js 架構

```
Silver RMV ──► Cube.js (Semantic Layer) ──► REST API / Playground
                    │
                    ├── ProcTaskNode (任務層)
                    ├── ProcInstNode (流程層)
                    └── BizEventInfo (業務事件層)
```

### 連線資訊

| 服務 | Port | 用途 |
|------|------|------|
| Cube.js API | 4002 | REST API |
| Cube.js Playground | 4003 | 查詢介面 |

### Cube Model 檔案

| 檔案 | Cube | 來源 |
|------|------|------|
| `cube/model/cubes/cube_proc_task_node.js` | ProcTaskNode | RMV_HI_PROC_TASK_NODE |
| `cube/model/cubes/cube_proc_inst_node.js` | ProcInstNode | RMV_HI_PROCINST_NODE |
| `cube/model/cubes/cube_biz_event_info.js` | BizEventInfo | RMV_HI_BIZ_EVENT_INFO |

### Gold 指標清單 (7 個)

| 指標 | Cube | 定義 |
|------|------|------|
| `inProgressTaskCount` | ProcTaskNode | 在途任務數 (TODO + DOING) |
| `autoCompleteRate` | ProcTaskNode | 自動完成率 |
| `avgWorkDuration` | ProcTaskNode | 平均任務處理時長 |
| `inProgressCount` | ProcInstNode | 在途流程數 |
| `completedCount` | ProcInstNode | 已完成流程數 |
| `inProgressEventCount` | BizEventInfo | 在途業務事件數 |
| `avgTotalDuration` | BizEventInfo | 平均業務事件總歷時 |

### 指標治理

- 已建立 `docs/semantic_gold_governance.md` - 指標治理文件
- 已建立 `docs/cube_gold_layer_audit.md` - Gold 層審查報告
- 已建立 `docs/metrics_in_cubejs.md` - 指標應用手冊

### Gold 層判定結果

| 分類 | 數量 | 比例 |
|------|------|------|
| 🥇 Gold 指標 | 7 個 | 37% |
| 🥈 Silver 包裝 | 12 個 | 63% |

---

## 第七階段：Physical Gold 快照層

### 完成日期：2026-01-12

### Gold 表結構

| 表 | 用途 | 首次快照筆數 |
|-----|------|-------------|
| `gold.DAILY_METRICS_SNAPSHOT` | 任務+流程指標 | 1,190 筆 |
| `gold.DAILY_BIZ_EVENT_SNAPSHOT` | 業務事件指標 | 38 筆 |

### 設計規格

| 項目 | 規格 |
|------|------|
| 快照頻率 | 每日 10:00 (Asia/Taipei) |
| 保留期限 | 365 天 (TTL 自動刪除) |
| 維度組合 | FACTORY, PLANT, PROC_DEF_NAME |
| 表引擎 | ReplacingMergeTree(_version) |
| 時區 | Asia/Taipei (UTC+8) |

### 首次快照摘要 (2026-01-12)

| 指標 | 數值 |
|------|------|
| 在途任務數 | 11,040 |
| 自動完成率 | 61.36% |
| 在途流程數 | 7,601 |
| 已完成流程數 | 6,762 |
| 在途業務事件數 | 2,465 |
| 平均業務事件歷時 | 54.83 小時 |

### Cube.js Gold 層 Model

| Cube | 來源表 | 用途 |
|------|--------|------|
| DailyMetricsSnapshot | gold.DAILY_METRICS_SNAPSHOT | 歷史趨勢（任務+流程） |
| DailyBizEventSnapshot | gold.DAILY_BIZ_EVENT_SNAPSHOT | 歷史趨勢（業務事件） |

### Cube.js Views（對外 API）

| View | 來源 Cube | 用途 |
|------|-----------|------|
| HistoricalTrends | DailyMetricsSnapshot | 歷史趨勢查詢介面 |
| HistoricalBizEvents | DailyBizEventSnapshot | 業務事件歷史趨勢介面 |

### 相關檔案

| 檔案 | 用途 |
|------|------|
| `sql/07_create_gold_snapshot.sql` | Gold 表 DDL |
| `scripts/create_gold_snapshot.py` | 快照執行腳本 |
| `cube/model/cubes/cube_daily_metrics_snapshot.js` | Gold Cube |
| `cube/model/cubes/cube_daily_biz_event_snapshot.js` | Gold Cube |
| `cube/model/views/view_historical_trends.js` | 歷史趨勢 View |

---

## Scripts 使用指南

### 資料流執行順序

| 順序 | 層級 | 執行時間 | 觸發方式 | 執行指令 |
|------|------|----------|----------|----------|
| 1 | **Bronze 同步** | 依需求（建議每日 09:00 前） | 手動 | `python sync/sync_incremental.py all` |
| 2 | **Silver RMV 刷新** | 每日 02:00 UTC (10:00 Asia/Taipei) | 自動 | ClickHouse 自動執行 |
| 3 | **Gold 快照** | 每日 10:00 Asia/Taipei 後 | 手動 | `python scripts/create_gold_snapshot.py` |

### 建議執行時間線

```
09:00  執行 Bronze 同步
10:00  RMV 自動刷新完成（02:00 UTC）
10:30  執行 Gold 快照
       ↓
       Cube.js API 可查詢最新資料
```

### 檢查 RMV 刷新狀態 (SQL)

```sql
SELECT 
    view,
    status,
    last_refresh_time,
    next_refresh_time
FROM system.view_refreshes
WHERE database = 'silver';
```

### 日常操作流程

```
Step 1: 同步 Bronze（增量）
python sync/sync_incremental.py all
        │
        ▼
Step 2: 檢查 RMV 刷新狀態（可選）
python scripts/check_rmv_status.py
        │
        ▼
Step 3: 執行 Gold 快照
python scripts/create_gold_snapshot.py
        │
        ▼
Step 4: 查詢指標
python scripts/query_metrics_rmv.py
```

### 完整 Scripts 清單

| 階段 | Script | 用途 | 使用頻率 |
|------|--------|------|----------|
| **Bronze 同步** | `sync/sync_incremental.py` | 增量+全量混合同步 | 日常 |
| | `sync/sync_to_clickhouse.py` | 全量同步（舊版） | 首次/重建 |
| **Silver 管理** | `scripts/check_rmv_status.py` | 檢查 RMV 刷新狀態 | 日常 |
| | `scripts/create_rmv.py` | 建立 RMV | 首次 |
| | `scripts/update_silver_views.py` | 更新 View 定義 | 維護 |
| **Gold 快照** | `scripts/create_gold_snapshot.py` | 建立每日快照 | 日常 |
| **指標查詢** | `scripts/query_metrics_rmv.py` | 查詢 17 指標（RMV） | 日常 |
| | `scripts/query_metrics.py` | 查詢 17 指標（View） | 備用 |
| **驗證比對** | `scripts/compare_with_benchmark.py` | 與 Benchmark 比對 | 驗證 |
| | `scripts/compare_view_rmv.py` | View vs RMV 比對 | 驗證 |
| | `scripts/compare_data_accuracy.py` | 資料準確性比對 | 驗證 |
| **環境檢查** | `scripts/check_my_env.py` | 檢查連線環境 | 除錯 |
| | `scripts/check_benchmark_tables.py` | 檢查 Benchmark 表 | 除錯 |
| | `scripts/check_silver_tables.py` | 檢查 Silver 表 | 除錯 |
| **分析工具** | `scripts/check_mssql_columns.py` | 查詢 MSSQL 欄位結構 | 分析 |
| | `scripts/check_tracking_behavior.py` | 驗證追蹤欄位行為 | 分析 |
