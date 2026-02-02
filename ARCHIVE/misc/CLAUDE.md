# CLAUDE.md - 專案快速上手指南

## 專案概述
DMP Flowable 資料同步專案，將 MSSQL 的 Flowable BPM 資料同步到 ClickHouse，建立 Bronze/Silver/Gold 層資料倉儲，並透過 Cube.js 提供 API。

## 目前狀態 (2026-01-30 更新)

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
| **L5 指標驗證** | FlowableTaskStats 與 QAS SQL 對比 | ✅ 完成 |
| **檔案整理** | 專案目錄重整 (Legacy/One-off 歸檔) | ✅ 完成 |

### 暫緩
- ⏸️ 逾期在途業務事件數 (缺 HealthSettings 表)
- ⏸️ 自動化排程 (目前手動執行)
- ⏸️ **VxType 歸屬邏輯修正** (待確認需求)

---

## L5 指標驗證結果 (2026-01-30)

### 驗證對象
- `L5_task_sample.sql` - 從 MSSQL 撈取 L5 任務資料
- `QAS_L5_task.sql` - 同上，使用 `_0108` 備份表
- `metric_definitions.md` - L5 指標業務定義

### 驗證結果

| 項目 | 狀態 | 說明 |
|------|------|------|
| Task Status 判定 | ✅ 一致 | TODO/DOING/DONE 邏輯正確 |
| TaskBypass 標記 | ✅ 一致 | autoComplete=1 → Y |
| 五階維度欄位 | ✅ 可用 | Plant/Factory/Line 都有 |
| **VxType 歸屬邏輯** | ✅ 已實作 | Silver 層 `mv_fact_task_vx` 已實作 315% → V1 規則 |
| **Region 維度** | ✅ 已實作 | 透過 MDM 主檔 `mv_dim_mfg_five_level` 補齊 |

### 數據比對 (2025-12-25, WJ2, NBU, E5)

| 資料來源 | Total | TODO | DOING | DONE | 說明 |
|---------|------:|-----:|------:|-----:|------|
| **QAS SQL (MSSQL)** | 198 | 0 | 0 | 198 | 原始資料 (含 bypass) |
| **Gold 層 (ClickHouse)** | 180 | 0 | 0 | 180 | 排除 bypass + 時間邏輯差異 |

### 差異原因

1. **時間篩選邏輯不同**
   - QAS: `START_TIME OR CLAIM_TIME OR END_TIME` 任一符合
   - Gold: 只看 `task_start_date` (任務建立日期)

2. **TaskBypass 排除**
   - QAS 原始結果包含 bypass 任務 (約 5 筆)
   - Gold 層已排除 bypass 任務

### 相關檔案
- [flowable_task_stats_mapping.md](docs/flowable_task_stats_mapping.md) - 欄位對應文件
- [query_gold_l5.py](scripts/validation/query_gold_l5.py) - Gold 層查詢腳本
- [query_gold_l5.py](scripts/validation/query_gold_l5.py) - Gold 層查詢腳本
- [test_time_filter.py](scripts/validation/test_time_filter.py) - 時間篩選測試腳本

### E4 異常數據調查結果 (2026-02-02)

**問題**: QAS 查 E4 只有 5 筆，但 ClickHouse Gold 顯示 155 筆。

**根本原因 (Root Cause)**:
- ClickHouse 正確同步了 UAT Source 的新表 (`ACT_HI_TASKINST_0108`)
- QAS 的 View (`FlowableTaskStats`) 仍指向舊的/空的表 (`ACT_HI_TASKINST`)

**證據**:
- Source (`_0108`) 與 ClickHouse Bronze 筆數完全一致 (147萬筆)。
- 在 ClickHouse 上模擬 QAS 邏輯，算出 E4=163, E5=196 (與 User 預期相符)。
- **結論**: ClickHouse 數據是正確的，QAS View 需修正。

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
| 2.5 | **Silver 通用指標轉換** | Bronze 同步後 | 手動 | `python scripts/transform_silver_generic_metrics.py` |
| 3 | **Gold 快照** | 每日 10:00 Asia/Taipei 後 | 手動 | `python scripts/create_gold_snapshot.py` |

### 建議執行時間線

```
09:00  執行 Bronze 同步
09:30  執行 Silver 通用指標轉換
10:00  RMV 自動刷新完成（02:00 UTC）
10:30  執行 Gold 快照（含 L5 + 人員使用率）
       ↓
       Cube.js API 可查詢最新資料
```

### 操作步驟

```
Step 1: 同步 Bronze（增量）
python sync/sync_incremental.py all
        │
        ▼
Step 1.5: 轉換 Silver 通用指標
python scripts/transform_silver_generic_metrics.py
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
- Host: 10.136.218.207:8121
- User: default / default

### ClickHouse (參考環境)
- Host: 10.136.218.207:8124
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
  -H "Authorization: dmp_flowable_cube_secret_key_2026" \
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

## L5 任務執行完成率 - 邏輯概念 (2026-01-16 更新)

### 資料來源與關聯

```
bronze.common_flowable_task_stats (主表)
    │
    ├── TaskDefinitionKey → 判斷 Vx 歸屬 (前兩字元)
    ├── TaskStatus → 任務狀態 (todo/Doing/Done)
    ├── TaskBypass → 是否 bypass (需 = 'N')
    ├── Plant / Factory / Line → 篩選維度
    └── ProcessInstanceId
            │
            ├──────────────────────────────────────┐
            ▼                                      ▼
bronze.bpm_act_hi_procinst (關聯表)    bronze.bpm_act_hi_varinst (轉置取得 moNumber)
    ├── PROC_INST_ID_ = ProcessInstanceId    ├── PROC_INST_ID_ = ProcessInstanceId
    └── BUSINESS_KEY_ → 判斷 NPE             └── moNumber → 判斷 V1 特殊規則 + Q/R 工單
```

### ⚠️ 重要變更 (2026-01-16)

**工單編號判斷改用 `varinst.moNumber`**（取代原本的 `FlowableTaskStats.MoNumber` 和 `procinst.NAME_`）

**原因：**
- `procinst.NAME_` 是流程名稱（如 `V32025111700005`），不是工單編號
- `varinst.moNumber` 是實際工單編號（如 `199170900339`）
- 使用 `varinst.moNumber` 可找到更多符合 V1 規則的任務（多 5,368 個流程）

### 篩選條件（基礎過濾）

| 條件 | 欄位 | 規則 |
|------|------|------|
| 排除 bypass | `TaskBypass` | = 'N' |
| 排除 E 開頭任務 | `TaskDefinitionKey` | NOT LIKE 'E%' |
| 排除 C 開頭任務 | `TaskDefinitionKey` | NOT LIKE 'C%' |
| 排除 Q 工單 | `varinst.moNumber` | NOT LIKE 'Q%' |
| 排除 R 工單 | `varinst.moNumber` | NOT LIKE 'R%' |

### Vx 歸屬判斷邏輯

```
IF varinst.moNumber 包含 196/199/200/210/212/213/315
    THEN → 歸類為 V1（不論 TaskDefinitionKey 是 V1 或 V3）
         ├── BUSINESS_KEY_ LIKE '%NPE%' → V1 NPE
         └── BUSINESS_KEY_ NOT LIKE '%NPE%' → V1 MFG
ELSE
    → 依 TaskDefinitionKey 前兩字元判斷 (V1/V2/V3/...)
```

### 任務狀態項目計算

| Item | Task Qty 計算 | (%) 計算 |
|------|--------------|----------|
| Total Task | todo + Doing + Done | - |
| Todo | TaskStatus = 'todo' | Todo / Total Task |
| Doing | TaskStatus = 'Doing' | Doing / Total Task |
| Done | TaskStatus = 'Done' | Done / Total Task |
| Doing + Done | Doing + Done | (Doing + Done) / Total Task |
| Todo + Doing (Acc) | 累計在途（依時間區間） | - |

### 時間區間計算

| 區間 | 計算方式 |
|------|---------|
| Total | 該月所有資料 |
| Month (MMM) | 同 Total |
| W${x} | 當前週（ISO Week，週一至週日） |
| W(${x}-1) | 前一週 |
| W(${x}-2) | 前兩週 |
| Dn-1 ~ Dn-7 | 最近 7 天每日資料 |

**週次計算：** `toISOWeek(date)` (ISO 8601 標準)

### 輸出維度

| 維度 | 說明 |
|------|------|
| Vx | V1 All / V1 NPE / V1 MFG / V2 / V3 / ... |
| Plant | 產品線 |
| Factory | 工廠 |
| Line | 線別 |

### 執行流程

```
1. 讀取 common_flowable_task_stats
       │
       ▼
2. 基礎篩選
   - TaskBypass = 'N'
   - TaskDefinitionKey NOT LIKE 'E%' / 'C%'
       │
       ▼
3. JOIN bpm_act_hi_procinst
   - 取得 BUSINESS_KEY_, NAME_
   - 排除 Q/R 工單
       │
       ▼
4. Vx 歸屬判斷
   - MoNumber 196/199/200/210/212/213/315 → V1
   - 其他 → TaskDefinitionKey 前兩字元
   - V1 再分 NPE / MFG
       │
       ▼
5. 按維度 + 時間區間分組
   - GROUP BY Vx, Plant, Factory, Line, 時間區間
       │
       ▼
6. 計算各狀態任務數 + 百分比
   - Total Task / Todo / Doing / Done / Doing+Done
   - Todo+Doing (Acc) 累計
```

---

## 通用指標 Silver/Gold 層

### Silver 層表（2 張）

| 表 | 用途 | 來源 |
|-----|------|------|
| `silver.FACT_TASK_VX_ATTRIBUTION` | 任務 Vx 歸屬事實表 | common_flowable_task_stats + bpm_act_hi_procinst |
| `silver.DIM_CONFIG_USER` | Config Users 維度表 | emp_node_role_mapping + emp_org_info_mapping + emp_user_group_mapping + user_group |

### Gold 層表（2 張）

| 表 | 用途 | 時間區間 |
|-----|------|---------|
| `gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT` | L5 任務執行完成率快照 | month/week/day |
| `gold.DAILY_USER_UTILIZATION_SNAPSHOT` | 人員使用率快照 | month/week/day |

### 執行順序

```bash
# 1. 建立 Silver 層表結構
clickhouse-client < sql/08_create_silver_generic_metrics.sql

# 2. 建立 Gold 層表結構
clickhouse-client < sql/09_create_gold_generic_metrics.sql

# 3. 轉換 Silver 層資料
python scripts/transform_silver_generic_metrics.py

# 4. 建立 Gold 層快照（整合在 create_gold_snapshot.py）
python scripts/create_gold_snapshot.py --date 2025-12-28
```

### 狀態計算邏輯

使用 `FlowableTaskStats.TaskStatus` 欄位直接計算：
- `TODO`：TaskStatus = 'TODO'
- `DOING`：TaskStatus = 'DOING'  
- `DONE`：TaskStatus = 'DONE'

### 與外部系統差異

| 項目 | 本地系統 | 外部系統 |
|------|---------|---------|
| 狀態來源 | `TaskStatus` 欄位 | 依時間欄位計算 `state_on_date` |
| Bypass 處理 | 排除 (`is_excluded=1`) | 不排除 |
| 2025-12-28 結果 | 3,410 筆 (全 DONE) | 5,209 筆 |

**差異原因**：
1. 本地排除 1,799 筆 Bypass 任務
2. 外部系統使用「當天狀態」計算，本地使用「最終狀態」

---

## ClickHouse 注意事項

- 不支援 `CREATE OR REPLACE VIEW`，需用 `DROP VIEW IF EXISTS` + `CREATE VIEW`
- 不允許一次執行多個語句，需分開執行
- 不支援中文別名
- RMV 需啟用 `allow_experimental_refreshable_materialized_view = 1`
- RMV 需設定 `allow_nullable_key = 1`
