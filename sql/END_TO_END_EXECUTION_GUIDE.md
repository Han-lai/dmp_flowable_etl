# ClickHouse 金銀銅資料層 End-to-End 執行指南

## 概述
本指南提供完整的 ClickHouse 資料倉儲建置流程，包含 Bronze（銅）、Silver（銀）、Gold（金）三層架構。

## 當前狀態分析

### 🚨 已知問題
- **Silver 層日期過濾邏輯不一致**：與 MSSQL 參考查詢結果不符
- **資料膨脹問題**：WJ2/NBU/E5 2025-12-25 應為 5 筆，實際為 188 筆

### 📁 關鍵檔案狀態
- ✅ `sql/12_create_silver_mviews_layer2_fixed.sql` - **修正版本（建議使用）**
- ⚠️ `sql/12_create_silver_mviews_layer2.sql` - 原版本（有日期過濾問題）
- ✅ `sql/13_create_gold_mviews.sql` - Gold 層定義
- ✅ `sql/test_mssql_date_filter_logic.sql` - 驗證查詢

## End-to-End 執行順序

### 階段 1：Bronze 層（銅層）- 原始資料同步
```bash
# 1. 建立資料庫結構
sql/01_create_database.sql

# 2. 建立 BPM 相關表（Flowable 資料）
sql/02_create_bpm_tables.sql

# 3. 建立共用表（HR、MDM 等）
sql/03_create_common_tables.sql
```

### 階段 2：Silver 層（銀層）- 資料轉換與業務邏輯
```bash
# 4. 建立 Silver 資料庫
sql/04_create_silver_database.sql

# 5. 建立 Silver 第一層 MVIEW（基礎轉換）
sql/11_create_silver_mviews_layer1.sql

# 6. 建立 Silver 第二層 MVIEW（業務邏輯）- 使用修正版本
sql/12_create_silver_mviews_layer2_fixed.sql  # ⭐ 修正版本

# 7. 建立製造五階維度
sql/create_silver_dim_mfg_five_level.sql
```

### 階段 3：Gold 層（金層）- 聚合指標
```bash
# 8. 建立 Gold 層 MVIEW（最終指標）
sql/13_create_gold_mviews.sql
```

### 階段 4：驗證與測試
```bash
# 9. 執行驗證查詢
sql/test_mssql_date_filter_logic.sql

# 10. 建立驗證表（可選）
sql/create_validation_table_20260123_143000.sql
```

## 檔案版本說明

### Silver 層第二層選項
| 檔案 | 狀態 | 說明 | 建議 |
|------|------|------|------|
| `12_create_silver_mviews_layer2_fixed.sql` | ✅ 修正版 | 修正日期過濾邏輯 | **推薦使用** |
| `12_create_silver_mviews_layer2.sql` | ⚠️ 原版 | 有日期過濾問題 | 不建議 |
| `12_create_silver_mviews_layer2_mdm_integrated.sql` | 🔄 MDM版 | 整合 MDM 維度 | 特殊需求 |
| `12_create_silver_mviews_layer2_native.sql` | 📦 原生版 | 使用原生 Flowable 表 | 備選方案 |

### 修正檔案
| 檔案 | 用途 | 狀態 |
|------|------|------|
| `fix_silver_date_filter_logic.sql` | 修正日期過濾 | 已整合到 fixed 版本 |
| `fix_silver_time_logic_unified.sql` | 統一時間邏輯 | 歷史修正 |
| `fix_v1_v3_attribution_logic.sql` | 修正 V1/V3 歸屬 | 歷史修正 |

## 執行腳本

### 方式 1：手動執行（推薦）
```bash
# 依序執行各階段 SQL 檔案
clickhouse-client < sql/01_create_database.sql
clickhouse-client < sql/02_create_bpm_tables.sql
# ... 依序執行
```

### 方式 2：使用 Python 腳本
```bash
# 使用現有的執行腳本
python scripts/fix_silver_date_filter_and_test.py
```

### 方式 3：批次執行（需建立）
```bash
# 建立批次執行腳本
sql/00_execute_all_mviews.sql  # 需要更新
```

## 驗證檢查點

### 1. Bronze 層驗證
```sql
-- 檢查 BPM 任務表記錄數
SELECT COUNT(*) FROM bronze.bpm_act_hi_taskinst;

-- 檢查 WJ2/NBU/E5 2025-12-25 Bronze 層記錄
SELECT COUNT(*) FROM bronze.bmp_act_hi_varinst v
JOIN bronze.bpm_act_hi_taskinst t ON v.PROC_INST_ID_ = t.PROC_INST_ID_
WHERE v.NAME_ = 'plant' AND v.TEXT_ = 'WJ2'
AND toDate(t.START_TIME_) = '2025-12-25';
```

### 2. Silver 層驗證
```sql
-- 檢查 Silver MVIEW 記錄數
SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution FINAL;

-- 關鍵驗證：WJ2/NBU/E5 2025-12-25 應為 5 筆
SELECT COUNT(*) FROM silver.mv_fact_task_vx_attribution FINAL
WHERE (
    toDate(task_create_time) = '2025-12-25'
    OR toDate(task_claim_time) = '2025-12-25'
    OR toDate(task_end_time) = '2025-12-25'
)
AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5';
-- 預期結果：5 筆
```

### 3. Gold 層驗證
```sql
-- 檢查 Gold 層聚合
SELECT COUNT(*) FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV FINAL;

-- 檢查特定日期聚合
SELECT * FROM gold.vw_daily_l5_completion_summary
WHERE snapshot_date = '2025-12-25'
AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5';
```

## 故障排除

### 常見問題
1. **日期過濾不一致**
   - 使用 `sql/12_create_silver_mviews_layer2_fixed.sql`
   - 執行 `sql/test_mssql_date_filter_logic.sql` 驗證

2. **資料膨脹問題**
   - 檢查 JOIN 邏輯是否產生笛卡爾積
   - 驗證 `mv_varinst_pivoted` 是否有重複 `PROC_INST_ID_`

3. **MVIEW 更新問題**
   - 使用 `FINAL` 關鍵字查詢
   - 檢查 `_mview_update_time` 時間戳

### 重建流程
```sql
-- 重建 Silver 層
DROP TABLE IF EXISTS silver.mv_fact_task_vx_attribution;
-- 重新執行 sql/12_create_silver_mviews_layer2_fixed.sql

-- 重建 Gold 層
DROP TABLE IF EXISTS gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV;
-- 重新執行 sql/13_create_gold_mviews.sql
```

## 效能監控

### 關鍵指標
- Bronze 層同步延遲
- Silver 層 MVIEW 更新時間
- Gold 層聚合完成時間
- 查詢回應時間

### 監控查詢
```sql
-- 檢查 MVIEW 更新狀態
SELECT 
    table AS mview_name,
    max(_mview_update_time) AS last_update
FROM system.parts 
WHERE database IN ('silver', 'gold')
GROUP BY table;
```

## 總結

**推薦執行順序：**
1. Bronze 層：`01` → `02` → `03`
2. Silver 層：`04` → `11` → `12_fixed` → `create_silver_dim_mfg_five_level`
3. Gold 層：`13`
4. 驗證：`test_mssql_date_filter_logic`

**關鍵成功因素：**
- 使用修正版本的 Silver 層檔案
- 驗證每個階段的資料一致性
- 監控 MVIEW 更新狀態