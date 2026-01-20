# CLAUDE.md - 專案快速上手指南

## 專案概述

DMP Flowable 資料同步專案，將 MSSQL 的 Flowable BPM 資料同步到 ClickHouse，建立 Bronze/Silver/Gold 層資料倉儲。

## 目前狀態 (2026-01-19)

### ✅ 已完成

| 項目 | 說明 | 驗證狀態 |
|------|------|----------|
| Bronze 層 | 18 張表從 MSSQL 同步至 ClickHouse | ✅ 100% 驗證通過 |
| Silver 層 | `FACT_TASK_VX_ATTRIBUTION` L5 任務事實表 | ✅ 基礎邏輯驗證通過 |
| Gold 層 | `DAILY_L5_TASK_COMPLETION_SNAPSHOT` L5 指標快照 | ⚠️ 架構完成，業務邏輯待驗證 |
| L5 指標實作 | 完整的 L5 任務執行完成率指標 | ⚠️ 85% 符合業務需求 |
| 對帳驗證 | 多組隨機條件 MSSQL vs ClickHouse | ✅ 100% 通過 |

### ⚠️ 待改善

| 項目 | 符合度 | 說明 |
|------|--------|------|
| 任務狀態計算 | 70% | 需確認是否按業務規則重新計算 |
| 累計在途邏輯 | 50% | Todo + Doing (Acc) 需重新設計 |
| L5 業務規則驗證 | 0% | Vx 歸屬、排除邏輯尚未驗證 |
| Gold 層聚合驗證 | 0% | 時間區間、百分比計算尚未驗證 |

### 📊 驗證覆蓋度

| 層級 | 覆蓋度 | 狀態 |
|------|--------|------|
| Bronze 層同步 | 100% | ✅ 完成 |
| Silver 層轉換 | 70% | ⚠️ 部分完成 |
| Gold 層聚合 | 0% | ❌ 未開始 |
| L5 業務規則 | 0% | ❌ 未開始 |
| 端到端流程 | 30% | ⚠️ 部分 |

---

## 架構概覽

```
MSSQL (APP_SRV_BPM/COMMON)
    │
    ▼ JDBC Bridge
ClickHouse bronze.*        ← 18 張原始表
    │
    ▼ Python ETL
ClickHouse silver.*        ← task_detail_wide 寬表
    │
    ▼ Snapshot
ClickHouse gold.*          ← 可查詢的指標快照
```

---

## 專案結構

```
├── sync/                   # Bronze 同步
│   ├── sync_to_clickhouse.py
│   └── sync_incremental.py
│
├── sql/                    # DDL（按順序執行）
│   ├── 01_create_database.sql
│   ├── 02_create_bpm_tables.sql
│   ├── ...
│   └── 10_create_silver_task_detail.sql
│
├── scripts/                # ETL & 驗證
│   ├── transform_silver_task_detail.py    # Silver ETL
│   ├── create_gold_snapshot.py            # Gold 快照
│   ├── verify_clickhouse_vs_mssql.py      # 對帳驗證
│   └── verify_reference_sql.py            # Reference SQL 驗證
│
├── docs/                   # 核心文件
│   ├── clickhouse_data_model_design.md    # 完整設計文件
│   ├── metric_definitions.md              # L5 指標業務定義
│   └── data_flow_guide.md                 # 資料流說明
│
├── docker/                 # 基礎設施
│   ├── docker-compose.yml
│   ├── clickhouse/
│   └── jdbc-bridge/
│
├── cube/                   # Cube.js 語意層（選用）
│
└── ARCHIVE/                # 歷史檔案（開發過程產物）
```

---

## 快速開始

```powershell
# 1. 啟動 ClickHouse + JDBC Bridge
cd docker
docker-compose up -d

# 2. 同步 Bronze 層
python sync/sync_to_clickhouse.py

# 3. 建立 Silver 層
python scripts/transform_silver_task_detail.py

# 4. 驗證結果
python scripts/verify_clickhouse_vs_mssql.py
```

---

## 關鍵設計決策

| 決策 | 說明 |
|------|------|
| `taskBypass` 來源 | Task 層級變數 `autoComplete`，JOIN Key 是 `TASK_ID_` |
| 流程變數 JOIN | `plant/factory/line` 來自 `ACT_HI_VARINST`，JOIN Key 是 `PROC_INST_ID_` |
| 工單編號判斷 | 使用 `LIKE '196%'`（開頭），不是 `LIKE '%196%'`（包含） |

---

## 連線資訊

| 環境 | Host | Port | 帳號 |
|------|------|------|------|
| MSSQL | twtpesqldv2.delta.corp | 1433 | DMP_APP_SRV |
| ClickHouse | REDACTED_IP | 8121 | default |

---

## 核心文件

| 檔案 | 用途 |
|------|------|
| `docs/data_flow_guide.md` | 資料流程指南（Bronze → Silver → Gold） |
| `docs/clickhouse_data_model_design.md` | 完整設計文件 |
| `docs/metric_definitions.md` | L5 指標業務定義 |

---

## TASK_STATUS 判斷邏輯

```sql
CASE
    WHEN END_TIME_ IS NOT NULL THEN 'DONE'
    WHEN ASSIGNEE_ IS NOT NULL THEN 'DOING'
    ELSE 'TODO'
END
```

## TASK_BYPASS 判斷邏輯

```sql
-- JOIN Key 是 TASK_ID_（不是 PROC_INST_ID_）
CASE WHEN varinst.LONG_ = 1 THEN 'Y' ELSE 'N' END
-- 變數名稱: autoComplete
```

---

**Last Updated**: 2026-01-19

---

## 最新進度記錄

### TASK 7: L5 指標與業務需求規格對比驗證 (2026-01-19)

**完成項目**：
- ✅ L5 指標實作與業務需求規格完整對比分析
- ✅ 驗證狀況分析：Bronze/Silver 層基礎資料 100% 驗證通過
- ✅ 符合度評估：整體 85% 符合業務需求

**主要發現**：
- ✅ Vx 歸屬規則、排除邏輯、資料來源變更：100% 符合
- ⚠️ 任務狀態計算、累計在途邏輯：需要改善
- ❌ L5 業務規則驗證、Gold 層聚合驗證：尚未開始

**下一步**：
1. 建立 L5 業務規則驗證腳本
2. 實作累計在途任務數邏輯
3. 建立 Gold 層聚合邏輯驗證
4. 加入 "total" 時間區間類型

**相關檔案**：
- `docs/metric_definitions.md` - 業務需求規格
- `scripts/verify_*.py` - 已完成的驗證腳本
- `scripts/transform_silver_generic_metrics.py` - Silver 轉換邏輯
- `scripts/create_gold_generic_metrics_snapshot.py` - Gold 聚合邏輯
