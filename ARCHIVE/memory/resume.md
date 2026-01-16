# 專案回顧 (下次對話請先讀這個)

**最後更新**: 2026-01-13

---

## 專案概述

**DMP Flowable 資料同步專案** - 將 MSSQL 的 Flowable BPM 資料同步到 ClickHouse，建立 Bronze/Silver/Gold 層資料倉儲，並透過 Cube.js 提供 API。

**專案狀態**: 🎉 **已完成**

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
| Bronze 增量同步 | ✅ 完成 | 2026-01-02 |
| 指標業務定義文件 | ✅ 完成 | 2026-01-02 |
| Cube.js 語意層 | ✅ 完成 | 2026-01-12 |
| Physical Gold 快照層 | ✅ 完成 | 2026-01-12 |
| **技術驗證 (IMV JOIN)** | ✅ 完成 | 2026-01-13 |
| **專案總結報告** | ✅ 完成 | 2026-01-13 |

---

## 架構

```
MSSQL ──► Bronze (16 表) ──► Silver (4 RMV) ──► Cube.js ──► 前端
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

## 資料流執行順序

| 順序 | 層級 | 執行時間 | 觸發方式 | 執行指令 |
|------|------|----------|----------|----------|
| 1 | **Bronze 同步** | 依需求（建議每日 09:00 前） | 手動 | `python sync/sync_incremental.py all` |
| 2 | **Silver RMV 刷新** | 每日 02:00 UTC (10:00 Asia/Taipei) | 自動 | ClickHouse 自動執行 |
| 3 | **Gold 快照** | 每日 10:00 Asia/Taipei 後 | 手動 | `python scripts/create_gold_snapshot.py` |

**建議執行時間線：**
```
09:00  執行 Bronze 同步
10:00  RMV 自動刷新完成（02:00 UTC）
10:30  執行 Gold 快照
       ↓
       Cube.js API 可查詢最新資料
```

---

## 暫緩項目 ⏸️

| 項目 | 原因 |
|------|------|
| 逾期在途業務事件數 | 缺少 HealthSettings 表 |
| 自動排程 | MVP 階段，手動執行足夠 |

---

## 日常操作流程

```
Step 1: 同步 Bronze（增量）
python sync/sync_incremental.py all
        │
        ▼
Step 2: 等待 RMV 刷新（或手動檢查）
python scripts/check_rmv_status.py
        │
        ▼
Step 3: 執行 Gold 快照
python scripts/create_gold_snapshot.py
        │
        ▼
Step 4: 查詢指標（可選）
python scripts/query_metrics_rmv.py
```

---

## 快速上手檔案

| 檔案 | 用途 |
|------|------|
| `CLAUDE.md` | 專案快速上手指南 |
| `docs/project_summary_report.md` | 主管報告文件 |
| `docs/project_technical_report.md` | 完整專案技術報告 |
| `docs/data_flow_guide.md` | 資料流程 (Bronze→Silver→Metric) |
| `docs/metric_definitions.md` | 17 個指標業務定義文件 |
| `docs/semantic_gold_governance.md` | 指標治理文件 |
| `docs/current_architecture_paths.md` | 架構路徑盤點 |
| `memory/project_context.md` | 完整專案進度 |
| `memory/decisions_log.md` | 技術決策紀錄 |
| `scripts/test_imv_join_behavior.py` | ClickHouse 原生增量 MView JOIN 行為測試 |

---

## 連線資訊

| 服務 | Host | Port | User |
|------|------|------|------|
| ClickHouse | REDACTED_IP | 8121 | default |
| Cube.js API | localhost | 4002 | - |
| Cube.js Playground | localhost | 4003 | - |
| MSSQL | 10.136.158.140 | 1433 | - |

---

## Gold 指標清單 (7 個)

| 指標 | Cube | 定義 |
|------|------|------|
| `inProgressTaskCount` | ProcTaskNode | 在途任務數 |
| `autoCompleteRate` | ProcTaskNode | 自動完成率 |
| `avgWorkDuration` | ProcTaskNode | 平均任務處理時長 |
| `inProgressCount` | ProcInstNode | 在途流程數 |
| `completedCount` | ProcInstNode | 已完成流程數 |
| `inProgressEventCount` | BizEventInfo | 在途業務事件數 |
| `avgTotalDuration` | BizEventInfo | 平均業務事件總歷時 |

---

## 常用指令

```bash
# 日常同步（增量 + 全量混合）
python sync/sync_incremental.py all

# 執行 Gold 快照
python scripts/create_gold_snapshot.py

# 查詢指標 (RMV，效能較好)
python scripts/query_metrics_rmv.py

# 檢查 RMV 刷新狀態
python scripts/check_rmv_status.py

# 檢查 RMV 刷新狀態 (SQL)
SELECT view, status, last_refresh_time, next_refresh_time 
FROM system.view_refreshes WHERE database = 'silver';
```
