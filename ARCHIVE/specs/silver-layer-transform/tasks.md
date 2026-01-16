# Implementation Plan (實際執行版)

## 說明

原始 spec 設計採用 fact_* 表 + Python ETL 架構，但實際實作改用 **View + RMV** 架構，更簡潔且符合 ClickHouse 特性。

---

## 實際完成狀態

### Phase 1: Silver Layer 基礎建置 ✅

- [x] 1. 建立 Silver Database
  - [x] 1.1 建立 silver database
  - _完成日期: 2024-12-23_

### Phase 2: Silver View 建立 ✅

- [x] 2. 建立 Silver Views (5 張)
  - [x] 2.1 V_PROC_VARIABLES_PIVOTED - 流程變數樞紐化
    - Grain: PROC_INST_ID
    - 將 varinst EAV 格式轉為寬表
  - [x] 2.2 V_TASK_VARIABLES_PIVOTED - 任務變數樞紐化
    - Grain: TASK_ID
    - 任務層變數 (candidateUser, autoComplete)
  - [x] 2.3 V_HI_PROC_TASK_NODE - 任務節點層
    - Grain: TASK_ID
    - 含 TASK_STATUS, 時長計算, 部門/廠區
  - [x] 2.4 V_HI_PROCINST_NODE - 流程實例層
    - Grain: PROC_INST_ID
    - 含 PROC_STATE, DEPTH
  - [x] 2.5 V_HI_BIZ_EVENT_INFO - 業務事件層
    - Grain: BUSINESS_KEY
    - 聚合統計
  - _完成日期: 2024-12-23_
  - _檔案: sql/05_create_silver_views.sql_

### Phase 3: Silver RMV 建立 ✅

- [x] 3. 建立 Silver RMV (5 張)
  - [x] 3.1 RMV_PROC_VARIABLES_PIVOTED
  - [x] 3.2 RMV_TASK_VARIABLES_PIVOTED
  - [x] 3.3 RMV_HI_PROC_TASK_NODE
  - [x] 3.4 RMV_HI_PROCINST_NODE
  - [x] 3.5 RMV_HI_BIZ_EVENT_INFO
  - _完成日期: 2024-12-24_
  - _檔案: sql/06_create_silver_rmv.sql_
  - _刷新頻率: 每天 02:00_

### Phase 4: 指標驗證 ✅

- [x] 4. 驗證 17 個指標
  - [x] 4.1 業務事件總歷時
  - [x] 4.2 流程執行總時間
  - [x] 4.3 任務處理總時間
  - [x] 4.4 流程總歷時
  - [x] 4.5 任務閒置時長
  - [x] 4.6 個人處理時長
  - [x] 4.7 任務總歷時
  - [x] 4.8 在途業務事件總數
  - [x] 4.9 在途任務總數
  - [x] 4.10 平均業務事件總歷時
  - [x] 4.11 平均任務處理時長
  - [x] 4.12 在途任務數-依部門
  - [x] 4.13 在途任務數-依廠區
  - [x] 4.14 在途任務數-依地區
  - [x] 4.15 在途任務數-依人員
  - [x] 4.16 在途流程健康度快照
  - [x] 4.17 事件自動完成率
  - [ ] 4.18 逾期在途業務事件數 (⏸️ 缺 HealthSettings 表)
  - _完成日期: 2024-12-24_
  - _檔案: docs/metric_query_summary.md_

### Phase 5: 邏輯等價性驗證 ✅

- [x] 5. 與 Benchmark 環境比對
  - [x] 5.1 欄位語意對應分析
  - [x] 5.2 狀態值對應分析
  - [x] 5.3 聚合層級比較
  - [x] 5.4 Join 語意比較
  - _完成日期: 2024-12-24_
  - _檔案: docs/logic_equivalence_audit_report.md_
  - _結論: 三環境邏輯等價_

### Phase 6: View vs RMV 驗證 ✅

- [x] 6. View vs RMV 比較
  - [x] 6.1 效能比較 (RMV 快 4-10 倍)
  - [x] 6.2 資料正確性比較 (9 個指標一致)
  - _完成日期: 2024-12-24_
  - _檔案: scripts/compare_view_rmv.py, scripts/compare_data_accuracy.py_

### Phase 7: 文件整理 ✅

- [x] 7. 文件與工具整理
  - [x] 7.1 建立資料流程指南
    - _檔案: docs/data_flow_guide.md_
  - [x] 7.2 Scripts 目錄整理
    - 保留 12 個正式工具
    - 歸檔 20 個到 scripts/archive/
  - [x] 7.3 更新 Memory Bank
    - _檔案: memory/project_context.md, memory/decisions_log.md_
  - _完成日期: 2024-12-24_

---

## 暫緩項目

| 項目 | 原因 | 狀態 |
|------|------|------|
| 逾期在途業務事件數 | 缺少 HealthSettings 表 | ⏸️ |
| 增量同步 | 目前資料量可接受全量 | ⏸️ |
| 自動化比對 | 目前手動執行腳本 | ⏸️ |

---

## 相關檔案

| 類型 | 檔案 |
|------|------|
| DDL | `sql/05_create_silver_views.sql`, `sql/06_create_silver_rmv.sql` |
| 文件 | `docs/data_flow_guide.md`, `docs/metric_query_summary.md`, `docs/logic_equivalence_audit_report.md` |
| 工具 | `scripts/query_metrics.py`, `scripts/query_metrics_rmv.py`, `scripts/create_rmv.py`, `scripts/update_silver_views.py` |
| 驗證 | `scripts/compare_view_rmv.py`, `scripts/compare_data_accuracy.py`, `scripts/compare_with_benchmark.py` |
