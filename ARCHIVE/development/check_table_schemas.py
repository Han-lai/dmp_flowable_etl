#!/usr/bin/env python3
"""
檢查各層表的欄位結構
"""

import clickhouse_connect

def main():
    print("=== 檢查表結構 ===")
    
    # 連接 ClickHouse
    client = clickhouse_connect.get_client(
        host='REDACTED_IP',
        port=8121,
        username='default',
        password='default'
    )
    
    # 檢查 Bronze 層表結構
    print("\n1. Bronze 層表結構:")
    
    bronze_schema_query = """
    SELECT name, type
    FROM system.columns
    WHERE database = 'bronze' 
      AND table = 'bmp_act_hi_taskinst'
    ORDER BY position
    """
    
    try:
        bronze_columns = client.query(bronze_schema_query).result_rows
        if bronze_columns:
            print("  bronze.bmp_act_hi_taskinst 欄位:")
            for col in bronze_columns:
                print(f"    {col[0]}: {col[1]}")
        else:
            print("  ❌ 找不到 bronze.bmp_act_hi_taskinst 表")
    except Exception as e:
        print(f"  ❌ 查詢錯誤: {e}")
    
    # 檢查正確的表名
    print("\n2. 檢查 Bronze 層所有表:")
    
    bronze_tables_query = """
    SELECT name, total_rows
    FROM system.tables
    WHERE database = 'bronze' 
      AND name LIKE '%taskinst%'
    ORDER BY name
    """
    
    try:
        bronze_tables = client.query(bronze_tables_query).result_rows
        for table in bronze_tables:
            print(f"  {table[0]}: {table[1]:,} 行")
            
            # 檢查表結構
            schema_query = f"""
            SELECT name, type
            FROM system.columns
            WHERE database = 'bronze' 
              AND table = '{table[0]}'
            ORDER BY position
            LIMIT 10
            """
            
            columns = client.query(schema_query).result_rows
            print(f"    前 10 個欄位:")
            for col in columns:
                print(f"      {col[0]}: {col[1]}")
            print()
    except Exception as e:
        print(f"  ❌ 查詢錯誤: {e}")
    
    # 檢查 Silver 層 Fact 表結構
    print("\n3. Silver 層 Fact 表結構:")
    
    silver_schema_query = """
    SELECT name, type
    FROM system.columns
    WHERE database = 'silver' 
      AND table = 'mv_fact_task_vx_attribution'
    ORDER BY position
    LIMIT 15
    """
    
    try:
        silver_columns = client.query(silver_schema_query).result_rows
        if silver_columns:
            print("  silver.mv_fact_task_vx_attribution 前 15 個欄位:")
            for col in silver_columns:
                print(f"    {col[0]}: {col[1]}")
        else:
            print("  ❌ 找不到 silver.mv_fact_task_vx_attribution 表")
    except Exception as e:
        print(f"  ❌ 查詢錯誤: {e}")

if __name__ == '__main__':
    main()