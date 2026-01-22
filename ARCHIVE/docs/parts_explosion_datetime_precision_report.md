# Parts 爆炸與時間精度問題修正報告

## 執行時間
2026-01-20 10:45-10:50

## 問題 1: Parts 爆炸問題

### 狀態：✅ 已解決（症狀）⚠️ 設定未載入（預防）

### 執行內容
1. **Parts 合併**：執行 `scripts/fix_parts_explosion.py`
   - 成功將 6 張 Bronze 層表的 Parts 從 2 parts → 1 part
   
2. **預防設定**：建立 `docker/clickhouse/config/merge_settings.xml`
   - 設定 parts_to_delay_insert: 150
   - 設定 parts_to_throw_insert: 300
   - 設定批次大小參數

3. **Docker 映射**：更新 `docker/docker-compose-portainer.yml`
   - 新增 `./clickhouse/config:/var/lib/clickhouse/server/config.d` 映射

### 驗證結果
- ✅ **Parts 狀態正常**：所有 19 張表格 Parts 數量都是 1
- ❌ **設定未載入**：ClickHouse 仍使用預設值，設定檔案未生效

### 後續處理
- 需要在 VM 上正確建立 `clickhouse/config/merge_settings.xml` 檔案
- 重啟容器後再次驗證設定載入

---

## 問題 2: 時間精度不一致問題

### 狀態：🟡 部分解決（15/30 欄位成功）

### 問題描述
- MSSQL: DateTime64(7) 
- ClickHouse: DateTime64(3)
- 影響：微秒級資料遺失，增量同步可能跳過資料

### 執行內容
執行 `scripts/fix_datetime_precision.py`，將 DateTime64(3) 統一改為 DateTime64(6)

### 修正結果

#### ✅ 成功修正（15 個欄位）
- `_sync_watermark`: 2 個欄位
- `bpm_act_hi_identitylink`: 2 個欄位  
- `common_dmp_function_client_mapping`: 2 個欄位
- `common_dmp_function_config`: 2 個欄位
- `common_emp_node_role_mapping`: 1 個欄位
- `common_emp_org_info_mapping`: 1 個欄位
- `common_emp_user_group_mapping`: 1 個欄位
- `common_hr_employee`: 1 個欄位（ModifyDate）
- `common_process_role_user_mapping`: 2 個欄位
- `common_user_group`: 1 個欄位

#### ❌ 修正失敗（15 個欄位）
**失敗原因**：Nullable 欄位包含 NULL 值，無法直接轉換

1. `bronze.bpm_act_hi_procinst` (3 個欄位)
   - END_TIME_, START_TIME_, _sync_time

2. `bronze.bpm_act_hi_taskinst` (5 個欄位)  
   - CLAIM_TIME_, DUE_DATE_, END_TIME_, START_TIME_, _sync_time

3. `bronze.bpm_act_hi_varinst` (2 個欄位)
   - CREATE_TIME_, _sync_time

4. `bronze.common_hr_employee` (1 個欄位)
   - TerminateDate

5. `bronze.common_process_role_group` (2 個欄位)
   - CreateDatetime, UpdateDatetime

6. `bronze.common_process_role_group_mapping` (2 個欄位)
   - CreateDatetime, UpdateDatetime

### 備份檔案
所有表格結構已自動備份至 `backup_structure_*.sql` 檔案

---

## 建議後續處理

### 立即處理
1. **Parts 爆炸預防**：在 VM 上正確部署設定檔案
2. **時間精度**：已成功的 15 個欄位可正常使用

### 長期處理
1. **失敗欄位處理**：
   - 選項 1：改用 Nullable(DateTime64(6))
   - 選項 2：先處理 NULL 值再轉換
   - 選項 3：重建表格時統一精度

2. **標準化規範**：
   - 建立時間精度標準（建議 DateTime64(6)）
   - 更新 DDL 模板
   - 新表格統一使用標準精度

---

## 影響評估

### Parts 爆炸問題
- ✅ **目前無影響**：Parts 數量已正常
- ⚠️ **未來風險**：預防機制未生效，可能再次發生

### 時間精度問題  
- ✅ **50% 改善**：15/30 欄位已修正
- 🟡 **部分風險**：失敗欄位仍有精度不一致問題
- 📈 **增量同步**：已修正欄位的同步精度提升

---

## 檔案清單

### 新建檔案
- `scripts/fix_parts_explosion.py` - Parts 合併工具
- `scripts/verify_parts_explosion_fix.py` - Parts 狀態驗證工具  
- `scripts/fix_datetime_precision.py` - 時間精度修正工具
- `docker/clickhouse/config/merge_settings.xml` - ClickHouse 設定檔案
- `backup_structure_*.sql` - 表格結構備份檔案（多個）

### 修改檔案
- `docker/docker-compose-portainer.yml` - 新增 volume 映射

### 報告檔案
- `docs/parts_explosion_datetime_precision_report.md` - 本報告