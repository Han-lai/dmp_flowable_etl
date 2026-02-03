import clickhouse_connect
import time

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

TABLE_MAPPINGS = [
    {
        "target": "bronze.common_emp_node_role_mapping",
        "source": "APP_SRV_COMMON.dbo.EmpNodeRoleMapping",
        "columns": "EmpCode, NodeCode, UpdateTime, UpdateEmp"
    },
    {
        "target": "bronze.common_emp_org_info_mapping",
        "source": "APP_SRV_COMMON.dbo.EmpOrgInfoMapping",
        "columns": "EmpCode, Plant, MFGFactoryId, UpdateTime, UpdateEmp"
    },
    {
        "target": "bronze.common_emp_user_group_mapping",
        "source": "APP_SRV_COMMON.dbo.EmpUserGroupMapping",
        "columns": "EmpCode, UserGroupId, UpdateTime, UpdateEmp"
    },
    {
        "target": "bronze.common_user_group",
        "source": "APP_SRV_COMMON.dbo.UserGroup",
        "columns": "UserGroupId, UserGroupName, UserGroupDesc, UpdateTime, UpdateEmp"
    },
    {
        "target": "bronze.common_process_role_user_mapping",
        "source": "APP_SRV_COMMON.dbo.ProcessRoleUserMapping",
        "columns": "ID, RoleId, Plant, Factory, ProductionArea, LineName, EmpCode, Updater, UpdateDatetime, UpdateCount, Creator, CreateDatetime"
    }
]

def main():
    print("Connecting to ClickHouse...")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    # 1. Execute DDL first (Safety check, though assumed run already)
    # Actually, let the user run the DDL manually or via this script?
    # Better to assume DDL is run. But we can truncate first.
    
    for mapping in TABLE_MAPPINGS:
        target = mapping['target']
        source = mapping['source']
        cols = mapping['columns']
        
        print(f"\nSyncing {target}...")
        
        # Truncate to ensure clean slate (since we are replacing)
        print(f"  Truncating {target}...")
        client.command(f"TRUNCATE TABLE {target}")
        
        # Insert from JDBC
        print(f"  Inserting data from {source}...")
        insert_sql = f"""
        INSERT INTO {target} ({cols})
        SELECT {cols}
        FROM jdbc('mssql_master', 'SELECT {cols} FROM {source}')
        """
        
        start_time = time.time()
        try:
            client.command(insert_sql)
            duration = time.time() - start_time
            
            # Count rows
            count = client.command(f"SELECT count() FROM {target}")
            print(f"  ✅ Synced {count:,} rows in {duration:.2f} seconds.")
            
        except Exception as e:
            print(f"  ❌ Error syncing {target}: {e}")

    print("\nAll sync operations completed.")

if __name__ == "__main__":
    main()
