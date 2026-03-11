# ETL 腳本工具目錄 (scripts/etl)

此目錄包含負責從來源系統 (MSSQL) 抽取資料、清洗並轉換至 ClickHouse (Bronze, Silver, Gold) 的核心工具。

## 資料流概覽 (Data Flow Overview)

本專案的 ETL 流程主要是將資料從 **MSSQL (QAS/Production)** 抽取至 **ClickHouse Bronze 層**，並透過以下技術棧實現：
1. **來源端**: MSSQL (包含 APP_SRV_BPM 與 APP_SRV_COMMON 資料庫)。
2. **傳輸機制**: 透過 **ClickHouse JDBC Bridge** (資料源名稱：`mssql_master`) 進行遠端查詢。
3. **目標端**: ClickHouse Bronze Layer (作為 ODS 原始資料層)。

## 核心執行腳本 (Core Scripts)

### 1. execute_etl.py - 結構建立與管理
負責管理資料庫的架構 (Schema)。它的核心功能是讀取並執行 sql/etl/ 下的 SQL 檔案，確保 ClickHouse 端的表格結構（包含 Bronze 原始表、Silver 轉換視圖、Gold KPI 報表）依序正確建立。
- **僅建立缺表**: python execute_etl.py --skip-existing (推薦日常用法，偵測到表已存在則跳過)
- **強制重建**: python execute_etl.py --force (會執行 DROP TABLE，適合架構大改時使用)
- **狀態檢查**: python execute_etl.py --status (統計當前資料庫各層級表格的筆數與狀態)

### 2. sync_unified.py - 資料同步主體
負責資料的搬運與同步。透過 JDBC Bridge 連接 MSSQL，處理資料型別轉換、增量同步邏輯 (Watermark) 以及針對大表的切片 (Batching) 同步。

#### 同步表清單 (Synced Tables)

目前的同步對照表如下：

| 來源系統 (MSSQL) | 目標系統 (ClickHouse) | 同步策略 |
| :--- | :--- | :--- |
| APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 | bronze.bpm_act_hi_taskinst | batch |
| APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 | bronze.bpm_act_hi_varinst | batch |
| APP_SRV_BPM.dbo.ACT_HI_PROCINST_0108 | bronze.bpm_act_hi_procinst | batch |
| APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK | bronze.bpm_act_hi_identitylink | batch |
| APP_SRV_BPM.dbo.ACT_RE_PROCDEF_0108 | bronze.bpm_act_re_procdef | full |
| APP_SRV_COMMON.dbo.HR_Employee | bronze.common_hr_employee | full |
| APP_SRV_COMMON.dbo.EmpNodeRoleMapping | bronze.common_emp_node_role_mapping | full |
| APP_SRV_COMMON.dbo.EmpOrgInfoMapping | bronze.common_emp_org_info_mapping | full |
| APP_SRV_COMMON.dbo.EmpUserGroupMapping | bronze.common_emp_user_group_mapping | full |
| APP_SRV_COMMON.dbo.UserGroup | bronze.common_user_group | full |
| APP_SRV_COMMON.dbo.ProcessRoleUserMapping | bronze.common_process_role_user_mapping | full |
| APP_SRV_COMMON.dbo.MDM_LINE_DESC_MASTER_0202 | bronze.common_mdm_line_desc_master | full |
| APP_SRV_COMMON.dbo.MDM_PROD_AREA_MASTER_0202 | bronze.common_mdm_prod_area_master | full |
| APP_SRV_COMMON.dbo.MDM_FACTORY_AREA_MASTER_0202 | bronze.common_mdm_factory_area_master | full |
| APP_SRV_COMMON.dbo.MDM_MFG_SITE_MASTER_0202 | bronze.common_mdm_mfg_site_master | full |
| APP_SRV_COMMON.dbo.DMPFunctionConfig_0202 | bronze.common_dmp_function_config | full |
| APP_SRV_COMMON.dbo.DMPFunctionClientMapping_0202 | bronze.common_dmp_function_client_mapping | full |

#### 基本用法
- **同步所有表**: python sync_unified.py --table all
- **同步特定表**: python sync_unified.py --table taskinst

#### **時間區間同步 (Time Range Sync)**
如果是 Strategy: batch 的大表 (如 taskinst, varinst, procinst)，您可以指定區間。
- **指定日期**: python sync_unified.py --table taskinst --start 2025-10-01 --end 2025-10-10
- **調整切分步長**: python sync_unified.py --table taskinst --step-days 1 (每天切一包，適合資料極大的情況)

#### **防呆偵測 (Auto Start Date Detection)**
- **自動起點**: 當您不帶 --start 參數且系統中沒有同步紀錄 (Watermark) 時，程式會自動透過 JDBC Bridge 查詢 MSSQL 來源端該表的最早紀錄時間作為起始點。這確保了同步會從有資料的第一天開始執行，避免從系統預設的 1970 年開始無意義的跑批。

## 自動化封裝 (Wrappers)

- **init_pipeline.sh**: 首次部署專用。依序呼叫 execute_etl.py 建立各層級結構，再執行 sync_unified.py 進行全量同步。
- **daily_etl_wrapper.sh**: 日常排程專用。僅執行 sync_unified.py 進行增量資料更新。

---

## 維運與疑難排解 (Troubleshooting)

### 1. 欄位不匹配 (Columns mismatch)
若來源端 MSSQL 增加欄位，請修改 sql/etl/ 下對應的 .sql 檔案，然後執行 python execute_etl.py 重建表格（或手動使用 ALTER TABLE 增加欄位）。

### 2. 進度重置 (Watermark Reset)
若想讓某張表重新從頭同步，請修改 bronze._sync_watermark 中該表的紀錄：
```sql
ALTER TABLE bronze._sync_watermark DELETE WHERE table_name = 'bronze.bpm_act_hi_taskinst';
```
