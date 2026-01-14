# CLAUDE.md - 專案快速上手指南

## 專案概述
DMP Flowable 資料同步專案，將 MSSQL 的 Flowable BPM 資料同步到 ClickHouse，建立 Bronze/Silver/Gold 層資料倉儲，並透過 Cube.js 提供 API。

## 目前狀態 (2026-01-14)

### 🎉 專案已完成

| 階段 | 內容 | 狀態 |
|------|------|------|
| Bronze 層 | 18 張表同步（5 大表增量 + 13 小表全量） | ✅ 完成 |
| Silver 層 | 4 張 View + 4 張 RMV（每日自動刷新） | ✅ 完成 |
| Gold 層 | 2 張每日快照表（保留 365 天） | ✅ 完成 |
| Cube.js | 語意層 API（7 個 Gold 指標 + VTeam 維度樹） | ✅ 完成 |
| 指標驗證 | 11 個指標與 Benchmark 邏輯等價 | ✅ 完成 |
| 技術驗證 | ClickHouse 原生增量 MView JOIN 行為測試 | ✅ 完成 |
| 專案報告 | 主管報告文件 | ✅ 完成 |

### 暫緩
- ⏸️ 逾期在途業務事件數 (缺 HealthSettings 表)
- ⏸️ 自動化排程 (目前手動執行)

---

## 整體架構

```
MSSQL ──► Bronze (18 表) ──► Silver (4 RMV) ──► Cube.js ──► 前端
                                    │
                                    └──► Gold (每日快照) ──► Cube.js
```

---

## 技術決策：為什麼用全量刷新而不是原生增量？

### ClickHouse 原生增量 MView 限制

透過測試腳本 (`scripts/test_imv_join_behavior.py`) 驗證：

| 測試場景 | 結果 |
|---------|------|
| 主表 INSERT 時 | ✅ MView 觸發，JOIN 成功 |
| JOIN 表 INSERT 後 | ❌ 已寫入的資料不會更新 |
| JOIN 表 UPDATE 後 | ❌ 已寫入的資料不會更新 |

### 結論

因為 11 個指標都需要 JOIN 維度表（部門、廠區、流程名稱），而維度表可能變更，所以選擇「每日全量刷新」確保資料一致性。即使未來維度表不再變更，因為表與表 JOIN 關係複雜，仍建議使用全量刷新。

---

## Cube.js 語意層

### 連線資訊

| 服務 | Port | 用途 |
|------|------|------|
| Cube.js API | 4002 | REST API |
| Cube.js Playground | 4003 | 查詢介面 |
| ClickHouse | 8121 | 資料來源 |

### Gold 指標清單 (7 個)

| 指標 | Cube | 定義 |
|------|------|------|
| `inProgressTaskCount` | ProcTaskNode | 在途任務數 |
| `autoCompleteRate` | ProcTaskNode | 自動完成率 |
| `avgWorkDuration` | ProcTaskNode | 平均任務處理時長 |
| `inProgressCount` | ProcInstNode | 在途流程數 |
| `completedCount` | ProcInstNode | 已完成流程數 |
| `inProgressEventCount` | BizEventInfo | 在途業務事件數 |
| `avgTotalDuration` | BizEventInfo | 平均業務事件總歷時 |

### 指標使用注意事項

- **avg/rate 指標不可直接平均**：需用分子分母重新計算
- **維度約束**：每個 Gold 指標有合法/禁止維度，詳見 `docs/semantic_gold_governance.md`

---

## Physical Gold 快照層

### 設計規格

| 項目 | 規格 |
|------|------|
| 快照頻率 | 每日 10:00 (Asia/Taipei) |
| 保留期限 | 365 天 |
| 維度組合 | FACTORY, PLANT, PROC_DEF_NAME |
| 表引擎 | ReplacingMergeTree(_version) |

### Gold 表

| 表 | 用途 | 首次快照 |
|-----|------|---------|
| `gold.DAILY_METRICS_SNAPSHOT` | 任務+流程指標 | 1,190 筆 |
| `gold.DAILY_BIZ_EVENT_SNAPSHOT` | 業務事件指標 | 38 筆 |

### 快照指標摘要 (2026-01-12)

| 指標 | 數值 |
|------|------|
| 在途任務數 | 11,040 |
| 自動完成率 | 61.36% |
| 在途流程數 | 7,601 |
| 已完成流程數 | 6,762 |
| 在途業務事件數 | 2,465 |
| 平均業務事件歷時 | 54.83 小時 |

### 相關檔案

| 檔案 | 用途 |
|------|------|
| `sql/07_create_gold_snapshot.sql` | Gold 表 DDL |
| `scripts/create_gold_snapshot.py` | 快照執行腳本 |

### 使用方式

```bash
# 初始化表結構
python scripts/create_gold_snapshot.py --init

# 執行今日快照
python scripts/create_gold_snapshot.py

# 指定日期快照
python scripts/create_gold_snapshot.py --date 2026-01-12
```

---

## 日常操作流程

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

### 操作步驟

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

---

## 增量同步架構

```
MSSQL ──► Bronze (ClickHouse) ──► Silver (RMV 自動刷新) ──► Metric 查詢
   │           │
   │     ReplacingMergeTree
   │     + _sync_time 欄位
   │           │
   └── Watermark 表記錄上次同步時間
```

### 增量同步表 (5 張大表)

| 表名 | 追蹤欄位 | 資料量 |
|------|----------|--------|
| ACT_HI_PROCINST | START_TIME_ | 17K |
| ACT_HI_TASKINST | LAST_UPDATED_TIME_ | 50K |
| ACT_HI_IDENTITYLINK | CREATE_TIME_ | 598K |
| ACT_HI_VARINST | LAST_UPDATED_TIME_ | 660K |
| FlowableTaskStats | LastUpdatedTime | 1.3M |

### 效能比較

| 方式 | 腳本 | 耗時 |
|------|------|------|
| 全量同步 | `sync/sync_to_clickhouse.py` | ~68 秒 |
| 增量同步 | `sync/sync_incremental.py` | ~10 秒 |

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

## 架構

```
Bronze (16 張表)              Silver (4 張 View + 4 張 RMV)
─────────────────────────────────────────────────────────────
bpm_act_hi_varinst ────────► V_PROC_VARIABLES_PIVOTED / RMV_PROC_VARIABLES_PIVOTED
                                    │
bpm_act_hi_taskinst ──┬────► V_HI_PROC_TASK_NODE / RMV_HI_PROC_TASK_NODE
bpm_act_hi_procinst ──┤
bpm_act_re_procdef  ──┤
common_hr_employee  ──┘

bpm_act_hi_procinst ──┬────► V_HI_PROCINST_NODE / RMV_HI_PROCINST_NODE
bpm_act_re_procdef  ──┘

bpm_act_hi_procinst ──┬────► V_HI_BIZ_EVENT_INFO / RMV_HI_BIZ_EVENT_INFO
bpm_act_hi_taskinst ──┤
bpm_act_re_procdef  ──┘
```

### View vs RMV 選擇

| 場景 | 建議 |
|------|------|
| 即時查詢、資料需最新 | View (V_*) |
| 報表查詢、效能優先 | RMV (RMV_*) |

---

## 連線資訊

### ClickHouse (你的環境)
- Host: REDACTED_IP:8121
- User: default / default

### ClickHouse (參考環境)
- Host: REDACTED_IP:8124
- User: ch_user / ch_strong_password_change_me
- Database: flowable_analytics

---

## 重要檔案

| 檔案 | 用途 |
|------|------|
| `sql/05_create_silver_views.sql` | Silver View DDL |
| `sql/06_create_silver_rmv.sql` | Silver RMV DDL |
| `docs/architecture_comparison.md` | 完整架構文件 |
| `docs/data_flow_guide.md` | 資料流程指南 (Bronze→Silver→Metric) |
| `docs/metric_query_summary.md` | 指標查詢統整 |
| `docs/logic_equivalence_audit_report.md` | 邏輯等價性審核報告 |
| `docs/semantic_gold_governance.md` | 指標治理文件 |
| `docs/cube_gold_layer_audit.md` | Gold 層審查報告 |
| `docs/metrics_in_cubejs.md` | Cube.js 指標應用手冊 |
| `memory/project_context.md` | 專案進度 |
| `memory/decisions_log.md` | 決策紀錄 |

### Cube.js 檔案

| 檔案 | 用途 |
|------|------|
| `cube/docker-compose.yml` | Cube.js Docker 設定 |
| `cube/.env.example` | 環境變數範例 |
| `cube/model/cubes/cube_proc_task_node.js` | 任務層 Cube (Silver) |
| `cube/model/cubes/cube_proc_inst_node.js` | 流程層 Cube (Silver) |
| `cube/model/cubes/cube_biz_event_info.js` | 業務事件層 Cube (Silver) |
| `cube/model/cubes/cube_daily_metrics_snapshot.js` | 每日指標快照 Cube (Gold) |
| `cube/model/cubes/cube_daily_biz_event_snapshot.js` | 每日業務事件快照 Cube (Gold) |
| `cube/model/views/view_historical_trends.js` | 歷史趨勢 View |
| `cube/model/cubes/cube_vteam_region_plant_factory_line_tree.js` | VTeam 維度階層樹 |

### Cube.js 查詢方式

1. **Playground**: http://localhost:4003
2. **REST API**: 
```bash
curl "http://localhost:4002/cubejs-api/v1/load" \
  -H "Authorization: REDACTED_SECRET" \
  -G --data-urlencode 'query={"measures":["HistoricalTrends.inProgressTaskCount"]}'
```

### Scripts 工具

| 階段 | 腳本 | 用途 | 使用頻率 |
|------|------|------|----------|
| **Bronze 同步** | `sync/sync_incremental.py` | 增量+全量混合同步 | 日常 |
| | `sync/sync_to_clickhouse.py` | 全量同步（舊版） | 首次/重建 |
| **Silver 管理** | `scripts/check_rmv_status.py` | 檢查 RMV 刷新狀態 | 日常 |
| | `scripts/create_rmv.py` | 建立 RMV | 首次 |
| | `scripts/update_silver_views.py` | 更新 View 定義 | 維護 |
| **指標查詢** | `scripts/query_metrics_rmv.py` | 查詢 17 指標（RMV） | 日常 |
| | `scripts/query_metrics.py` | 查詢 17 指標（View） | 備用 |
| **Gold 快照** | `scripts/create_gold_snapshot.py` | 建立每日快照 | 日常 |
| **驗證比對** | `scripts/compare_with_benchmark.py` | 與 Benchmark 比對 | 驗證 |
| | `scripts/compare_view_rmv.py` | View vs RMV 比對 | 驗證 |
| | `scripts/compare_data_accuracy.py` | 資料準確性比對 | 驗證 |
| **環境檢查** | `scripts/check_my_env.py` | 檢查連線環境 | 除錯 |
| | `scripts/check_benchmark_tables.py` | 檢查 Benchmark 表 | 除錯 |
| | `scripts/check_silver_tables.py` | 檢查 Silver 表 | 除錯 |
| **分析工具** | `scripts/check_mssql_columns.py` | 查詢 MSSQL 欄位結構 | 分析 |
| | `scripts/check_tracking_behavior.py` | 驗證追蹤欄位行為 | 分析 |

> 歸檔腳本位於 `scripts/archive/`

---

## SQL 執行順序

1. `sql/01_create_database.sql`
2. `sql/02_create_bpm_tables.sql`
3. `sql/03_create_common_tables.sql`
4. `sql/04_create_silver_database.sql`
5. `sql/05_create_silver_views.sql`
6. `sql/06_create_silver_rmv.sql`
7. `sql/07_create_gold_snapshot.sql`

---

## TASK_STATUS 判斷邏輯

```sql
multiIf(
    DELETE_REASON_ IS NOT NULL, 'CANCELLED',
    ASSIGNEE_ IS NULL AND END_TIME_ IS NULL, 'TODO',
    ASSIGNEE_ IS NOT NULL AND END_TIME_ IS NULL, 'DOING',
    ASSIGNEE_ IS NOT NULL AND CLAIM_TIME_ IS NULL AND END_TIME_ IS NOT NULL, 'DONE_AUTO',
    END_TIME_ IS NOT NULL, 'DONE',
    'TODO'
)
```

---

## ClickHouse 注意事項

- 不支援 `CREATE OR REPLACE VIEW`，需用 `DROP VIEW IF EXISTS` + `CREATE VIEW`
- 不允許一次執行多個語句，需分開執行
- 不支援中文別名
- RMV 需啟用 `allow_experimental_refreshable_materialized_view = 1`
- RMV 需設定 `allow_nullable_key = 1`
