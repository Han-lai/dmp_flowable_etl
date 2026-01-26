#!/usr/bin/env python3
"""
檢查 Gold 層資料完整性
比對 Silver 層與 Gold 層的日期範圍，確認是否有遺漏
"""
import clickhouse_connect
from datetime import datetime, timedelta

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
        print("-" * 60)
        
        result = client.query(sql)
        return result.result_rows
        
    except Exception as e:
        print(f"❌ ClickHouse 查詢錯誤: {e}")
        return None

def main():
    """檢查 Gold 層資料完整性"""
    print("=" * 80)
    print("Gold 層資料完整性檢查")
    print("=" * 80)
    
    # 1. 檢查 Silver 層的完整日期範圍
    sql_silver_range = """
    SELECT 
        MIN(toDate(task_create_time)) as min_date,
        MAX(toDate(task_create_time)) as max_date,
        COUNT(DISTINCT toDate(task_create_time)) as date_count
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE is_excluded = 0
    """
    
    results_silver_range = query_clickhouse(sql_silver_range, "Silver 層整體日期範圍")
    if results_silver_range:
        min_date, max_date, date_count = results_silver_range[0]
        print(f"Silver 層日期範圍: {min_date} ~ {max_date}")
        print(f"Silver 層日期數量: {date_count} 天")
        
        # 計算預期天數
        from datetime import datetime
        start = datetime.strptime(str(min_date), '%Y-%m-%d')
        end = datetime.strptime(str(max_date), '%Y-%m-%d')
        expected_days = (end - start).days + 1
        print(f"預期天數: {expected_days} 天")
        print(f"缺失天數: {expected_days - date_count} 天")
    
    # 2. 檢查 Gold 層的日期範圍
    sql_gold_range = """
    SELECT 
        MIN(snapshot_date) as min_date,
        MAX(snapshot_date) as max_date,
        COUNT(DISTINCT snapshot_date) as date_count
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
    """
    
    results_gold_range = query_clickhouse(sql_gold_range, "Gold 層整體日期範圍")
    if results_gold_range:
        min_date, max_date, date_count = results_gold_range[0]
        print(f"Gold 層日期範圍: {min_date} ~ {max_date}")
        print(f"Gold 層日期數量: {date_count} 天")
    
    # 3. 檢查特定條件下的 Silver vs Gold 對比
    sql_silver_specific = """
    SELECT 
        toDate(task_create_time) as create_date,
        COUNT(*) as task_count
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE vx_type = 'V1'
      AND plant = 'WJ2'
      AND factory = 'NBU'
      AND line = 'E5'
      AND is_excluded = 0
      AND toDate(task_create_time) >= '2025-12-01'
    GROUP BY toDate(task_create_time)
    ORDER BY create_date
    """
    
    results_silver_specific = query_clickhouse(sql_silver_specific, "Silver 層特定條件 (12月後)")
    silver_dates = {}
    if results_silver_specific:
        print("Silver 層 12月後資料:")
        for row in results_silver_specific:
            date, count = row
            silver_dates[str(date)] = count
            print(f"  {date}: {count} 筆")
    
    # 4. 檢查 Gold 層對應資料
    sql_gold_specific = """
    SELECT 
        snapshot_date,
        time_period_type,
        total_task_qty
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
    WHERE vx_type = 'V1'
      AND plant = 'WJ2'
      AND factory = 'NBU'
      AND line = 'E5'
      AND snapshot_date >= '2025-12-01'
    ORDER BY snapshot_date, time_period_type
    """
    
    results_gold_specific = query_clickhouse(sql_gold_specific, "Gold 層特定條件 (12月後)")
    gold_dates = {}
    if results_gold_specific:
        print("Gold 層 12月後資料:")
        for row in results_gold_specific:
            date, period, count = row
            if period == 'day':  # 只看 day 粒度
                gold_dates[str(date)] = count
                print(f"  {date} ({period}): {count} 筆")
    
    # 5. 比對 Silver vs Gold 缺失日期
    print("\n📊 Silver vs Gold 日期比對")
    print("-" * 60)
    
    missing_in_gold = []
    mismatched_counts = []
    
    for date, silver_count in silver_dates.items():
        if date not in gold_dates:
            missing_in_gold.append(date)
            print(f"❌ {date}: Silver有{silver_count}筆，Gold缺失")
        else:
            gold_count = gold_dates[date]
            if silver_count != gold_count:
                mismatched_counts.append((date, silver_count, gold_count))
                print(f"⚠️ {date}: Silver={silver_count}筆，Gold={gold_count}筆")
            else:
                print(f"✅ {date}: Silver={silver_count}筆，Gold={gold_count}筆")
    
    # 6. 檢查 Gold 層是否有 Silver 層沒有的日期
    extra_in_gold = []
    for date in gold_dates:
        if date not in silver_dates:
            extra_in_gold.append(date)
    
    # 7. 檢查 Gold 層建立邏輯
    sql_gold_logic = """
    SELECT 
        snapshot_date,
        time_period_type,
        COUNT(*) as record_count,
        SUM(total_task_qty) as total_tasks,
        MIN(total_task_qty) as min_tasks,
        MAX(total_task_qty) as max_tasks
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
    WHERE snapshot_date >= '2025-12-01'
    GROUP BY snapshot_date, time_period_type
    ORDER BY snapshot_date DESC, time_period_type
    LIMIT 20
    """
    
    results_gold_logic = query_clickhouse(sql_gold_logic, "Gold 層建立邏輯檢查 (最近20筆)")
    if results_gold_logic:
        print("Gold 層記錄分布:")
        for row in results_gold_logic:
            date, period, count, total, min_val, max_val = row
            print(f"  {date} ({period}): {count}筆記錄, 總任務={total}, 範圍={min_val}~{max_val}")
    
    # 8. 檢查是否存在 MATERIALIZED VIEW
    sql_mview = """
    SELECT 
        name,
        engine,
        total_rows,
        total_bytes
    FROM system.tables 
    WHERE database = 'gold'
      AND (engine LIKE '%MaterializedView%' OR name LIKE '%SNAPSHOT%')
    """
    
    results_mview = query_clickhouse(sql_mview, "Gold 層表和 MView 檢查")
    if results_mview:
        print("Gold 層相關表:")
        for row in results_mview:
            name, engine, rows, bytes_size = row
            print(f"  {name}: {engine}, {rows}行, {bytes_size}字節")
    
    # 9. 總結報告
    print("\n" + "=" * 80)
    print("Gold 層資料完整性報告")
    print("=" * 80)
    
    print(f"📊 統計摘要:")
    if results_silver_range and results_gold_range:
        silver_min, silver_max, silver_count = results_silver_range[0]
        gold_min, gold_max, gold_count = results_gold_range[0]
        
        print(f"  Silver 層: {silver_min} ~ {silver_max} ({silver_count} 天)")
        print(f"  Gold 層:   {gold_min} ~ {gold_max} ({gold_count} 天)")
        
        if gold_count < silver_count:
            print(f"  ❌ Gold 層缺少 {silver_count - gold_count} 天的資料")
        else:
            print(f"  ✅ Gold 層日期數量正常")
    
    print(f"\n🎯 特定條件 (V1+WJ2+NBU+E5) 分析:")
    print(f"  Silver 層日期數: {len(silver_dates)}")
    print(f"  Gold 層日期數:   {len(gold_dates)}")
    print(f"  Gold 層缺失日期: {len(missing_in_gold)}")
    print(f"  數量不匹配日期: {len(mismatched_counts)}")
    
    if missing_in_gold:
        print(f"\n❌ Gold 層缺失的日期:")
        for date in missing_in_gold:
            print(f"    {date}")
    
    if mismatched_counts:
        print(f"\n⚠️ 數量不匹配的日期:")
        for date, silver_count, gold_count in mismatched_counts:
            print(f"    {date}: Silver={silver_count}, Gold={gold_count}")
    
    print(f"\n💡 建議:")
    if missing_in_gold:
        print("  1. 檢查 Gold 層快照建立的 batch job")
        print("  2. 確認 MATERIALIZED VIEW 是否需要手動刷新")
        print("  3. 檢查快照建立邏輯的時間範圍設定")
    else:
        print("  Gold 層資料完整，問題可能在其他層級")

if __name__ == "__main__":
    main()