#!/usr/bin/env python3
"""
檢查 Gold 層 2025-12-28 重複資料問題
分析重複原因並提供去重方案
"""
import clickhouse_connect

def check_duplicates():
    client = clickhouse_connect.get_client(
        host="REDACTED_IP",
        port=8121,
        username="default",
        password="default"
    )
    
    print("=" * 60)
    print("Gold 層 2025-12-28 重複資料檢查")
    print("=" * 60)
    
    # 1. 檢查 2025-12-28 的重複情況
    print("\n1. 檢查 2025-12-28 重複情況...")
    
    duplicate_check_sql = """
    SELECT 
        snapshot_date,
        vx_type,
        plant,
        factory,
        line,
        time_period_type,
        COUNT(*) as record_count,
        COUNT(DISTINCT _version) as version_count,
        MIN(_version) as min_version,
        MAX(_version) as max_version
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
    WHERE snapshot_date = '2025-12-28'
      AND vx_type = 'V1' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
    GROUP BY snapshot_date, vx_type, plant, factory, line, time_period_type
    ORDER BY record_count DESC
    """
    
    result = client.query(duplicate_check_sql)
    if result.result_rows:
        print("2025-12-28 重複情況:")
        print(f"{'Type':<8} {'Records':<8} {'Versions':<8} {'Min Ver':<15} {'Max Ver':<15}")
        print("-" * 70)
        for row in result.result_rows:
            date, vx, plant, factory, line, period_type, count, ver_count, min_ver, max_ver = row
            print(f"{period_type:<8} {count:<8} {ver_count:<8} {min_ver:<15} {max_ver:<15}")
    
    # 2. 檢查所有日期的記錄數分布
    print("\n2. 檢查所有日期記錄數分布...")
    
    all_dates_sql = """
    SELECT 
        snapshot_date,
        COUNT(*) as total_records,
        COUNT(DISTINCT CONCAT(vx_type, plant, factory, line, time_period_type)) as unique_combinations
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
    WHERE vx_type = 'V1' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
    GROUP BY snapshot_date
    ORDER BY snapshot_date
    """
    
    result = client.query(all_dates_sql)
    if result.result_rows:
        print("各日期記錄數:")
        print(f"{'Date':<12} {'Records':<8} {'Unique':<8}")
        print("-" * 30)
        for row in result.result_rows:
            date, records, unique = row
            status = "⚠️" if records > unique else "✅"
            print(f"{date:<12} {records:<8} {unique:<8} {status}")
    
    # 3. 檢查 ReplacingMergeTree 是否正常工作
    print("\n3. 檢查 ReplacingMergeTree 去重效果...")
    
    # 不使用 FINAL 查詢
    no_final_sql = """
    SELECT COUNT(*) as count_without_final
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
    WHERE snapshot_date = '2025-12-28'
      AND vx_type = 'V1' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
    """
    
    # 使用 FINAL 查詢
    with_final_sql = """
    SELECT COUNT(*) as count_with_final
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE snapshot_date = '2025-12-28'
      AND vx_type = 'V1' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
    """
    
    no_final_count = client.command(no_final_sql)
    with_final_count = client.command(with_final_sql)
    
    print(f"不使用 FINAL: {no_final_count} 筆")
    print(f"使用 FINAL:   {with_final_count} 筆")
    print(f"重複筆數:     {no_final_count - with_final_count} 筆")
    
    # 4. 分析重複資料的來源
    print("\n4. 分析重複資料來源...")
    
    source_analysis_sql = """
    SELECT 
        _version,
        _snapshot_time,
        COUNT(*) as record_count
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
    WHERE snapshot_date = '2025-12-28'
      AND vx_type = 'V1' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
    GROUP BY _version, _snapshot_time
    ORDER BY _snapshot_time
    """
    
    result = client.query(source_analysis_sql)
    if result.result_rows:
        print("重複資料來源分析:")
        print(f"{'Version':<20} {'Snapshot Time':<20} {'Records':<8}")
        print("-" * 50)
        for row in result.result_rows:
            version, snapshot_time, count = row
            print(f"{version:<20} {str(snapshot_time):<20} {count:<8}")
    
    # 5. 提供去重建議
    print("\n" + "=" * 60)
    print("去重建議")
    print("=" * 60)
    
    if no_final_count > with_final_count:
        print("🔍 問題確認:")
        print(f"  - 2025-12-28 存在 {no_final_count - with_final_count} 筆重複資料")
        print("  - ReplacingMergeTree 引擎可以去重，但需要使用 FINAL")
        
        print("\n💡 解決方案:")
        print("1. 立即方案：查詢時使用 FINAL")
        print("   SELECT * FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL")
        
        print("\n2. 根本方案：手動觸發 OPTIMIZE")
        print("   OPTIMIZE TABLE gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL")
        
        print("\n3. 預防方案：避免重複插入")
        print("   - 檢查補齊腳本是否重複執行")
        print("   - 確認 REFRESHABLE MV 與手動腳本不衝突")
        
        # 提供手動去重 SQL
        print("\n🔧 手動去重 SQL:")
        print("OPTIMIZE TABLE gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL")
        
    else:
        print("✅ 無重複資料問題")

if __name__ == "__main__":
    check_duplicates()