# 專案進度 (2026-01-16 更新)

## 目前狀態

**已完成**：第一個通用指標（Task-based Flow 指標）的完整 Pipeline

| 層級 | 內容 | 狀態 |
|------|------|------|
| Bronze | 18 張表從 MSSQL 同步至 ClickHouse | ✅ |
| Silver | `task_detail_wide` 任務明細寬表 | ✅ |
| 對帳驗證 | Reference Case 通過 | ✅ |
| 專案整理 | 結構重整、文件更新 | ✅ |

**尚未做**：其他指標擴充（架構已可複用）

---

## 驗證結果

**Reference Case**：
- 條件：`date=2025-12-31, plant='WJ2', line='E5', taskBypass='N'`
- 結果：12 筆（TODO=8, DOING=2, DONE=2）
- 狀態：✅ MSSQL 與 ClickHouse 完全一致

---

## 關鍵設計決策

| 決策 | 說明 |
|------|------|
| `taskBypass` 來源 | Task 層級變數 `autoComplete`，JOIN Key 是 `TASK_ID_` |
| 流程變數 JOIN | `plant/factory/line` 來自 `ACT_HI_VARINST`，JOIN Key 是 `PROC_INST_ID_` |
| 工單編號判斷 | 使用 `LIKE '196%'`（開頭），不是 `LIKE '%196%'`（包含） |

---

## 專案結構（整理後）

```
├── sync/                   # Bronze 同步
├── sql/                    # DDL（01-10）
├── scripts/                # ETL & 驗證（6 個核心腳本）
├── docs/                   # 核心文件（3 份）
├── docker/                 # 基礎設施
├── cube/                   # Cube.js（選用）
└── ARCHIVE/                # 歷史檔案
```

---

## 核心檔案清單

**Scripts**：
- `transform_silver_task_detail.py` - Silver ETL
- `create_gold_snapshot.py` - Gold 快照
- `verify_clickhouse_vs_mssql.py` - 對帳驗證
- `verify_reference_sql.py` - Reference SQL 驗證

**Docs**：
- `data_flow_guide.md` - 資料流程指南
- `clickhouse_data_model_design.md` - 完整設計文件
- `metric_definitions.md` - L5 指標業務定義

---

## 連線資訊

| 環境 | Host | Port | 帳號 |
|------|------|------|------|
| MSSQL | twtpesqldv2.delta.corp | 1433 | DMP_APP_SRV |
| ClickHouse | 10.136.218.207 | 8121 | default |
