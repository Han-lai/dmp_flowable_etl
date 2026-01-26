#!/usr/bin/env python3
"""
檢查快取和資料更新狀態
確認是否因為快取或 mview 未更新導致只看到舊資料
"""
import clickhouse_connect
import requests
import json

CUBE_API_BASE = "http://REDACTED_IP:4002/cubejs-api/v1"
CUBE_API_KEY = "REDACTED_SECRET"

CH_HOST = "REDACTED_IP"
CH_PORT = 8121
CH_USER = "default"
CH_PASSWORD = ""

def query_clickhouse(sql, description=""):
    """查詢 ClickHouse"""
    try:
        client = clickhouse_connect.get_client(
            host=CH_HOST,
            port=CH_PORT,
            username=CH_USER,
            password=CH_PASSWORD
        )
        
        print(f"\n🔍 {description}")
        print("-" * 60)
        
        result = client.query(sql)
        return result.result_rows
        
    except Exception as e:
        print(f"❌ ClickHouse 查詢錯誤: {e}")
        return None

def check_cube_cache():
    """檢查 Cube.js 快取狀態"""
    try:
        # 檢查 meta 資訊
        response = requests.get(
            f"{CUBE_API_BASE}/meta",
            headers={'Authorization': CUBE_API_KEY},
            timeout=10
        )
        
        if response.status_code == 200:
            meta = response.json()
            cubes = meta.get('cubes', [])
            
            print("\n🔍 Cube.js Meta 資訊")
            print("-" * 60)
            print(f"可用 Cubes: {len(cubes)}")
            
            for cube in cubes:
                if 'DailyMetricsSnapshot' in cube.get('name', ''):
                    print(f"找到 DailyMetricsSnapshot: {cube.get('name')}")
                    
        return True
        
    except Exception as e:
        print(f"❌ Cube.js Meta 查詢錯誤: {e}")
        return False

def main():
    """檢查快取和更新狀態"""
    print("=" * 80)
    print("快取和資料更新狀態檢查")
    print("=" * 80)
    
    # 1. 檢查 ClickHouse 表的最後更新時間
    sql_table_info = """
    SELECT 
        table,
        engine,
        total_rows,
        total_bytes
    FROM system.tables 
    WHERE database = 'gold' 
      AND name = 'DAILY_L5_TASK_COMPLETION_SNAPSHOT'
    """
    
    results_table = query_clickhouse(sql_table_info, "Gold 層表基本資訊")
    if results_table:
        for row in results_table:
            table, engine, rows, bytes_size = row
            print(f"表: {table}, 引擎: {engine}, 行數: {rows}, 大小: {bytes_size}")
    
    # 2. 檢查 Gold 層表的資料範圍
    sql_data_range = """
    SELECT 
        MIN(snapshot_date) as min_date,
        MAX(snapshot_date) as max_date,
        COUNT(DISTINCT snapshot_date) as date_count,
        COUNT(*) as total_records
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
    """
    
    results_range = query_clickhouse(sql_data_range, "Gold 層資料範圍")
    if results_range:
        for row in results_range:
            min_date, max_date, date_count, total = row
            print(f"日期範圍: {min_date} ~ {max_date}")
            print(f"日期數量: {date_count}, 總記錄: {total}")
    
    # 3. 檢查特定條件下的資料分布
    sql_condition_check = """
    SELECT 
        snapshot_date,
        time_period_type,
        COUNT(*) as record_count,
        SUM(total_task_qty) as total_tasks
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
    WHERE vx_type = 'V1'
      AND plant = 'WJ2'
      AND factory = 'NBU'
      AND line = 'E5'
    GROUP BY snapshot_date, time_period_type
    ORDER BY snapshot_date DESC, time_period_type
    LIMIT 10
    """
    
    results_condition = query_clickhouse(sql_condition_check, "特定條件資料分布 (最近10筆)")
    if results_condition:
        print("最近的資料:")
        for row in results_condition:
            date, period, count, total = row
            print(f"  {date} ({period}): {count}筆記錄, 總任務={total}")
    
    # 4. 檢查是否有 MATERIALIZED VIEW
    sql_mview_check = """
    SELECT 
        name,
        engine,
        create_table_query
    FROM system.tables 
    WHERE database IN ('silver', 'gold')
      AND engine LIKE '%MaterializedView%'
    """
    
    results_mview = query_clickhouse(sql_mview_check, "MATERIALIZED VIEW 檢查")
    if results_mview:
        print("發現 Materialized Views:")
        for row in results_mview:
            name, engine, query = row
            print(f"  {name} ({engine})")
    else:
        print("未發現 Materialized Views")
    
    # 5. 檢查 Cube.js 快取狀態
    check_cube_cache()
    
    # 6. 檢查 Silver 層最新資料
    sql_silver_latest = """
    SELECT 
        toDate(task_create_time) as create_date,
        COUNT(*) as task_count
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE vx_type = 'V1'
      AND plant = 'WJ2'
      AND factory = 'NBU'
      AND line = 'E5'
      AND is_excluded = 0
      AND task_create_time >= '2025-12-25'
    GROUP BY toDate(task_create_time)
    ORDER BY create_date DESC
    """
    
    results_silver_latest = query_clickhouse(sql_silver_latest, "Silver 層最新資料 (12/25後)")
    if results_silver_latest:
        print("Silver 層最新資料:")
        for row in results_silver_latest:
            date, count = row
            print(f"  {date}: {count} 筆")
    
    print("\n" + "=" * 80)
    print("檢查結果分析")
    print("=" * 80)
    print("🎯 關鍵檢查點:")
    print("1. Gold 層表是否有最新資料")
    print("2. Silver 層是否有 12/31 的資料")
    print("3. 是否存在 Materialized View 更新延遲")
    print("4. Cube.js 是否有快取問題")

if __name__ == "__main__":
    main()