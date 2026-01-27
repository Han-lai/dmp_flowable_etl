#!/usr/bin/env python3
"""
補齊 Gold 層歷史快照資料
批量建立缺失日期的快照
"""
import clickhouse_connect
from datetime import datetime, timedelta

# ClickHouse 連接設定
CH_HOST = "10.136.218.207"
CH_PORT = 8121
CH_USER = "default"
CH_PASSWORD = "default"

def get_client():
    """建立 ClickHouse 連線"""
    return clickhouse_connect.get_client(
        host=CH_HOST,
        port=CH_PORT,
        username=CH_USER,
        password=CH_PASSWORD
    )

def get_missing_dates():
    """取得需要補齊的日期清單"""
    # 直接列出需要補齊的日期（從檢查結果得知）
    missing_dates = [
        '2025-12-01', '2025-12-02', '2025-12-03', '2025-12-04', '2025-12-05', '2025-12-06',
        '2025-12-09', '2025-12-10', '2025-12-11', '2025-12-12', '2025-12-13', '2025-12-14',
        '2025-12-15', '2025-12-16', '2025-12-17', '2025-12-18', '2025-12-19', '2025-12-20',
        '2025-12-21', '2025-12-22', '2025-12-23', '2025-12-24', '2025-12-25', '2025-12-26',
        '2025-12-27', '2025-12-29', '2025-12-30', '2025-12-31', '2026-01-02', '2026-01-07',
        '2026-01-08'
    ]
    
    return missing_dates

def create_snapshot_for_date(client, snapshot_date):
    """為指定日期建立快照"""
    print(f"建立 {snapshot_date} 快照...")
    
    sql = f"""
    INSERT INTO gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
    SELECT
        toDate('{snapshot_date}') AS snapshot_date,
        vx_type,
        COALESCE(vx_subtype, '') AS vx_subtype,
        COALESCE(plant, '') AS plant,
        COALESCE(factory, '') AS factory,
        COALESCE(line, '') AS line,
        'day' AS time_period_type,
        '{snapshot_date}' AS time_period_value,
        
        count() AS total_task_qty,
        countIf(task_status = 'TODO') AS todo_qty,
        countIf(task_status = 'DOING') AS doing_qty,
        countIf(task_status = 'DONE') AS done_qty,
        countIf(task_status IN ('DOING', 'DONE')) AS doing_done_qty,
        countIf(task_status IN ('TODO', 'DOING')) AS todo_doing_acc_qty,
        
        if(count() > 0, round(countIf(task_status = 'TODO') * 100.0 / count(), 2), 0) AS todo_pct,
        if(count() > 0, round(countIf(task_status = 'DOING') * 100.0 / count(), 2), 0) AS doing_pct,
        if(count() > 0, round(countIf(task_status = 'DONE') * 100.0 / count(), 2), 0) AS done_pct,
        if(count() > 0, round(countIf(task_status IN ('DOING', 'DONE')) * 100.0 / count(), 2), 0) AS doing_done_pct,
        
        toUnixTimestamp64Milli(now64(3)) AS _version,
        now64(3) AS _snapshot_time
        
    FROM silver.FACT_TASK_VX_ATTRIBUTION
    WHERE is_excluded = 0
      AND task_create_date = toDate('{snapshot_date}')
    GROUP BY vx_type, vx_subtype, plant, factory, line
    HAVING total_task_qty > 0
    """
    
    try:
        client.command(sql)
        
        # 查詢插入的記錄數
        count_sql = f"""
        SELECT count() FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
        WHERE snapshot_date = toDate('{snapshot_date}')
        """
        count = client.command(count_sql)
        
        print(f"✅ {snapshot_date}: {count} 筆記錄")
        return True, count
        
    except Exception as e:
        print(f"❌ {snapshot_date}: 失敗 - {e}")
        return False, 0

def main():
    """主要補齊流程"""
    print("=" * 60)
    print("Gold 層歷史快照補齊")
    print("=" * 60)
    
    client = get_client()
    
    # 1. 取得缺失日期
    print("1. 檢查缺失日期...")
    missing_dates = get_missing_dates()
    
    if not missing_dates:
        print("✅ 無缺失日期，所有資料已完整")
        return
    
    print(f"發現 {len(missing_dates)} 個缺失日期:")
    for date in missing_dates:
        print(f"  {date}")
    
    # 2. 確認是否繼續
    print(f"\n是否開始補齊 {len(missing_dates)} 個日期的快照？(y/N): ", end="")
    try:
        choice = input().strip().lower()
        if choice != 'y':
            print("取消補齊")
            return
    except:
        print("取消補齊")
        return
    
    # 3. 批量補齊
    print(f"\n2. 開始補齊快照...")
    success_count = 0
    total_records = 0
    
    for date in missing_dates:
        success, count = create_snapshot_for_date(client, date)
        if success:
            success_count += 1
            total_records += count
    
    # 4. 總結報告
    print(f"\n" + "=" * 60)
    print("補齊結果總結")
    print("=" * 60)
    
    print(f"📊 統計:")
    print(f"  需要補齊: {len(missing_dates)} 個日期")
    print(f"  成功補齊: {success_count} 個日期")
    print(f"  失敗數量: {len(missing_dates) - success_count} 個日期")
    print(f"  總記錄數: {total_records} 筆")
    
    if success_count == len(missing_dates):
        print(f"\n✅ 所有歷史快照補齊完成")
    else:
        print(f"\n⚠️ 部分日期補齊失敗，請檢查錯誤訊息")
    
    # 5. 驗證結果
    print(f"\n3. 驗證補齊結果...")
    
    # 檢查特定條件的資料
    verify_sql = """
    SELECT 
        snapshot_date,
        total_task_qty
    FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
    WHERE vx_type = 'V1' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
      AND snapshot_date >= '2025-12-01'
    ORDER BY snapshot_date
    """
    
    result = client.query(verify_sql)
    if result.result_rows:
        print("驗證結果 (V1+WJ2+NBU+E5):")
        for row in result.result_rows:
            date, count = row
            print(f"  {date}: {count} 筆任務")
    
    print(f"\n💡 下一步:")
    print(f"1. 檢查 Cube.js Historical Trends 是否顯示完整資料")
    print(f"2. 監控 REFRESHABLE MV 未來的自動執行")
    print(f"3. 定期檢查 system.view_refreshes 狀態")

if __name__ == "__main__":
    main()