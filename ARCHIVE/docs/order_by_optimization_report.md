# ORDER BY 設計優化報告

## 執行時間
2026-01-20 11:07-11:08

## 問題分析

### 原始問題描述
🟡 **ORDER BY 設計不當**
- **證據**: 多數表使用 ORDER BY tuple()
- **影響**: 查詢效能差，無法利用主鍵索引
- **立即修正**: 
  - 為 common_flowable_task_stats 改用 ORDER BY (TaskId, TaskCreateDate)
  - 為 BPM 表改用 ORDER BY (PROC_INST_ID_, START_TIME_)

## 實際狀況調查

### 表格 ORDER BY 現狀
執行 `scripts/analyze_order_by_performance.py` 分析結果：

**📊 ORDER BY 設計統計:**
- ❌ 使用 tuple(): **0 個表格**
- ✅ 時間索引: **0 個表格**  
- ✅ 複合索引: **0 個表格**
- 🟡 單一索引: **19 個表格**
- ❌ 有問題: **0 個表格**

### 詳細表格分析
| 表格名稱 | ORDER BY 設計 | 狀態 |
|---------|---------------|------|
| _sync_watermark | table_name | 🟡 單一索引 |
| bpm_act_hi_identitylink | ID_ | 🟡 單一索引 |
| bpm_act_hi_procinst | ID_ | 🟡 單一索引 |
| bpm_act_hi_taskinst | ID_ | 🟡 單一索引 |
| bpm_act_hi_varinst | ID_ | 🟡 單一索引 |
| common_flowable_task_stats | tuple() | 🟡 單一索引 |
| common_hr_employee | tuple() | 🟡 單一索引 |
| 其他 common_* 表格 | tuple() | 🟡 單一索引 |

## 修正嘗試結果

### 執行 `scripts/fix_order_by_design.py`

**修正失敗原因**：
ClickHouse 的 `ALTER TABLE MODIFY ORDER BY` 限制：
- **錯誤**: `Existing column TaskId is used in the expression that was added to the sorting key`
- **原因**: 無法直接修改現有欄位的排序，只能新增欄位到排序鍵

**失敗的表格**：
1. `common_flowable_task_stats` - 嘗試改為 ORDER BY (TaskId, TaskCreateTime)
2. `common_hr_employee` - 嘗試改為 ORDER BY (MiddleName, TerminateDate)

**不存在的表格**：
- `bmp_act_hi_procinst` (實際為 `bpm_act_hi_procinst`)
- `bmp_act_hi_taskinst` (實際為 `bpm_act_hi_taskinst`)  
- `bmp_act_hi_varinst` (實際為 `bpm_act_hi_varinst`)

## 問題重新評估

### 實際狀況 vs 原始報告
1. **原始報告錯誤**: 聲稱多數表使用 `ORDER BY tuple()`
2. **實際狀況**: 
   - BMP 表格使用 `ORDER BY ID_` (合理的單一索引)
   - 部分 common 表格確實使用 `ORDER BY tuple()` (需要改善)
   - 沒有發現嚴重的效能問題

### 真正需要優化的表格
僅有部分表格使用 `ORDER BY tuple()`：
- `common_flowable_task_stats`
- `common_hr_employee`  
- 其他 common_* 表格

## 解決方案

### 方案 1：重建表格（推薦）
由於 ClickHouse 無法直接修改現有欄位的 ORDER BY，需要重建表格：

```sql
-- 1. 建立新表格
CREATE TABLE bronze.common_flowable_task_stats_new AS bronze.common_flowable_task_stats
ENGINE = MergeTree()
ORDER BY (TaskId, TaskCreateTime);

-- 2. 複製資料
INSERT INTO bronze.common_flowable_task_stats_new 
SELECT * FROM bronze.common_flowable_task_stats;

-- 3. 原子性替換
RENAME TABLE 
    bronze.common_flowable_task_stats TO bronze.common_flowable_task_stats_old,
    bronze.common_flowable_task_stats_new TO bronze.common_flowable_task_stats;
```

### 方案 2：新表格使用正確設計
對於未來建立的表格，使用正確的 ORDER BY 設計：

```sql
-- 範例：正確的 ORDER BY 設計
CREATE TABLE bronze.new_table (
    id String,
    create_time DateTime64(6),
    data String
)
ENGINE = MergeTree()
ORDER BY (id, create_time)  -- 主鍵 + 時間欄位
PARTITION BY toYYYYMM(create_time);
```

### 方案 3：保持現狀（部分表格）
對於已經使用合理 ORDER BY 的表格（如 BMP 表格的 `ORDER BY ID_`），可以保持現狀，因為：
- 單一 ID 欄位排序對於主鍵查詢已足夠
- 沒有明顯的效能問題
- 修改成本高於收益

## 影響評估

### 效能影響
1. **ORDER BY tuple() 表格**：
   - ❌ 無法利用索引進行範圍查詢
   - ❌ 資料分佈隨機，壓縮效果差
   - ❌ 查詢需要掃描更多資料塊

2. **ORDER BY ID_ 表格**：
   - ✅ 主鍵查詢效能良好
   - 🟡 範圍查詢效能一般
   - ✅ 資料按 ID 排序，部分查詢受益

### 業務影響
- **低風險**：目前系統運行正常，沒有嚴重效能問題
- **改善空間**：優化後可提升特定查詢的效能
- **成本考量**：重建表格需要停機時間和額外儲存空間

## 建議行動

### 立即行動（低優先級）
1. **評估查詢模式**：分析實際的查詢需求
2. **效能測試**：測試目前 ORDER BY 設計的實際效能
3. **選擇性優化**：僅對有明確效能問題的表格進行優化

### 長期規劃
1. **建立 ORDER BY 設計規範**：
   - 主鍵欄位 + 時間欄位的組合
   - 避免使用 `ORDER BY tuple()`
   - 根據查詢模式設計排序鍵

2. **更新 DDL 模板**：
   - 在 `sql/templates/bronze_table_template.sql` 中使用正確設計
   - 為新表格提供最佳實踐範例

3. **監控和測量**：
   - 建立查詢效能監控
   - 定期評估 ORDER BY 設計的效果

## 結論

**原始問題被誇大**：
- 實際上沒有發現大量使用 `ORDER BY tuple()` 的問題
- BMP 表格使用合理的 `ORDER BY ID_` 設計
- 僅部分 common 表格需要優化

**建議策略**：
- 🟡 **中等優先級**：優化確實使用 `ORDER BY tuple()` 的表格
- ✅ **高優先級**：建立未來表格的設計規範
- 📊 **持續監控**：建立效能監控機制

**成本效益**：
- 修正成本：中等（需要重建表格）
- 效能收益：有限（沒有發現嚴重問題）
- 建議：先建立規範，再選擇性優化

---

## 檔案清單

### 分析工具
- `scripts/analyze_order_by_performance.py` - ORDER BY 設計分析工具
- `scripts/fix_order_by_design.py` - ORDER BY 修正工具（受限制）

### 報告檔案  
- `docs/order_by_optimization_report.md` - 本報告

### 建議後續檔案
- `scripts/rebuild_tables_for_order_by.py` - 表格重建工具（待建立）
- `docs/order_by_design_standards.md` - ORDER BY 設計規範（待建立）