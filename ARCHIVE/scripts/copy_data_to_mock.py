"""
從舊 MSSQL 讀取資料，複製前 1000 筆到新 MSSQL（Docker Sandbox）

⚠️ 安全限制：
- 舊 MSSQL（source）只允許 SELECT，禁止任何寫入操作
- 新 MSSQL（target）允許 INSERT / CREATE TABLE
"""
import os
import pyodbc
import pandas as pd
from typing import Optional

# ============================================
# 連線設定（使用環境變數）
# ============================================

# 舊 MSSQL（來源）- 只讀
SOURCE_SERVER = os.getenv("SOURCE_MSSQL_SERVER", "twtpesqldv2.delta.corp")
SOURCE_PORT = os.getenv("SOURCE_MSSQL_PORT", "1433")
SOURCE_USER = os.getenv("SOURCE_MSSQL_USER", "DMP_APP_SRV")
SOURCE_PASSWORD = os.getenv("SOURCE_MSSQL_PASSWORD", "APP@DB#01")

# 新 MSSQL（目標）- Docker Sandbox（暫時硬編碼測試）
TARGET_SERVER = "localhost"
TARGET_PORT = "1433"
TARGET_USER = "sa"
TARGET_PASSWORD = "YourStrong@Passw0rd"

# ============================================
# 連線函數
# ============================================

def get_source_connection(database: str) -> pyodbc.Connection:
    """
    建立舊 MSSQL 連線（只讀來源）
    ⚠️ 此連線只允許 SELECT 操作
    """
    conn_str = (
        f"DRIVER={{SQL Server}};"
        f"SERVER={SOURCE_SERVER},{SOURCE_PORT};"
        f"DATABASE={database};"
        f"UID={SOURCE_USER};"
        f"PWD={SOURCE_PASSWORD};"
    )
    return pyodbc.connect(conn_str)


def get_target_connection() -> pyodbc.Connection:
    """
    建立新 MSSQL 連線（Docker Sandbox）- 連到 master
    此連線允許 INSERT / CREATE TABLE
    """
    conn_str = (
        f"DRIVER={{SQL Server}};"
        f"SERVER={TARGET_SERVER},{TARGET_PORT};"
        f"DATABASE=master;"
        f"UID={TARGET_USER};"
        f"PWD={TARGET_PASSWORD};"
    )
    print(f"[TARGET] 連線到 {TARGET_SERVER}:{TARGET_PORT}/master...")
    try:
        conn = pyodbc.connect(conn_str)
        print(f"[TARGET] 連線成功")
        return conn
    except Exception as e:
        print(f"[TARGET] 連線失敗: {e}")
        raise


# ============================================
# 資料讀取（只讀來源）
# ============================================

def read_from_source(source_conn: pyodbc.Connection, table_name: str, limit: int = 1000) -> pd.DataFrame:
    """
    從舊 MSSQL 讀取資料
    ⚠️ 只執行 SELECT，不執行任何寫入操作
    
    Args:
        source_conn: 舊 MSSQL 連線（只讀）
        table_name: 資料表名稱
        limit: 讀取筆數上限（預設 1000）
    
    Returns:
        DataFrame 包含讀取的資料
    """
    # ⚠️ 只允許 SELECT 操作
    query = f"SELECT TOP {limit} * FROM {table_name}"
    print(f"[SOURCE] 執行查詢: {query}")
    
    df = pd.read_sql(query, source_conn)
    print(f"[SOURCE] 讀取 {len(df)} 筆資料")
    
    return df


# ============================================
# 資料寫入（目標）
# ============================================

def write_to_target(target_conn: pyodbc.Connection, df: pd.DataFrame, database: str, table_name: str):
    """
    將資料寫入新 MSSQL（Docker Sandbox）
    
    Args:
        target_conn: 新 MSSQL 連線（連到 master）
        df: 要寫入的 DataFrame
        database: 目標資料庫名稱
        table_name: 目標資料表名稱
    """
    if df.empty:
        print(f"[TARGET] DataFrame 為空，跳過寫入")
        return
    
    cursor = target_conn.cursor()
    full_table = f"[{database}].[dbo].[{table_name}]"
    
    # 檢查 table 是否存在
    check_query = f"""
    SELECT COUNT(*) FROM [{database}].INFORMATION_SCHEMA.TABLES 
    WHERE TABLE_NAME = '{table_name}'
    """
    cursor.execute(check_query)
    table_exists = cursor.fetchone()[0] > 0
    
    if not table_exists:
        print(f"[TARGET] Table {full_table} 不存在，建立中...")
        create_table_from_df(cursor, df, database, table_name)
    else:
        # 清空現有資料
        print(f"[TARGET] 清空 {full_table} 現有資料...")
        cursor.execute(f"TRUNCATE TABLE {full_table}")
    
    # INSERT 資料
    insert_data(cursor, df, database, table_name)
    
    target_conn.commit()
    print(f"[TARGET] 成功寫入 {len(df)} 筆資料到 {full_table}")


def create_table_from_df(cursor, df: pd.DataFrame, database: str, table_name: str):
    """
    根據 DataFrame 建立 table（簡單型別推論）
    """
    columns = []
    for col in df.columns:
        dtype = df[col].dtype
        if dtype == 'int64':
            sql_type = 'BIGINT'
        elif dtype == 'float64':
            sql_type = 'FLOAT'
        elif dtype == 'datetime64[ns]':
            sql_type = 'DATETIME2'
        else:
            # 預設使用 NVARCHAR(MAX)
            sql_type = 'NVARCHAR(MAX)'
        columns.append(f"[{col}] {sql_type} NULL")
    
    full_table = f"[{database}].[dbo].[{table_name}]"
    create_sql = f"CREATE TABLE {full_table} ({', '.join(columns)})"
    print(f"[TARGET] 執行: {create_sql[:100]}...")
    cursor.execute(create_sql)


def insert_data(cursor, df: pd.DataFrame, database: str, table_name: str):
    """
    將 DataFrame 資料 INSERT 到 table
    """
    columns = ', '.join([f'[{col}]' for col in df.columns])
    placeholders = ', '.join(['?' for _ in df.columns])
    full_table = f"[{database}].[dbo].[{table_name}]"
    insert_sql = f"INSERT INTO {full_table} ({columns}) VALUES ({placeholders})"
    
    success_count = 0
    fail_count = 0
    
    # 逐筆插入（簡單實作）
    for idx, row in df.iterrows():
        values = [None if pd.isna(v) else v for v in row.values]
        try:
            cursor.execute(insert_sql, values)
            success_count += 1
            print(f"[TARGET] 插入第 {idx} 筆成功")
        except Exception as e:
            fail_count += 1
            print(f"[TARGET] 插入第 {idx} 筆失敗: {e}")
            # 印出第一筆失敗的詳細資料
            if fail_count == 1:
                print(f"[DEBUG] SQL: {insert_sql[:200]}...")
                print(f"[DEBUG] Values types: {[type(v).__name__ for v in values]}")
            continue
    
    print(f"[TARGET] INSERT 完成 - 成功: {success_count}, 失敗: {fail_count}")


# ============================================
# 主程式
# ============================================

def copy_table(source_db: str, target_db: str, table_name: str, limit: int = 1000):
    """
    複製單一資料表
    
    Args:
        source_db: 來源資料庫名稱
        target_db: 目標資料庫名稱
        table_name: 資料表名稱
        limit: 讀取筆數上限
    """
    print(f"\n{'='*60}")
    print(f"複製 {source_db}.{table_name} -> {target_db}.{table_name}")
    print(f"{'='*60}")
    
    # 建立連線
    source_conn = get_source_connection(source_db)  # ⚠️ 只讀
    target_conn = get_target_connection()  # 連到 master
    
    try:
        # Step 1: 從舊 MSSQL 讀取（只讀）
        df = read_from_source(source_conn, table_name, limit)
        
        # Step 2: 寫入新 MSSQL
        write_to_target(target_conn, df, target_db, table_name)
        
    finally:
        source_conn.close()
        target_conn.close()


def main():
    """
    主程式：複製所有目標資料表
    """
    # APP_SRV_BPM 資料表
    bpm_tables = [
        "ACT_HI_PROCINST",
        "ACT_HI_TASKINST",
        "ACT_HI_IDENTITYLINK",
        "ACT_HI_VARINST",
        "ACT_RE_PROCDEF"
    ]
    
    # APP_SRV_COMMON 資料表
    common_tables = [
        "FlowableTaskStats",
        "HR_Employee",
        "ProcessRoleUserMapping",
        "ProcessRoleGroup",
        "ProcessRoleGroupMapping",
        "EmpNodeRoleMapping",
        "EmpOrgInfoMapping",
        "EmpUserGroupMapping",
        "UserGroup",
        "DMPFunctionConfig",
        "DMPFunctionClientMapping"
    ]
    
    print("開始複製資料...")
    print(f"來源: {SOURCE_SERVER}:{SOURCE_PORT}")
    print(f"目標: {TARGET_SERVER}:{TARGET_PORT}")
    
    # 複製 BPM 資料表
    for table in bpm_tables:
        try:
            copy_table("APP_SRV_BPM", "APP_SRV_BPM", table, limit=10)
        except Exception as e:
            print(f"[ERROR] 複製 {table} 失敗: {e}")
    
    # 複製 COMMON 資料表
    for table in common_tables:
        try:
            copy_table("APP_SRV_COMMON", "APP_SRV_COMMON", table, limit=10)
        except Exception as e:
            print(f"[ERROR] 複製 {table} 失敗: {e}")
    
    print("\n複製完成！")


if __name__ == "__main__":
    main()
