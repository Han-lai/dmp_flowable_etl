# Silver 層表格清理報告

## 清理概述

**執行時間**: 2026-01-19  
**清理目的**: 移除 Silver 層中不需要的殘留表格，保持系統整潔

## 清理前狀態

- **總表格數**: 41 張
- **殘留表格數**: 31 張
- **需要保留**: 10 張

## 清理結果

### 成功清理的表格類型

| 類型 | 數量 | 釋放空間 | 說明 |
|------|------|----------|------|
| 舊的 View | 5 張 | 0 MB | V_* 系列視圖 |
| 舊的 MVIEW | 5 張 | 9.68 MB | RMV_* 系列 MVIEW |
| MVIEW 內部表格 | 12 張 | 101.45 MB | .inner_id.* 系列內部表格 |
| 舊的事實表 | 4 張 | 50.29 MB | fact_* 系列表格 |
| 舊的維度表 | 1 張 | 6.69 MB | dim_employee |
| 舊的轉置表 | 2 張 | 1.18 MB | varinst_*_pivot 系列 |
| 其他殘留表格 | 2 張 | 3.43 MB | _transform_log, task_detail_wide |

### 清理統計

- **成功刪除**: 31 張表格
- **失敗刪除**: 0 張表格
- **釋放空間**: 172.81 MB
- **清理資料**: 2,650,702 筆

## 清理後狀態

### 保留的表格結構

| 分類 | 表格名稱 | 用途 | 引擎 |
|------|----------|------|------|
| **現有批次表** | `FACT_TASK_VX_ATTRIBUTION` | L5 指標批次處理結果 | ReplacingMergeTree |
| | `DIM_CONFIG_USER` | 用戶配置維度表 | ReplacingMergeTree |
| **MVIEW 第一層** | `mv_varinst_pivoted` | EAV 結構轉置 | MaterializedView |
| | `mv_emp_user_groups` | 員工用戶群組聚合 | MaterializedView |
| | `mv_emp_node_codes` | 員工節點代碼聚合 | MaterializedView |
| | `mv_emp_org_info` | 員工組織資訊整合 | MaterializedView |
| | `mv_task_status_summary` | 任務狀態統計聚合 | MaterializedView |
| **MVIEW 第二層** | `mv_fact_task_vx_attribution` | 任務 Vx 歸屬事實表 | MaterializedView |
| | `mv_dim_config_user` | 用戶配置維度表 | MaterializedView |
| **查詢介面** | `vw_fact_task_vx_attribution_realtime` | 即時查詢視圖 | View |

### 最終統計

- **總表格數**: 10 張
- **結構**: 2 張批次表 + 5 張第一層 MVIEW + 2 張第二層 MVIEW + 1 個查詢視圖
- **系統狀態**: ✅ 整潔，無殘留表格

## 清理效益

1. **空間釋放**: 釋放 172.81 MB 儲存空間
2. **系統整潔**: 移除 31 張不需要的表格
3. **維護簡化**: 只保留必要的表格，降低維護複雜度
4. **效能提升**: 減少不必要的表格掃描和管理開銷

## 系統架構確認

清理後的 Silver 層架構符合設計規範：

```
Bronze 層 → Silver 第一層 MVIEW → Silver 第二層 MVIEW → 查詢介面
```

- **Bronze → Silver**: 透過 MVIEW 自動同步
- **批次系統**: 保持現有 `FACT_TASK_VX_ATTRIBUTION` 和 `DIM_CONFIG_USER`
- **即時系統**: 透過 MVIEW 系統提供即時查詢能力
- **相容性**: 兩套系統並行運行，互不影響

## 建議

1. **定期檢查**: 建議每月執行一次表格檢查，確保無新的殘留表格
2. **監控 MVIEW**: 定期檢查 MVIEW 更新狀態和效能
3. **空間監控**: 持續監控 Silver 層空間使用情況

## 清理腳本

已建立以下腳本供未來使用：

- `scripts/check_clickhouse_tables.py`: 檢查所有表格狀態
- `scripts/cleanup_silver_residual_tables.py`: 清理殘留表格

使用方式：
```bash
# 檢查表格狀態
python scripts/check_clickhouse_tables.py

# 預覽清理（dry-run）
python scripts/cleanup_silver_residual_tables.py --dry-run

# 執行清理
python scripts/cleanup_silver_residual_tables.py
```