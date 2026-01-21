#!/usr/bin/env python3
"""
分析 2025-12-28 的詳細資料分布
確認是否有不同維度組合導致的多筆記錄
"""
import clickhouse_connect

def analyze_1228_data():
    client = clickhouse_connect.get_client(
        host="10.136.218.207",
        port=8121,
        username="default",
        password="default"
    )
    
    print("=" * 80)
    print("2025-12-28 資料詳細分析")
    print("=" * 80)
    
    # 1. 檢查 2025-12-28 所有記錄的詳細資訊
    print("\n1. 2025-12-28 所有記錄詳細資訊...")
    
    detail_sql = """
    SELECT 
        vx_type,
        plant,
        factory,
        line,
        time_period_type,
        total_task_qty,
        done_qty,
        done_pct,
        _snapshot_time
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE snapshot_date = '2025-12-28'
    ORDER BY vx_type, plant, factory, line, time_period_type
    """
    
    result = client.query(detail_sql)
    if result.result_rows:
        print(f"總共 {len(result.result_rows)} 筆記錄:")
        print(f"{'VX':<4} {'Plant':<6} {'Factory':<8} {'Line':<6} {'Period':<8} {'Total':<8} {'Done':<6} {'%':<6} {'Time':<20}")
        print("-" * 80)
        
        for row in result.result_rows:
            vx, plant, factory, line, period, total, done, pct, time = row
            print(f"{vx:<4} {plant:<6} {factory:<8} {line:<6} {period:<8} {total:<8} {done:<6} {pct:<6} {str(time)[:19]}")
    
    # 2. 按維度組合統計
    print(f"\n2. 按維度組合統計...")
    
    dimension_sql = """
    SELECT 
        vx_type,
        plant,
        factory,
        line,
        COUNT(*) as record_count,
        arrayStringConcat(groupArray(time_period_type), ',') as period_types
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE snapshot_date = '2025-12-28'
    GROUP BY vx_type, plant, factory, line
    ORDER BY record_count DESC, vx_type, plant, factory, line
    """
    
    result = client.query(dimension_sql)
    if result.result_rows:
        print("維度組合統計:")
        print(f"{'VX':<4} {'Plant':<6} {'Factory':<8} {'Line':<6} {'Count':<6} {'Periods'}")
        print("-" * 60)
        
        for row in result.result_rows:
            vx, plant, factory, line, count, periods = row
            print(f"{vx:<4} {plant:<6} {factory:<8} {line:<6} {count:<6} {periods}")
    
    # 3. 檢查是否有不同的 time_period_type
    print(f"\n3. 檢查 time_period_type 分布...")
    
    period_sql = """
    SELECT 
        time_period_type,
        COUNT(*) as record_count,
        COUNT(DISTINCT CONCAT(vx_type, plant, factory, line)) as unique_combinations
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE snapshot_date = '2025-12-28'
    GROUP BY time_period_type
    ORDER BY record_count DESC
    """
    
    result = client.query(period_sql)
    if result.result_rows:
        print("時間週期類型分布:")
        print(f"{'Period Type':<12} {'Records':<8} {'Unique Combos':<15}")
        print("-" * 40)
        
        for row in result.result_rows:
            period_type, count, unique = row
            print(f"{period_type:<12} {count:<8} {unique:<15}")
    
    # 4. 檢查特定條件 (V1+WJ2+NBU+E5) 的詳細情況
    print(f"\n4. V1+WJ2+NBU+E5 詳細情況...")
    
    specific_sql = """
    SELECT 
        time_period_type,
        time_period_value,
        total_task_qty,
        todo_qty,
        doing_qty,
        done_qty,
        done_pct,
        _snapshot_time
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE snapshot_date = '2025-12-28'
      AND vx_type = 'V1' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
    ORDER BY time_period_type, _snapshot_time
    """
    
    result = client.query(specific_sql)
    if result.result_rows:
        print("V1+WJ2+NBU+E5 詳細記錄:")
        print(f"{'Period':<8} {'Value':<12} {'Total':<8} {'TODO':<6} {'DOING':<6} {'DONE':<6} {'%':<6} {'Time':<20}")
        print("-" * 80)
        
        for row in result.result_rows:
            period, value, total, todo, doing, done, pct, time = row
            print(f"{period:<8} {value:<12} {total:<8} {todo:<6} {doing:<6} {done:<6} {pct:<6} {str(time)[:19]}")
    
    # 5. 檢查是否來自不同來源
    print(f"\n5. 檢查資料來源...")
    
    source_sql = """
    SELECT 
        DATE(_snapshot_time) as snapshot_date_only,
        COUNT(*) as record_count,
        MIN(_snapshot_time) as earliest_time,
        MAX(_snapshot_time) as latest_time
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE snapshot_date = '2025-12-28'
    GROUP BY DATE(_snapshot_time)
    ORDER BY snapshot_date_only
    """
    
    result = client.query(source_sql)
    if result.result_rows:
        print("資料來源時間分析:")
        print(f"{'Date':<12} {'Records':<8} {'Earliest':<20} {'Latest':<20}")
        print("-" * 65)
        
        for row in result.result_rows:
            date, count, earliest, latest = row
            print(f"{date:<12} {count:<8} {str(earliest)[:19]:<20} {str(latest)[:19]:<20}")
    
    print(f"\n" + "=" * 80)
    print("分析結論")
    print("=" * 80)
    
    print("🔍 2025-12-28 資料狀況:")
    print("1. 檢查是否有多個 time_period_type (day/week/month)")
    print("2. 檢查是否有不同維度組合")
    print("3. 檢查是否來自不同時間的插入")

if __name__ == "__main__":
    analyze_1228_data()