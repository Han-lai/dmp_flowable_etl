-- ========================================
-- 步驟 2: Bronze Layer - Common Dimensions (MDM & HR)
-- 內容: MDM Tables, HR Employee, Mapping Tables
-- ========================================

-- ==========================================
-- 2.1 HR Employee Table (Missing in previous Rebuild)
-- ==========================================
-- DROP TABLE IF EXISTS bronze.common_hr_employee;
CREATE TABLE bronze.common_hr_employee (
    EmpCode String,
    EmpName String,
    DeptCode Nullable(String),
    DeptCodeLname Nullable(String),
    Email Nullable(String),
    IsActive Nullable(Int32),
    UpdateTime DateTime,
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
) ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY EmpCode
TTL UpdateTime + INTERVAL 1 YEAR;

-- ==========================================
-- 2.2 Organization & Role Mapping Tables
-- ==========================================

-- 1. common_emp_node_role_mapping
-- DROP TABLE IF EXISTS bronze.common_emp_node_role_mapping;
CREATE TABLE bronze.common_emp_node_role_mapping (
    EmpCode String,
    NodeCode String,
    UpdateTime DateTime,
    UpdateEmp String,
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
) ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY (EmpCode, NodeCode)
TTL UpdateTime + INTERVAL 1 YEAR;

-- 2. common_emp_org_info_mapping
-- DROP TABLE IF EXISTS bronze.common_emp_org_info_mapping;
CREATE TABLE bronze.common_emp_org_info_mapping (
    EmpCode String,
    Plant String,
    MFGFactoryId String,
    UpdateTime DateTime,
    UpdateEmp String,
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
) ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY (EmpCode, Plant, MFGFactoryId)
TTL UpdateTime + INTERVAL 1 YEAR;

-- 3. common_emp_user_group_mapping
-- DROP TABLE IF EXISTS bronze.common_emp_user_group_mapping;
CREATE TABLE bronze.common_emp_user_group_mapping (
    EmpCode String,
    UserGroupId Int32,
    UpdateTime DateTime,
    UpdateEmp String,
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
) ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY (EmpCode, UserGroupId)
TTL UpdateTime + INTERVAL 1 YEAR;

-- 4. common_user_group
-- DROP TABLE IF EXISTS bronze.common_user_group;
CREATE TABLE bronze.common_user_group (
    UserGroupId Int32,
    UserGroupName String,
    UserGroupDesc String,
    UpdateTime DateTime,
    UpdateEmp String,
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
) ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY (UserGroupId)
TTL UpdateTime + INTERVAL 1 YEAR;

-- 5. common_process_role_user_mapping
-- DROP TABLE IF EXISTS bronze.common_process_role_user_mapping;
CREATE TABLE bronze.common_process_role_user_mapping (
    ID Int32,
    RoleId String,
    Plant String,
    Factory Nullable(String),
    ProductionArea Nullable(String),
    LineName Nullable(String),
    EmpCode String,
    Updater Nullable(String),
    UpdateDatetime Nullable(DateTime),
    UpdateCount Int32,
    Creator Nullable(String),
    CreateDatetime Nullable(DateTime),
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
) ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY (ID);
-- ==========================================
-- 2.3 MDM Master Tables (for Five Level Dimensions)
-- ==========================================

-- 1. common_mdm_line_desc_master
-- DROP TABLE IF EXISTS bronze.common_mdm_line_desc_master;
CREATE TABLE bronze.common_mdm_line_desc_master (
    LINE_NAME String,
    LINE_DESC String,
    PROD_AREA_ID String,
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
) ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY LINE_NAME
TTL toDateTime(_extracted_at) + INTERVAL 1 YEAR;

-- 2. common_mdm_prod_area_master
-- DROP TABLE IF EXISTS bronze.common_mdm_prod_area_master;
CREATE TABLE bronze.common_mdm_prod_area_master (
    PROD_AREA_ID String,
    PROD_AREA_CODE String,
    FACTORY String,
    MFG_PLANT_ID Nullable(String),
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
) ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY PROD_AREA_ID
TTL toDateTime(_extracted_at) + INTERVAL 1 YEAR;

-- 3. common_mdm_factory_area_master
-- DROP TABLE IF EXISTS bronze.common_mdm_factory_area_master;
CREATE TABLE bronze.common_mdm_factory_area_master (
    FACTORY String,
    FACTORY_DESC String,
    PLANT_NODE String,
    PLANT_NODE_DESC String,
    REGION String,
    MFG_SITE Nullable(String),
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
) ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY FACTORY
TTL toDateTime(_extracted_at) + INTERVAL 1 YEAR;

-- 4. common_mdm_mfg_site_master
-- DROP TABLE IF EXISTS bronze.common_mdm_mfg_site_master;
CREATE TABLE bronze.common_mdm_mfg_site_master (
    MFG_SITE String,
    MFG_SITE_DESC String,
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
) ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY MFG_SITE
TTL toDateTime(_extracted_at) + INTERVAL 1 YEAR;

-- 5. common_mdm_mfg_plant_master (User Request: Use for Plant/Factory info)
-- DROP TABLE IF EXISTS bronze.common_mdm_mfg_plant_master;
CREATE TABLE bronze.common_mdm_mfg_plant_master (
    MFG_PLANT_ID String,
    MFG_PLANT_CODE String, -- Factory Code
    MFG_PLANT_DESC String, -- Factory Name
    FACTORY String,        -- Plant Code
    VALIDITY Nullable(String),
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
) ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY MFG_PLANT_ID
TTL toDateTime(_extracted_at) + INTERVAL 1 YEAR;

-- 2.4 DMP Function Config Tables
-- ==========================================

-- 1. common_dmp_function_config
-- DROP TABLE IF EXISTS bronze.common_dmp_function_config;
CREATE TABLE bronze.common_dmp_function_config
(
    `ID` Int64,
    `Plant` Nullable(String),
    `Creator` Nullable(String),
    `Factory` Nullable(String),
    `Updater` Nullable(String),
    `LineName` Nullable(String),
    `UpdateCount` Nullable(Int64),
    `FunctionCode` Nullable(String),
    `AssignLineFlag` Nullable(String),
    `CreateDatetime` Nullable(DateTime64(3)),
    `ProductionArea` Nullable(String),
    `UpdateDatetime` Nullable(DateTime64(3)),
    `SyncESB` Nullable(String),
    `StartDps` Nullable(String),
    `AssignWorkStatus` Nullable(String),
    `EffectiveEndDate` Nullable(DateTime64(3)),
    `EffectiveStartDate` Nullable(DateTime64(3)),
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
)
ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY (ID);

-- 2. common_dmp_function_client_mapping
-- DROP TABLE IF EXISTS bronze.common_dmp_function_client_mapping;
CREATE TABLE bronze.common_dmp_function_client_mapping
(
    `ID` Int64,
    `Plant` Nullable(String),
    `Logsys` Nullable(String),
    `Region` Nullable(String),
    `Creator` Nullable(String),
    `Updater` Nullable(String),
    `UpdateCount` Nullable(Int64),
    `CreateDatetime` Nullable(DateTime64(3)),
    `UpdateDatetime` Nullable(DateTime64(3)),
    `_batch_id` String DEFAULT '',
    `_extracted_at` DateTime64(3) DEFAULT now(),
    `_sync_version` UInt64 DEFAULT 1
)
ENGINE = ReplacingMergeTree(_sync_version)
ORDER BY (ID);

