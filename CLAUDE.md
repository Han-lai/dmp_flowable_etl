# CLAUDE.md - 專案快速上手指南

## 專案概述

DMP Flowable 資料同步專案，將 MSSQL 的 Flowable BPM 資料同步到 ClickHouse，建立 Bronze/Silver/Gold 層資料倉儲。

## 目前狀態 (2026-01-16)

### ✅ 已完成

| 項目 | 說明 |
|------|------|
| Bronze 層 | 18 張表從 MSSQL 同步至 ClickHouse |
| Silver 層 | `task_detail_wide` 任務明細寬表（等價於 MSSQL Reference SQL） |
| 對帳驗證 | 條件 `date=2025-12-31, plant='WJ2', line='E5', taskBypass='N'` → 12 筆通過 |

### ⏸️ 尚未做

- 其他指標擴充（架構已可複用）

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
| ClickHouse | 10.136.218.207 | 8121 | default |

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

**Last Updated**: 2026-01-16
