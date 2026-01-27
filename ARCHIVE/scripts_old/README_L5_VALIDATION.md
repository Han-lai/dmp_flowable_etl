# L5 業務規則驗證腳本使用說明

## 概述

本目錄包含完整的 L5 任務執行完成率指標驗證腳本，用於確保 ClickHouse Silver 層實作與 MSSQL 原始邏輯完全一致。

## 腳本清單

### 1. 主要驗證腳本

| 腳本名稱 | 用途 | 驗證內容 |
|---------|------|----------|
| `verify_l5_business_rules.py` | L5 業務規則驗證 | Vx 歸屬、工單號判斷、排除邏輯 |
| `verify_l5_edge_cases.py` | 邊界案例驗證 | NULL 值、特殊字符、混合條件 |
| `run_l5_validation_suite.py` | 完整驗證套件 | 執行所有驗證腳本並生成報告 |

### 2. 基礎驗證腳本（已存在）

| 腳本名稱 | 用途 | 驗證內容 |
|---------|------|----------|
| `verify_reference_sql.py` | 參考案例驗證 | 12 筆基準資料 |
| `verify_random_conditions.py` | 隨機條件驗證 | 5 組隨機測試 |
| `verify_clickhouse_vs_mssql.py` | 對帳驗證 | ClickHouse vs MSSQL |

## 使用方式

### 快速開始（推薦）

執行完整驗證套件：
```bash
python scripts/run_l5_validation_suite.py
```

這會自動執行所有相關驗證腳本並生成完整報告。

### 單獨執行驗證

#### 1. L5 業務規則驗證
```bash
# 驗證所有業務規則
python scripts/verify_l5_business_rules.py

# 只驗證 Vx 歸屬規則
python scripts/verify_l5_business_rules.py --rule vx

# 只驗證工單號判斷邏輯
python scripts/verify_l5_business_rules.py --rule mo

# 只驗證排除邏輯
python scripts/verify_l5_business_rules.py --rule exclude
```

#### 2. 邊界案例驗證
```bash
python scripts/verify_l5_edge_cases.py
```

## 驗證內容詳解

### L5 業務規則驗證

#### 1. Vx 歸屬規則驗證
- **V1 特殊規則**: 工單號以 196/199/200/210/212/213/315 開頭強制歸類為 V1
- **一般規則**: 使用 TaskDefinitionKey 前兩碼 (V1/V2/V3)
- **V1 子類型**: 
  - V1_NPE: business_key 包含 "NPE"
  - V1_MFG: 其他 V1 任務
- **特殊 V1 規則標記**: is_special_v1_rule 欄位正確性

#### 2. 工單號判斷邏輯驗證
- **varinst.moNumber 使用**: 確認使用 EAV 展開後的 moNumber
- **工單號分布統計**: 各類工單號（196/199/200/210/212/213/315/Q/R）的數量一致性
- **V1 特殊工單號總計**: 所有 V1 特殊規則工單號的總數

#### 3. 排除邏輯驗證
- **TaskBypass 判斷**: bypass = 'Y' 的任務排除
- **TaskDefinitionKey 排除**: 以 'E' 或 'C' 開頭的任務排除
- **工單號排除**: 以 'Q' 或 'R' 開頭的工單排除
- **排除原因分類**: exclude_reason 欄位正確性
- **排除標記**: is_excluded 欄位正確性

### 邊界案例驗證

#### 1. NULL 值處理
- **NULL moNumber**: 沒有工單號的任務處理
- **NULL 值 Vx 歸屬**: 依 TaskDefinitionKey 判斷 Vx 類型
- **統計一致性**: NULL 值情況下的統計正確性

#### 2. 邊界工單號
- **接近但不符合規則**: 195/197/201/211/214/316 開頭的工單號
- **擴展工單號**: 1960/1999 等擴展格式
- **邊界判斷正確性**: 確保只有精確匹配的工單號被歸類為 V1

#### 3. 混合條件
- **多重排除條件**: 同時滿足多個排除條件的任務
- **V1 特殊但被排除**: V1 特殊工單號但因其他原因被排除
- **複雜邏輯驗證**: 確保複雜條件組合的正確處理

#### 4. 特殊字符處理
- **特殊符號**: 包含 -、_、空格的工單號
- **超長工單號**: 長度超過 20 字符的工單號
- **空字串**: 空字串工單號的處理

## 預期結果

### 成功標準
所有驗證腳本應該顯示：
- ✅ 100% 一致性
- ✅ 所有統計數字完全匹配
- ✅ 無任何不一致的記錄

### 失敗處理
如果驗證失敗：
1. 檢查 Silver 層轉換邏輯 (`scripts/transform_silver_generic_metrics.py`)
2. 確認 EAV 展開邏輯正確
3. 驗證業務規則實作
4. 檢查資料同步完整性

## 依賴需求

### Python 套件
```bash
pip install pymssql clickhouse-connect
```

### 資料庫連線
- **MSSQL**: `twtpesqldv2.delta.corp:1433` (DMP_APP_SRV 帳號)
- **ClickHouse**: `10.136.218.207:8121` (default 帳號)

### 資料需求
- Bronze 層資料已同步
- Silver 層 `FACT_TASK_VX_ATTRIBUTION` 表已建立
- 測試資料範圍：2025-12-01 以後的資料

## 故障排除

### 常見問題

#### 1. 連線失敗
```
pymssql.OperationalError: (20002, b'DB-Lib error message 20002')
```
**解決方案**: 檢查網路連線和資料庫權限

#### 2. 表不存在
```
clickhouse_connect.driver.exceptions.DatabaseError: Table doesn't exist
```
**解決方案**: 確認 Silver 層表已建立，執行 `transform_silver_generic_metrics.py`

#### 3. 資料不一致
```
❌ vx_type 歸屬規則：X 筆不一致
```
**解決方案**: 檢查 Silver 轉換邏輯，特別是 Vx 歸屬計算部分

### 除錯模式
在腳本中加入更詳細的日誌：
```python
logging.basicConfig(level=logging.DEBUG)
```

## 效能考量

### 執行時間
- 單個驗證腳本：1-3 分鐘
- 完整驗證套件：5-10 分鐘

### 資料量影響
- 測試資料量：約 10-50 萬筆任務
- 記憶體使用：< 1GB
- 網路傳輸：< 100MB

## 維護說明

### 定期執行
建議在以下情況執行驗證：
- 每次 Silver 層邏輯變更後
- 每週定期驗證
- 生產部署前

### 更新腳本
當業務規則變更時，需要更新：
1. 驗證腳本中的業務邏輯
2. 預期結果標準
3. 測試案例

### 版本控制
- 腳本變更需要版本控制
- 重要變更需要測試驗證
- 保留歷史驗證記錄

---

**最後更新**: 2026-01-19  
**維護者**: DMP Flowable 團隊  
**聯絡方式**: 請參考專案文件  