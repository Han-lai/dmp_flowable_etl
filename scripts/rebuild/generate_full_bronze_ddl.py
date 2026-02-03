import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

# Existing tables to preserve
EXISTING_TABLES = [
    "bronze.bpm_act_hi_taskinst",
    "bronze.bpm_act_hi_varinst",
    "bronze.bpm_act_hi_procinst",
    "bronze._sync_watermark"
]

# New tables to add
NEW_TABLES_DDL = """
-- ==========================================
-- New User Utilization Tables (2026-02-02)
-- ==========================================

-- 1. common_emp_node_role_mapping
DROP TABLE IF EXISTS bronze.common_emp_node_role_mapping;
CREATE TABLE bronze.common_emp_node_role_mapping (
    EmpCode String,
    NodeCode String,
    UpdateTime DateTime,
    UpdateEmp String,
    _sync_time DateTime64(3) DEFAULT now64(3)
) ENGINE = ReplacingMergeTree
ORDER BY (EmpCode, NodeCode)
TTL UpdateTime + INTERVAL 1 YEAR;

-- 2. common_emp_org_info_mapping
DROP TABLE IF EXISTS bronze.common_emp_org_info_mapping;
CREATE TABLE bronze.common_emp_org_info_mapping (
    EmpCode String,
    Plant String,
    MFGFactoryId String,
    UpdateTime DateTime,
    UpdateEmp String,
    _sync_time DateTime64(3) DEFAULT now64(3)
) ENGINE = ReplacingMergeTree
ORDER BY (EmpCode, Plant, MFGFactoryId)
TTL UpdateTime + INTERVAL 1 YEAR;

-- 3. common_emp_user_group_mapping
DROP TABLE IF EXISTS bronze.common_emp_user_group_mapping;
CREATE TABLE bronze.common_emp_user_group_mapping (
    EmpCode String,
    UserGroupId Int32,
    UpdateTime DateTime,
    UpdateEmp String,
    _sync_time DateTime64(3) DEFAULT now64(3)
) ENGINE = ReplacingMergeTree
ORDER BY (EmpCode, UserGroupId)
TTL UpdateTime + INTERVAL 1 YEAR;

-- 4. common_user_group
DROP TABLE IF EXISTS bronze.common_user_group;
CREATE TABLE bronze.common_user_group (
    UserGroupId Int32,
    UserGroupName String,
    UserGroupDesc String,
    UpdateTime DateTime,
    UpdateEmp String,
    _sync_time DateTime64(3) DEFAULT now64(3)
) ENGINE = ReplacingMergeTree
ORDER BY (UserGroupId)
TTL UpdateTime + INTERVAL 1 YEAR;

-- 5. common_process_role_user_mapping
DROP TABLE IF EXISTS bronze.common_process_role_user_mapping;
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
    _sync_time DateTime64(3) DEFAULT now64(3)
) ENGINE = ReplacingMergeTree
ORDER BY (ID)
TTL toDate(_sync_time) + INTERVAL 1 YEAR;
"""

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    output_content = []
    output_content.append("-- ========================================")
    output_content.append("-- 步驟 1: Bronze 層完整建表 (Consolidated)")
    output_content.append("-- ========================================\n")
    
    # 1. Fetch Existing DDLs
    print("Fetching existing DDLs...")
    for table in EXISTING_TABLES:
        try:
            ddl = client.command(f"SHOW CREATE TABLE {table}")
            # Format: DROP IF EXISTS + CREATE
            output_content.append(f"-- {table}")
            output_content.append(f"DROP TABLE IF EXISTS {table};")
            # Ensure the DDL ends with semicolon
            if not ddl.strip().endswith(';'):
                ddl += ';'
            output_content.append(ddl)
            output_content.append("")
        except Exception as e:
            print(f"Warning: Could not fetch DDL for {table}: {e}")
            
    # 2. Append New DDLs
    print("Appending new DDLs...")
    output_content.append(NEW_TABLES_DDL)
    
    # 3. Write to file
    with open('sql/rebuild/01_bronze_tables.sql', 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_content))
        
    print("Successfully generated sql/rebuild/01_bronze_tables.sql")

if __name__ == "__main__":
    main()
