# CLAUDE.md - 專案快速上手指南

## 專案概述
DMP Flowable 資料同步專案，將 MSSQL 的 Flowable BPM 資料同步到 ClickHouse，建立 Bronze/Silver 層資料倉儲。

## 目前狀態 (2024-12-24)

### 已完成
- ✅ Bronze 層：16 張表同步完成
- ✅ Silver 層：4 張 View + 4 張 RMV 建立完成
- ✅ 17 個指標驗證完成
- ✅ View vs RMV 效能比較完成 (RMV 快 4-10 倍)
- ✅ View vs RMV 資料正確性驗證完成 (9 個指標一致)
- ✅ 邏輯等價性驗證完成 (Benchmark vs View vs RMV)
- ✅ Scripts 目錄整理完成 (18 個正式工具 + 14 個歸檔)

### 暫緩
- ⏸️ 逾期在途業務事件數 (缺 HealthSettings 表)

---

## 目前痛點

### 🔴 資料層面
1. **Benchmark 資料過時** - 最後同步 2025-12-10，無法做即時比對
2. **缺少 HealthSettings 表** - 無法實作逾期判斷邏輯
3. **Bronze 層無增量同步** - 每次全量同步，大表效能問題

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
- [ ] 大表增量同步方案
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
| `memory/project_context.md` | 專案進度 |
| `memory/decisions_log.md` | 決策紀錄 |

### Scripts 工具 (整理後 12 個)

| 類別 | 腳本 | 用途 |
|------|------|------|
| 環境檢查 | `check_my_env.py` | 環境診斷 |
| | `check_benchmark_tables.py` | Benchmark 資料範圍 |
| | `check_rmv_status.py` | RMV 刷新狀態 |
| | `check_silver_tables.py` | Silver 表格列表 |
| | `check_view_rmv_consistency.py` | View vs RMV 一致性 |
| 比對驗證 | `compare_data_accuracy.py` | View vs RMV 正確性 |
| | `compare_view_rmv.py` | View vs RMV 效能 |
| | `compare_with_benchmark.py` | Benchmark 比對 |
| 建置/查詢 | `create_rmv.py` | RMV 建置 |
| | `query_metrics.py` | 指標查詢 (View) |
| | `query_metrics_rmv.py` | 指標查詢 (RMV) |
| | `update_silver_views.py` | View 更新 |

> 歸檔腳本 (20 個) 位於 `scripts/archive/`

---

## SQL 執行順序

1. `sql/01_create_database.sql`
2. `sql/02_create_bpm_tables.sql`
3. `sql/03_create_common_tables.sql`
4. `sql/04_create_silver_database.sql`
5. `sql/05_create_silver_views.sql`
6. `sql/06_create_silver_rmv.sql`

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
