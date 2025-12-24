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
Exploration / MVP

## 專案目標
1. 探索真實 MSSQL 資料表結構
2. 建立本機 MSSQL Docker Sandbox 測試環境
3. 將 MSSQL 資料同步到 ClickHouse Bronze 層

## 資料來源

| Database | 用途 | 表數量 |
|----------|------|--------|
| APP_SRV_BPM | Flowable 流程資料 | 5 |
| APP_SRV_COMMON | DMP 人員/組織資料 | 11 |

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
- Host: 10.136.218.207
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
