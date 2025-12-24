# 專案回顧 (下次對話請先讀這個)

**最後更新**: 2024-12-24

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

---

## 架構

```
MSSQL → Bronze (16 張表) → Silver (5 View + 5 RMV) → Metric 查詢
```

**Silver View/RMV:**
- V_PROC_VARIABLES_PIVOTED - 流程變數樞紐化
- V_TASK_VARIABLES_PIVOTED - 任務變數樞紐化
- V_HI_PROC_TASK_NODE - 任務節點層
- V_HI_PROCINST_NODE - 流程實例層
- V_HI_BIZ_EVENT_INFO - 業務事件層

---

## 暫緩項目 ⏸️

| 項目 | 原因 |
|------|------|
| 逾期在途業務事件數 | 缺少 HealthSettings 表 |
| Bronze 增量同步 | 目前資料量可接受全量 |
| 自動化比對 | 目前手動執行腳本 |

---

## 下次可能的 Task

1. **確認 RMV 刷新狀態** - 休息 10 天後檢查 RMV 是否正常刷新
   ```bash
   python scripts/check_rmv_status.py
   ```

2. **重新同步 Bronze** - 如果需要最新資料
   ```bash
   python sync/sync_to_clickhouse.py
   ```

3. **逾期判斷功能** - 如果取得 HealthSettings 表

4. **增量同步** - 如果資料量成長需要優化

---

## 快速上手檔案

| 檔案 | 用途 |
|------|------|
| `CLAUDE.md` | 專案快速上手指南 |
| `docs/data_flow_guide.md` | 資料流程 (Bronze→Silver→Metric) |
| `docs/metric_query_summary.md` | 17 個指標查詢 SQL |
| `memory/project_context.md` | 完整專案進度 |
| `memory/decisions_log.md` | 技術決策紀錄 |

---

## 連線資訊

| 環境 | Host | Port | User |
|------|------|------|------|
| 我的環境 | REDACTED_IP | 8121 | default |
| Benchmark | REDACTED_IP | 8124 | ch_user |

---

## 常用指令

```bash
# 查詢指標 (View)
python scripts/query_metrics.py

# 查詢指標 (RMV，效能較好)
python scripts/query_metrics_rmv.py

# 檢查 RMV 刷新狀態
python scripts/check_rmv_status.py

# View vs RMV 比對
python scripts/compare_view_rmv.py
```
