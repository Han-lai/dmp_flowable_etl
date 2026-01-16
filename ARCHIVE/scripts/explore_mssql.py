"""
MSSQL 資料表探索腳本
用於連線 MSSQL 並取得目標資料表的 schema、row count 等資訊
"""
import pyodbc
import pandas as pd
from datetime import datetime

# 連線設定
SERVER = "twtpesqldv2.delta.corp"
PORT = "1433"
USERNAME = "DMP_APP_SRV"
PASSWORD = "APP@DB#01"

# 目標資料庫與資料表
DATABASES = {
    "APP_SRV_BPM": [
        "ACT_HI_IDENTITYLINK",
        "ACT_HI_PROCINST", 
        "ACT_HI_TASKINST",
        "ACT_HI_VARINST",
        "ACT_RE_PROCDEF"
    ],
    "APP_SRV_COMMON": [
        "DMPFunctionClientMapping",
        "DMPFunctionConfig",
        "EmpNodeRoleMapping",
        "EmpOrgInfoMapping",
        "EmpUserGroupMapping",
        "FlowableTaskStats",
        "HR_Employee",
        "ProcessRoleGroup",
        "ProcessRoleGroupMapping",
        "ProcessRoleUserMapping",
        "UserGroup"
    ]
}

def get_connection(database):
    """建立 MSSQL 連線"""
    conn_str = (
        f"DRIVER={{SQL Server}};"
        f"SERVER={SERVER},{PORT};"
        f"DATABASE={database};"
        f"UID={USERNAME};"
        f"PWD={PASSWORD};"
    )
    return pyodbc.connect(conn_str)

def get_table_schema(conn, table_name):
    """取得資料表的欄位結構"""
    query = f"""
    SELECT 
        COLUMN_NAME,
        DATA_TYPE,
        CHARACTER_MAXIMUM_LENGTH,
        IS_NULLABLE,
        COLUMN_DEFAULT
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = '{table_name}'
    ORDER BY ORDINAL_POSITION
    """
    return pd.read_sql(query, conn)


def get_row_count(conn, table_name):
    """取得資料表的 row count"""
    query = f"SELECT COUNT(*) as cnt FROM {table_name}"
    cursor = conn.cursor()
    cursor.execute(query)
    return cursor.fetchone()[0]

def get_primary_keys(conn, table_name):
    """取得資料表的 Primary Key"""
    query = f"""
    SELECT COLUMN_NAME
    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
    WHERE OBJECTPROPERTY(OBJECT_ID(CONSTRAINT_SCHEMA + '.' + CONSTRAINT_NAME), 'IsPrimaryKey') = 1
    AND TABLE_NAME = '{table_name}'
    """
    df = pd.read_sql(query, conn)
    return df['COLUMN_NAME'].tolist()

def get_indexes(conn, table_name):
    """取得資料表的索引資訊"""
    query = f"""
    SELECT 
        i.name AS index_name,
        COL_NAME(ic.object_id, ic.column_id) AS column_name,
        i.is_unique
    FROM sys.indexes i
    INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
    WHERE i.object_id = OBJECT_ID('{table_name}')
    AND i.name IS NOT NULL
    """
    return pd.read_sql(query, conn)

def get_sample_data(conn, table_name, limit=5):
    """取得資料表的樣本資料"""
    query = f"SELECT TOP {limit} * FROM {table_name}"
    return pd.read_sql(query, conn)

def explore_database(database, tables):
    """探索指定資料庫的所有目標資料表"""
    print(f"\n{'='*60}")
    print(f"Database: {database}")
    print(f"{'='*60}")
    
    conn = get_connection(database)
    results = []
    
    for table in tables:
        print(f"\n--- {table} ---")
        try:
            # Schema
            schema = get_table_schema(conn, table)
            print(f"Columns: {len(schema)}")
            print(schema.to_string(index=False))
            
            # Row count
            row_count = get_row_count(conn, table)
            print(f"\nRow Count: {row_count:,}")
            
            # Primary Keys
            pks = get_primary_keys(conn, table)
            print(f"Primary Keys: {pks}")
            
            # Indexes
            indexes = get_indexes(conn, table)
            if not indexes.empty:
                print(f"Indexes:\n{indexes.to_string(index=False)}")
            
            # 檢查時間戳欄位
            time_cols = schema[schema['DATA_TYPE'].isin(['datetime', 'datetime2', 'date', 'timestamp'])]
            if not time_cols.empty:
                print(f"Time Columns: {time_cols['COLUMN_NAME'].tolist()}")
            
            results.append({
                'database': database,
                'table': table,
                'columns': len(schema),
                'row_count': row_count,
                'primary_keys': pks,
                'time_columns': time_cols['COLUMN_NAME'].tolist() if not time_cols.empty else []
            })
            
        except Exception as e:
            print(f"Error: {e}")
            results.append({
                'database': database,
                'table': table,
                'error': str(e)
            })
    
    conn.close()
    return results

def main():
    print(f"MSSQL 資料表探索")
    print(f"執行時間: {datetime.now()}")
    print(f"Server: {SERVER}:{PORT}")
    
    all_results = []
    for database, tables in DATABASES.items():
        results = explore_database(database, tables)
        all_results.extend(results)
    
    # 輸出摘要
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    summary_df = pd.DataFrame(all_results)
    print(summary_df.to_string(index=False))
    
    # 儲存結果
    summary_df.to_csv('table_exploration_results.csv', index=False)
    print(f"\n結果已儲存至 table_exploration_results.csv")

if __name__ == "__main__":
    main()
