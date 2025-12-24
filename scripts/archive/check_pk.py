"""
查詢 MSSQL 表的 Primary Key
"""

import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

# DMP COMMON 表清單
TABLES = [
    "APP_SRV_COMMON.dbo.FlowableTaskStats",
    "APP_SRV_COMMON.dbo.HR_Employee", 
    "APP_SRV_COMMON.dbo.ProcessRoleUserMapping",
    "APP_SRV_COMMON.dbo.ProcessRoleGroup",
    "APP_SRV_COMMON.dbo.ProcessRoleGroupMapping",
    "APP_SRV_COMMON.dbo.EmpNodeRoleMapping",
    "APP_SRV_COMMON.dbo.EmpOrgInfoMapping",
    "APP_SRV_COMMON.dbo.EmpUserGroupMapping",
    "APP_SRV_COMMON.dbo.UserGroup",
    "APP_SRV_COMMON.dbo.DMPFunctionConfig",
    "APP_SRV_COMMON.dbo.DMPFunctionClientMapping"
]

def get_primary_keys():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    for table in TABLES:
        schema, table_name = table.split(".")[-2:]  # dbo.TableName
        
        sql = f"""
        SELECT * FROM jdbc('mssql_master', '
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
            WHERE OBJECTPROPERTY(OBJECT_ID(CONSTRAINT_SCHEMA + ''.'' + QUOTENAME(CONSTRAINT_NAME)), ''IsPrimaryKey'') = 1 
            AND TABLE_SCHEMA = ''{schema}'' 
            AND TABLE_NAME = ''{table_name}''
            ORDER BY ORDINAL_POSITION
        ')
        """
        
        try:
            result = client.query(sql)
            pk_columns = [row[0] for row in result.result_rows]
            print(f"{table_name}: {', '.join(pk_columns) if pk_columns else 'No PK'}")
        except Exception as e:
            print(f"{table_name}: Error - {e}")

if __name__ == "__main__":
    get_primary_keys()