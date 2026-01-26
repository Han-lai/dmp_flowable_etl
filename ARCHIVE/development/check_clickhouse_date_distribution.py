#!/usr/bin/env python3
"""
檢查 ClickHouse 來源表的日期分布
確認是否真的只有 12/28 的資料
"""
import clickhouse_connect

# ClickHouse 連接設定
CH_HOST = "10.136.218.207"
CH_PORT = 8121
CH_USER = "default"
CH_PASSWORD = "default"

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
        print("SQL:", sql)
        print("-" * 60)
        
        result = client.query(sql)
        return result.result_rows
        
    except Exception as e:
        print(f"❌ ClickHouse 查詢錯誤: {e}")
        return None

def main():
    """檢查日期分布"""
    print("=" * 80)
    print("ClickHouse 來源表日期分布檢查")
    print("條件: V1 + WJ2 + NBU + E5")
    print("=" * 80)
    
    # 1. 檢查 Gold 層快照表日期分布
    sql_gold = """
    SELECT 
        snapshot_date,
        time_period_type,
        total_task_qty,
        done_qty
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
    WHERE vx_type = 'V1'
      AND plant = 'WJ2'
      AND factory = 'NBU'
      AND line = 'E5'
    ORDER BY snapshot_date, time_period_type
    """
    
    results_gold = query_clickhouse(sql_gold, "Gold 層快照表")
    if results_gold:
        print(f"Gold 層共 {len(results_gold)} 筆資料:")
        for row in results_gold:
            date, period, total, done = row
            print(f"  {date} ({period}): 總數={total}, 完成={done}")
    
    # 2. 檢查 Silver 層事實表日期分布
    sql_silver = """
    SELECT 
        toDate(task_create_time) as create_date,
        COUNT(*) as task_count,
        SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END) as done_count
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE vx_type = 'V1'
      AND plant = 'WJ2'
      AND factory = 'NBU'
      AND line = 'E5'
      AND is_excluded = 0
    GROUP BY toDate(task_create_time)
    ORDER BY create_date
    """
    
    results_silver = query_clickhouse(sql_silver, "Silver 層事實表 (按 task_create_time)")
    if results_silver:
        print(f"Silver 層共 {len(results_silver)} 個日期:")
        for row in results_silver:
            date, total, done = row
            print(f"  {date}: 總數={total}, 完成={done}")
    
    # 3. 檢查是否有其他時間欄位的資料
    sql_other_dates = """
    SELECT 
        'task_create_time' as time_field,
        toDate(task_create_time) as date_value,
        COUNT(*) as count
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE vx_type = 'V1' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND is_excluded = 0
    GROUP BY toDate(task_create_time)
    
    UNION ALL
    
    SELECT 
        'task_end_time' as time_field,
        toDate(task_end_time) as date_value,
        COUNT(*) as count
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE vx_type = 'V1' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5' AND is_excluded = 0
      AND task_end_time IS NOT NULL
    GROUP BY toDate(task_end_time)
    
    ORDER BY time_field, date_value
    """
    
    results_other = query_clickhouse(sql_other_dates, "不同時間欄位的日期分布")
    if results_other:
        print("不同時間欄位的資料分布:")
        current_field = None
        for row in results_other:
            field, date, count = row
            if field != current_field:
                print(f"\n  📅 {field}:")
                current_field = field
            print(f"    {date}: {count} 筆")

if __name__ == "__main__":
    main()