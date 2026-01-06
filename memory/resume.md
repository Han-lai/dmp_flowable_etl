# 專案回顧 (下次對話請先讀這個)

**最後更新**: 2026-01-02

---

## 專案概述

**DMP Flowable 資料同步專案** - 將 MSSQL 的 Flowable BPM 資料同步到 ClickHouse，建立 Bronze/Silver 層資料倉儲。

---

## 目前進度 ✅

| 階段 | 狀態 | 完成日期 |
|------|------|----------|
| Bronze 層同步 | ✅ 完成 | 2024-12-18 |
| Silver View 建立 | ✅ 完成 | 2024-12-23 |
| Silver RMV 建立 | ✅ 完成 | 2024-12-24 |
| 17 指標驗證 | ✅ 完成 | 2024-12-24 |
| 邏輯等價性驗證 | ✅ 完成 | 2024-12-24 |
| Scripts 整理 | ✅ 完成 | 2024-12-24 |
| **Bronze 增量同步** | ✅ 完成 | 2026-01-02 |
| **指標業務定義文件** | ✅ 完成 | 2026-01-02 |

---

## 架構

```
MSSQL → Bronze (16 張表) → Silver (5 View + 5 RMV) → Metric 查詢
         ↑
    增量同步 (5 張大表)
    全量同步 (11 張小表)
```

**增量同步表 (5 張):**
| 表名 | 追蹤欄位 | 資料量 |
|------|----------|--------|
| ACT_HI_PROCINST | START_TIME_ | 17K |
| ACT_HI_TASKINST | LAST_UPDATED_TIME_ | 50K |
| ACT_HI_IDENTITYLINK | CREATE_TIME_ | 598K |
| ACT_HI_VARINST | LAST_UPDATED_TIME_ | 660K |
| FlowableTaskStats | LastUpdatedTime | 1.3M |

---

## 暫緩項目 ⏸️

| 項目 | 原因 |
|------|------|
| 逾期在途業務事件數 | 缺少 HealthSettings 表 |
| 自動化比對 | 目前手動執行腳本 |

---

## 日常操作流程

```
Step 1: 同步 Bronze（增量）
python sync/sync_incremental.py all
        │
        ▼
Step 2: 檢查 RMV 刷新狀態（可選）
python scripts/check_rmv_status.py
        │
        ▼
Step 3: 查詢指標
python scripts/query_metrics_rmv.py
```

---

## 快速上手檔案

| 檔案 | 用途 |
|------|------|
| `CLAUDE.md` | 專案快速上手指南 |
| `docs/data_flow_guide.md` | 資料流程 (Bronze→Silver→Metric) |
| `docs/metric_definitions.md` | 17 個指標業務定義文件 |
| `docs/metric_query_summary.md` | 17 個指標查詢 SQL |
| `memory/project_context.md` | 完整專案進度 |
| `memory/decisions_log.md` | 技術決策紀錄 |

---

## 連線資訊

| 環境 | Host | Port | User |
|------|------|------|------|
| 我的環境 | 10.136.218.207 | 8121 | default |
| Benchmark | 10.136.218.207 | 8124 | ch_user |

---

## 常用指令

```bash
# 日常同步（增量 + 全量混合）
python sync/sync_incremental.py all

# 查詢指標 (RMV，效能較好)
python scripts/query_metrics_rmv.py

# 檢查 RMV 刷新狀態
python scripts/check_rmv_status.py

# View vs RMV 比對
python scripts/compare_view_rmv.py
```
