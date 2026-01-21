#!/usr/bin/env python3
"""
分析 2025-12-28 的 done task 數量為什麼高達三千多筆
檢查是否為正常業務狀況還是資料異常
"""
import clickhouse_connect

def analyze_1228_done_tasks():
    client = clickhouse_connect.get_client(
        host="10.136.218.207",
        port=8121,
        username="default",
        password="default"
    )
    
    print("=" * 80)
    print("2025-12-28 Done Task 數量分析")
    print("=" * 80)
    
    # 1. 檢查 2025-12-28 總體 done task 數量
    print("\n1. 2025-12-28 總體 done task 統計...")
    
    total_sql = """
    SELECT 
        time_period_type,
        SUM(done_qty) as total_done_tasks,
        COUNT(*) as record_count,
        AVG(done_qty) as avg_done_per_record,
        MAX(done_qty) as max_done_per_record
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE snapshot_date = '2025-12-28'
    GROUP BY time_period_type
    ORDER BY total_done_tasks DESC
    """
    
    result = client.query(total_sql)
    if result.result_rows:
        print("按時間維度統計:")
        print(f"{'Period':<8} {'Total Done':<12} {'Records':<8} {'Avg/Record':<12} {'Max/Record':<12}")
        print("-" * 65)
        
        total_done = 0
        for row in result.result_rows:
            period_type, total, count, avg, max_val = row
            total_done += total
            print(f"{period_type:<8} {total:<12} {count:<8} {avg:<12.1f} {max_val:<12}")
        
        print(f"\n總 Done Tasks: {total_done:,} 筆")
    
    # 2. 對比其他日期的 done task 數量
    print(f"\n2. 對比其他日期的 done task 數量...")
    
    comparison_sql = """
    SELECT 
        snapshot_date,
        SUM(done_qty) as total_done_tasks,
        COUNT(*) as record_count
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE snapshot_date >= '2025-12-25' AND snapshot_date <= '2025-12-31'
    GROUP BY snapshot_date
    ORDER BY snapshot_date
    """
    
    result = client.query(comparison_sql)
    if result.result_rows:
        print("近期日期對比:")
        print(f"{'Date':<12} {'Total Done':<12} {'Records':<8}")
        print("-" * 35)
        
        for row in result.result_rows:
            date, total, count = row
            status = "⚠️" if total > 100000 else "✅"
            print(f"{date:<12} {total:<12} {count:<8} {status}")
    
    # 3. 檢查 2025-12-28 最大貢獻者
    print(f"\n3. 2025-12-28 最大 done task 貢獻者...")
    
    top_contributors_sql = """
    SELECT 
        vx_type,
        plant,
        factory,
        line,
        time_period_type,
        done_qty,
        total_task_qty,
        done_pct
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE snapshot_date = '2025-12-28'
      AND done_qty > 1000
    ORDER BY done_qty DESC
    LIMIT 20
    """
    
    result = client.query(top_contributors_sql)
    if result.result_rows:
        print("Top 20 高 done task 記錄:")
        print(f"{'VX':<4} {'Plant':<6} {'Factory':<8} {'Line':<8} {'Period':<8} {'Done':<8} {'Total':<8} {'%':<6}")
        print("-" * 70)
        
        for row in result.result_rows:
            vx, plant, factory, line, period, done, total, pct = row
            print(f"{vx:<4} {plant:<6} {factory:<8} {line:<8} {period:<8} {done:<8} {total:<8} {pct:<6.1f}")
    
    # 4. 檢查月度資料是否異常
    print(f"\n4. 檢查月度資料...")
    
    monthly_sql = """
    SELECT 
        vx_type,
        plant,
        factory,
        line,
        time_period_value,
        done_qty,
        total_task_qty,
        done_pct
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE snapshot_date = '2025-12-28'
      AND time_period_type = 'month'
      AND done_qty > 5000
    ORDER BY done_qty DESC
    """
    
    result = client.query(monthly_sql)
    if result.result_rows:
        print("月度高 done task 記錄:")
        print(f"{'VX':<4} {'Plant':<6} {'Factory':<8} {'Line':<8} {'Month':<8} {'Done':<8} {'Total':<8} {'%':<6}")
        print("-" * 70)
        
        for row in result.result_rows:
            vx, plant, factory, line, month, done, total, pct = row
            print(f"{vx:<4} {plant:<6} {factory:<8} {line:<8} {month:<8} {done:<8} {total:<8} {pct:<6.1f}")
    
    # 5. 檢查是否為累計效應
    print(f"\n5. 檢查累計效應...")
    
    cumulative_sql = """
    SELECT 
        time_period_type,
        time_period_value,
        COUNT(*) as line_count,
        SUM(done_qty) as total_done,
        AVG(done_qty) as avg_done
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE snapshot_date = '2025-12-28'
      AND time_period_type = 'month'
    GROUP BY time_period_type, time_period_value
    ORDER BY total_done DESC
    """
    
    result = client.query(cumulative_sql)
    if result.result_rows:
        print("月度累計分析:")
        print(f"{'Period':<8} {'Value':<12} {'Lines':<8} {'Total Done':<12} {'Avg Done':<12}")
        print("-" * 60)
        
        for row in result.result_rows:
            period_type, value, line_count, total_done, avg_done = row
            print(f"{period_type:<8} {value:<12} {line_count:<8} {total_done:<12} {avg_done:<12.1f}")
    
    # 6. 檢查 Silver 層對應資料
    print(f"\n6. 檢查 Silver 層對應資料...")
    
    silver_sql = """
    SELECT 
        COUNT(*) as total_tasks,
        SUM(CASE WHEN task_status = 'COMPLETED' THEN 1 ELSE 0 END) as completed_tasks,
        COUNT(DISTINCT CONCAT(vx_type, plant, factory, line)) as unique_combinations
    FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
    WHERE DATE(task_end_time) = '2025-12-28'
      OR (task_end_time IS NULL AND DATE(task_create_time) <= '2025-12-28')
    """
    
    result = client.query(silver_sql)
    if result.result_rows:
        print("Silver 層 2025-12-28 資料:")
        print(f"{'Total Tasks':<15} {'Completed':<12} {'Unique Combos':<15}")
        print("-" * 45)
        
        for row in result.result_rows:
            total, completed, unique = row
            print(f"{total:<15} {completed:<12} {unique:<15}")
    
    print(f"\n" + "=" * 80)
    print("分析結論")
    print("=" * 80)
    
    print("🔍 2025-12-28 Done Task 高數量原因分析:")
    print("1. 檢查是否為月度累計效應")
    print("2. 檢查是否為特定產線大量完成任務")
    print("3. 檢查是否為資料聚合邏輯問題")
    print("4. 對比 Silver 層原始資料確認正確性")

if __name__ == "__main__":
    analyze_1228_done_tasks()