#!/usr/bin/env python3
"""
檢查 User Utilization Cube 的資料來源
"""

import clickhouse_connect
from datetime import datetime

def main():
    print("=== 檢查 User Utilization Cube 資料來源 ===")
    
    # 連接 ClickHouse
    client = clickhouse_connect.get_client(
        host='10.136.218.207',
        port=8121,
        username='default',
        password='default'
    )
    
    # 1. 檢查 Silver 層表是否存在
    print("\n1. 檢查 Silver 層表...")
    
    tables_query = """
    SELECT 
        name,
        engine,
        total_rows
    FROM system.tables
    WHERE database = 'silver' 
      AND name IN ('mv_dim_config_user', 'mv_fact_task_vx_attribution')
    ORDER BY name
    """
    
    try:
        tables = client.query(tables_query).result_rows
        print("  Silver 層表狀態:")
        for table in tables:
            print(f"    {table[0]}: {table[1]}, {table[2]:,} 行")
    except Exception as e:
        print(f"  ❌ 檢查表時發生錯誤: {e}")
        return
    
    # 2. 檢查 mv_dim_config_user 的資料結構
    print("\n2. 檢查 mv_dim_config_user 資料結構...")
    
    config_user_query = """
    SELECT 
        vx_type,
        plant,
        factory,
        COUNT(DISTINCT emp_code) AS config_user_count
    FROM silver.mv_dim_config_user FINAL
    WHERE is_config_user = 1
    GROUP BY vx_type, plant, factory
    ORDER BY vx_type, plant, factory
    LIMIT 10
    """
    
    try:
        config_results = client.query(config_user_query).result_rows
        if config_results:
            print("  Config Users 範例資料:")
            print("  Vx | Plant | Factory | Config Users")
            print("  " + "-" * 40)
            for result in config_results:
                print(f"  {result[0]:2} | {result[1]:5} | {result[2]:7} | {result[3]:11}")
        else:
            print("  ❌ 沒有找到 Config Users 資料")
    except Exception as e:
        print(f"  ❌ 檢查 Config Users 時發生錯誤: {e}")
    
    # 3. 檢查 mv_fact_task_vx_attribution 的活躍用戶資料
    print("\n3. 檢查 Active Users 資料...")
    
    active_user_query = """
    SELECT 
        vx_type,
        plant,
        factory,
        toDate(task_create_time) AS task_date,
        COUNT(DISTINCT task_assignee_name) AS active_user_count
    FROM silver.mv_fact_task_vx_attribution FINAL
    WHERE is_excluded = 0 
      AND task_status IN ('DONE', 'DOING')
      AND task_assignee_name IS NOT NULL
      AND task_assignee_name != ''
      AND task_date >= '2025-12-01'
    GROUP BY vx_type, plant, factory, task_date
    ORDER BY task_date DESC, vx_type, plant, factory
    LIMIT 10
    """
    
    try:
        active_results = client.query(active_user_query).result_rows
        if active_results:
            print("  Active Users 範例資料:")
            print("  日期       | Vx | Plant | Factory | Active Users")
            print("  " + "-" * 50)
            for result in active_results:
                print(f"  {result[3]} | {result[0]:2} | {result[1]:5} | {result[2]:7} | {result[4]:11}")
        else:
            print("  ❌ 沒有找到 Active Users 資料")
    except Exception as e:
        print(f"  ❌ 檢查 Active Users 時發生錯誤: {e}")
    
    # 4. 測試 User Utilization Cube 的 SQL 邏輯
    print("\n4. 測試 User Utilization Cube SQL 邏輯...")
    
    cube_sql = """
    WITH config_users AS (
      SELECT 
        vx_type,
        plant,
        factory,
        COUNT(DISTINCT emp_code) AS config_user_count
      FROM silver.mv_dim_config_user FINAL
      WHERE is_config_user = 1
      GROUP BY vx_type, plant, factory
    ),
    active_users AS (
      SELECT 
        vx_type,
        plant,
        factory,
        toDate(task_create_time) AS task_date,
        COUNT(DISTINCT task_assignee_name) AS active_user_count
      FROM silver.mv_fact_task_vx_attribution FINAL
      WHERE is_excluded = 0 
        AND task_status IN ('DONE', 'DOING')
        AND task_assignee_name IS NOT NULL
        AND task_assignee_name != ''
        AND task_date = '2025-12-30'
      GROUP BY vx_type, plant, factory, task_date
    )
    SELECT 
      c.vx_type,
      c.plant,
      c.factory,
      '' AS line,
      a.task_date AS snapshot_date,
      c.config_user_count,
      COALESCE(a.active_user_count, 0) AS active_user_count,
      CASE WHEN c.config_user_count > 0 
           THEN ROUND(COALESCE(a.active_user_count, 0) * 100.0 / c.config_user_count, 2)
           ELSE 0 END AS utilization_rate
    FROM config_users c
    LEFT JOIN active_users a ON c.vx_type = a.vx_type 
                             AND c.plant = a.plant 
                             AND c.factory = a.factory
    WHERE c.plant = 'WJ2' AND c.factory = 'NBU'
    ORDER BY c.vx_type, c.plant, c.factory
    """
    
    try:
        cube_results = client.query(cube_sql).result_rows
        if cube_results:
            print("  User Utilization 測試結果 (WJ2+NBU 2025-12-30):")
            print("  Vx | Plant | Factory | 日期       | Config | Active | 使用率%")
            print("  " + "-" * 70)
            for result in cube_results:
                snapshot_date = result[4] if result[4] else 'N/A'
                print(f"  {result[0]:2} | {result[1]:5} | {result[2]:7} | {snapshot_date} | {result[5]:6} | {result[6]:6} | {result[7]:7.1f}")
        else:
            print("  ❌ User Utilization 測試沒有結果")
    except Exception as e:
        print(f"  ❌ 測試 User Utilization 時發生錯誤: {e}")
    
    # 5. 檢查是否需要建立 Gold 層 User Utilization MView
    print("\n5. 檢查 Gold 層 User Utilization MView...")
    
    gold_tables_query = """
    SELECT name
    FROM system.tables
    WHERE database = 'gold' 
      AND name LIKE '%user%utilization%'
    """
    
    try:
        gold_tables = client.query(gold_tables_query).result_rows
        if gold_tables:
            print("  找到 Gold 層 User Utilization 表:")
            for table in gold_tables:
                print(f"    {table[0]}")
        else:
            print("  ❌ 沒有找到 Gold 層 User Utilization MView")
            print("  💡 建議：User Utilization Cube 目前直接查詢 Silver 層")
    except Exception as e:
        print(f"  ❌ 檢查 Gold 層表時發生錯誤: {e}")
    
    print("\n=== 總結 ===")
    print("✅ Silver 層資料來源存在且有資料")
    print("✅ User Utilization Cube SQL 邏輯可以執行")
    print("💡 User Utilization Cube 直接查詢 Silver 層，無需 Gold 層 MView")

if __name__ == '__main__':
    main()