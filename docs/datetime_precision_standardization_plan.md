# 時間精度標準化實現計畫

## 目標
將 ClickHouse 時間欄位統一標準化為 DateTime64(6)，解決與 MSSQL DateTime64(7) 的精度不一致問題。

## 標準化規範

### 時間型別標準
- **MSSQL 來源**：datetime2(7) → **ClickHouse 目標**：DateTime64(6)
- **原因**：DateTime64(6) 提供微秒精度，足以保留 MSSQL 的時間精度
- **適用範圍**：所有新建表格、重建表格、DDL 更新

### 欄位命名標準
- 同步時間戳：`_sync_time DateTime64(6)`
- 建立時間：`CreateDatetime DateTime64(6)` 或 `Nullable(DateTime64(6))`
- 更新時間：`UpdateDatetime DateTime64(6)` 或 `Nullable(DateTime64(6))`
- 業務時間：依業務需求決定是否 Nullable

---

## 實現階段

### 階段 1：DDL 模板標準化

#### 1.1 建立 DDL 模板檔案
```sql
-- sql/templates/bronze_table_template.sql
CREATE TABLE bronze.{table_name}
(
    -- 業務欄位 (依實際需求)
    {business_columns},
    
    -- 標準時間欄位
    _sync_time DateTime64(6) DEFAULT now64(6),
    
    -- 業務時間欄位範例
    CreateDatetime Nullable(DateTime64(6)),
    UpdateDatetime Nullable(DateTime64(6))
)
ENGINE = MergeTree()
ORDER BY (_sync_time)
PARTITION BY toYYYYMM(_sync_time);
```

#### 1.2 更新現有 DDL 檔案
- 檢查 `sql/02_create_bmp_tables.sql`
- 檢查 `sql/03_create_common_tables.sql`
- 將所有 DateTime64(3) 改為 DateTime64(6)

### 階段 2：同步腳本更新

#### 2.1 更新 JDBC 查詢
```python
# sync/sync_to_clickhouse.py 中的時間欄位處理
def format_datetime_column(mssql_datetime):
    """將 MSSQL datetime2(7) 轉換為 ClickHouse DateTime64(6) 格式"""
    if mssql_datetime is None:
        return None
    # 保留到微秒精度 (6位小數)
    return mssql_datetime.strftime('%Y-%m-%d %H:%M:%S.%f')[:-1]
```

#### 2.2 更新增量同步邏輯
```python
# 確保 watermark 比較使用相同精度
def get_last_sync_time():
    query = """
    SELECT max(_sync_time) as last_sync 
    FROM bronze.{table_name}
    """
    # 返回 DateTime64(6) 格式
```

### 階段 3：表格重建策略

#### 3.1 失敗欄位處理方案

**方案 A：重建表格（推薦）**
```sql
-- 1. 建立新表格 (使用標準精度)
CREATE TABLE bronze.{table_name}_new AS bronze.{table_name}
ENGINE = MergeTree()
ORDER BY (_sync_time);

-- 2. 修改時間欄位精度
ALTER TABLE bronze.{table_name}_new 
MODIFY COLUMN CreateDatetime Nullable(DateTime64(6)),
MODIFY COLUMN UpdateDatetime Nullable(DateTime64(6));

-- 3. 複製資料
INSERT INTO bronze.{table_name}_new 
SELECT * FROM bronze.{table_name};

-- 4. 原子性替換
RENAME TABLE 
    bronze.{table_name} TO bronze.{table_name}_old,
    bronze.{table_name}_new TO bronze.{table_name};

-- 5. 清理舊表格
DROP TABLE bronze.{table_name}_old;
```

**方案 B：處理 NULL 值後轉換**
```sql
-- 先將 NULL 值替換為預設值
UPDATE bronze.{table_name} 
SET CreateDatetime = '1900-01-01 00:00:00.000000'
WHERE CreateDatetime IS NULL;

-- 然後修改欄位型別
ALTER TABLE bronze.{table_name}
MODIFY COLUMN CreateDatetime DateTime64(6);
```

#### 3.2 批次重建腳本
```python
# scripts/rebuild_tables_with_standard_precision.py
FAILED_TABLES = [
    'bpm_act_hi_procinst',
    'bpm_act_hi_taskinst', 
    'bpm_act_hi_varinst',
    'common_hr_employee',
    'common_process_role_group',
    'common_process_role_group_mapping'
]

def rebuild_table_with_standard_precision(table_name):
    # 實現重建邏輯
    pass
```

---

## 實現步驟

### 步驟 1：準備階段
1. **建立 DDL 模板**
   - 建立標準化的表格建立模板
   - 定義時間欄位命名規範

2. **更新現有 DDL**
   - 修改 `sql/02_create_bmp_tables.sql`
   - 修改 `sql/03_create_common_tables.sql`
   - 將所有 DateTime64(3) 改為 DateTime64(6)

### 步驟 2：同步邏輯更新
1. **更新同步腳本**
   - 修改 `sync/sync_to_clickhouse.py`
   - 確保時間格式轉換正確

2. **測試同步功能**
   - 驗證新精度下的增量同步
   - 確認 watermark 比較邏輯正確

### 步驟 3：表格重建
1. **重建失敗表格**
   - 執行批次重建腳本
   - 驗證資料完整性

2. **更新 Silver/Gold 層**
   - 檢查下游表格是否需要更新
   - 確保整個資料流的時間精度一致

### 步驟 4：驗證與文件
1. **全面驗證**
   - 執行端到端測試
   - 驗證時間精度一致性

2. **更新文件**
   - 更新開發規範
   - 記錄標準化流程

---

## 檔案清單

### 需要建立的檔案
- `sql/templates/bronze_table_template.sql` - DDL 模板
- `scripts/rebuild_tables_with_standard_precision.py` - 批次重建工具
- `scripts/validate_datetime_precision.py` - 精度驗證工具
- `docs/datetime_precision_standards.md` - 開發規範文件

### 需要修改的檔案
- `sql/02_create_bmp_tables.sql` - BMP 表格 DDL
- `sql/03_create_common_tables.sql` - Common 表格 DDL  
- `sync/sync_to_clickhouse.py` - 同步腳本
- `sync/sync_incremental.py` - 增量同步腳本

---

## 風險評估

### 高風險
- **資料遺失**：重建表格過程中的資料安全
- **服務中斷**：重建期間的同步服務影響

### 中風險  
- **精度不一致**：部分表格未完全標準化
- **效能影響**：DateTime64(6) vs DateTime64(3) 的儲存差異

### 低風險
- **相容性問題**：現有查詢語法需要調整

---

## 成功指標

### 技術指標
- ✅ 所有 Bronze 層表格使用 DateTime64(6)
- ✅ 增量同步精度提升到微秒級
- ✅ MSSQL 與 ClickHouse 時間精度一致

### 業務指標  
- ✅ 資料同步準確性提升
- ✅ 時間相關查詢結果更精確
- ✅ 減少因時間精度導致的資料遺漏

---

## 時程規劃

### Week 1: 準備與設計
- 建立 DDL 模板和標準
- 更新現有 DDL 檔案
- 準備重建腳本

### Week 2: 實施與測試
- 執行表格重建
- 更新同步腳本
- 進行功能測試

### Week 3: 驗證與部署
- 端到端驗證
- 生產環境部署
- 文件更新

這個計畫提供了完整的時間精度標準化路徑，確保未來所有表格都使用一致的時間精度標準。