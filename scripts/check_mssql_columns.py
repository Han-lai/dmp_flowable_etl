"""
檢查 MSSQL 各表的欄位結構
目的：確認是否有適合做增量同步的追蹤欄位（如 LAST_UPDATED_TIME_）
"""

import clickhouse_connect

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

# 要檢查的表
TABLES_TO_CHECK = [
    # APP_SRV_BPM
    ("APP_SRV_BPM", "dbo", "ACT_HI_PROCINST"),
    ("APP_SRV_BPM", "dbo", "ACT_HI_TASKINST"),
    ("APP_SRV_BPM", "dbo", "ACT_HI_IDENTITYLINK"),
    ("APP_SRV_BPM", "dbo", "ACT_HI_VARINST"),
    ("APP_SRV_BPM", "dbo", "ACT_RE_PROCDEF"),
    # APP_SRV_COMMON
    ("APP_SRV_COMMON", "dbo", "FlowableTaskStats"),
    ("APP_SRV_COMMON", "dbo", "HR_Employee"),
    ("APP_SRV_COMMON", "dbo", "ProcessRoleUserMapping"),
    ("APP_SRV_COMMON", "dbo", "ProcessRoleGroup"),
    ("APP_SRV_COMMON", "dbo", "ProcessRoleGroupMapping"),
    ("APP_SRV_COMMON", "dbo", "EmpNodeRoleMapping"),
    ("APP_SRV_COMMON", "dbo", "EmpOrgInfoMapping"),
    ("APP_SRV_COMMON", "dbo", "EmpUserGroupMapping"),
    ("APP_SRV_COMMON", "dbo", "UserGroup"),
    ("APP_SRV_COMMON", "dbo", "DMPFunctionConfig"),
    ("APP_SRV_COMMON", "dbo", "DMPFunctionClientMapping"),
]

# 關注的欄位關鍵字（可能用於增量同步）
TRACKING_KEYWORDS = ['TIME', 'DATE', 'UPDATE', 'CREATE', 'MODIFY', 'STAMP']

def get_table_columns(client, database, schema, table):
    """透過 JDBC Bridge 查詢 MSSQL 表結構"""
    sql = f"""
    SELECT * FROM jdbc('mssql_master', '
        SELECT 
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            COLUMN_DEFAULT
        FROM {database}.INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = ''{schema}'' AND TABLE_NAME = ''{table}''
        ORDER BY ORDINAL_POSITION
    ')
    """
    result = client.query(sql)
    return result.result_rows

def check_primary_key(client, database, schema, table):
    """查詢主鍵欄位"""
    sql = f"""
    SELECT * FROM jdbc('mssql_master', '
        SELECT COLUMN_NAME
        FROM {database}.INFORMATION_SCHEMA.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = ''{schema}'' 
          AND TABLE_NAME = ''{table}''
          AND CONSTRAINT_NAME LIKE ''PK_%''
        ORDER BY ORDINAL_POSITION
    ')
    """
    result = client.query(sql)
    return [row[0] for row in result.result_rows]

def is_tracking_column(col_name, data_type):
    """判斷是否為追蹤欄位"""
    col_upper = col_name.upper()
    for keyword in TRACKING_KEYWORDS:
        if keyword in col_upper:
            return True
    if 'datetime' in data_type.lower() or 'timestamp' in data_type.lower():
        return True
    return False

def main():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    print("連線成功\n")
    
    print("=" * 100)
    print("MSSQL 表結構分析 - 增量同步可行性評估")
    print("=" * 100)
    
    summary = []
    
    for database, schema, table in TABLES_TO_CHECK:
        full_name = f"{database}.{schema}.{table}"
        print(f"\n{'─' * 100}")
        print(f"📋 {full_name}")
        print(f"{'─' * 100}")
        
        # 取得欄位
        columns = get_table_columns(client, database, schema, table)
        
        # 取得主鍵
        pk_columns = check_primary_key(client, database, schema, table)
        
        # 找出追蹤欄位
        tracking_cols = []
        all_cols = []
        
        for row in columns:
            col_name, data_type, nullable, default = row[0], row[1], row[2], row[3]
            all_cols.append(col_name)
            if is_tracking_column(col_name, data_type):
                tracking_cols.append((col_name, data_type))
        
        # 輸出
        print(f"  主鍵: {pk_columns if pk_columns else '無'}")
        print(f"  欄位數: {len(columns)}")
        print(f"  追蹤欄位候選:")
        if tracking_cols:
            for col, dtype in tracking_cols:
                marker = "⭐" if "UPDATE" in col.upper() or "MODIFY" in col.upper() else "  "
                print(f"    {marker} {col} ({dtype})")
        else:
            print(f"    ❌ 無")
        
        # 記錄 summary
        best_tracking = None
        for col, dtype in tracking_cols:
            if "UPDATE" in col.upper() or "MODIFY" in col.upper():
                best_tracking = col
                break
        if not best_tracking and tracking_cols:
            # 退而求其次，找 END_TIME 或 CREATE_TIME
            for col, dtype in tracking_cols:
                if "END" in col.upper() or "CREATE" in col.upper():
                    best_tracking = col
                    break
        
        summary.append({
            "table": table,
            "pk": pk_columns,
            "tracking_col": best_tracking,
            "can_incremental": best_tracking is not None
        })
    
    # 輸出總結
    print("\n")
    print("=" * 100)
    print("📊 增量同步可行性總結")
    print("=" * 100)
    print(f"{'表名':<35} {'主鍵':<20} {'追蹤欄位':<25} {'可增量'}")
    print("-" * 100)
    
    for s in summary:
        pk_str = ",".join(s["pk"]) if s["pk"] else "-"
        tracking = s["tracking_col"] if s["tracking_col"] else "-"
        can_inc = "✅ 是" if s["can_incremental"] else "❌ 否"
        print(f"{s['table']:<35} {pk_str:<20} {tracking:<25} {can_inc}")
    
    # 統計
    can_inc_count = sum(1 for s in summary if s["can_incremental"])
    print("-" * 100)
    print(f"可增量同步: {can_inc_count}/{len(summary)} 張表")

if __name__ == "__main__":
    main()
