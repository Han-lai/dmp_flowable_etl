#!/usr/bin/env python3
"""
建立 Gold 層 REFRESHABLE MATERIALIZED VIEW
取代手動 Python 腳本，實現自動每日快照
"""
import clickhouse_connect

def create_refreshable_mv():
    client = clickhouse_connect.get_client(
        host="REDACTED_IP",
        port=8121,
        username="default",
        password="default"
    )
    
    print("=" * 60)
    print("建立 Gold 層 REFRESHABLE MATERIALIZED VIEW")
    print("=" * 60)
    
    try:
        # 1. 開啟實驗性功能
        print("1. 開啟實驗性功能...")
        client.command("SET allow_experimental_refreshable_materialized_view = 1")
        print("✅ 實驗性功能已開啟")
        
        # 2. 清理舊的 MV
        print("\n2. 清理舊的 MV...")
        try:
            client.command("DROP VIEW IF EXISTS gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV")
            print("✅ 舊 MV 已清理")
        except:
            print("⚠️ 無舊 MV 需清理")
        
        # 3. 建立新的 REFRESHABLE MV
        print("\n3. 建立 REFRESHABLE MV...")
        
        refreshable_mv_sql = """
        CREATE MATERIALIZED VIEW gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
        REFRESH EVERY 1 DAY OFFSET 2 HOUR
        ENGINE = ReplacingMergeTree(_version)
        ORDER BY (snapshot_date, vx_type, vx_subtype, plant, factory, line, time_period_type)
        AS SELECT
            today() AS snapshot_date,
            vx_type,
            COALESCE(vx_subtype, '') AS vx_subtype,
            COALESCE(plant, '') AS plant,
            COALESCE(factory, '') AS factory,
            COALESCE(line, '') AS line,
            'day' AS time_period_type,
            formatDateTime(today(), '%Y-%m-%d') AS time_period_value,
            
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
          AND task_create_date = today()
        GROUP BY vx_type, vx_subtype, plant, factory, line
        HAVING total_task_qty > 0
        """
        
        client.command(refreshable_mv_sql)
        print("✅ REFRESHABLE MV 建立成功")
        print("   刷新時間: 每日 02:00 UTC (10:00 Asia/Taipei)")
        print("   快照日期: today() - 當天的資料")
        
        # 4. 檢查 MV 狀態
        print("\n4. 檢查 MV 狀態...")
        
        refresh_info_sql = """
        SELECT 
            database,
            view,
            status,
            last_refresh_time,
            next_refresh_time,
            refresh_count,
            exception
        FROM system.view_refreshes
        WHERE database = 'gold' AND view = 'DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV'
        """
        
        result = client.query(refresh_info_sql)
        if result.result_rows:
            print("MV 刷新狀態:")
            for row in result.result_rows:
                db, view, status, last_refresh, next_refresh, count, exception = row
                print(f"  狀態: {status}")
                print(f"  上次刷新: {last_refresh}")
                print(f"  下次刷新: {next_refresh}")
                print(f"  刷新次數: {count}")
                if exception:
                    print(f"  錯誤: {exception}")
        
        # 5. 手動觸發第一次刷新
        print("\n5. 手動觸發第一次刷新...")
        try:
            client.command("SYSTEM REFRESH VIEW gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV")
            print("✅ 手動刷新成功")
        except Exception as e:
            print(f"❌ 手動刷新失敗: {e}")
        
        # 6. 檢查結果
        print("\n6. 檢查 MV 結果...")
        
        mv_result_sql = """
        SELECT 
            snapshot_date,
            COUNT(*) as record_count,
            SUM(total_task_qty) as total_tasks
        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
        GROUP BY snapshot_date
        ORDER BY snapshot_date DESC
        LIMIT 5
        """
        
        result = client.query(mv_result_sql)
        if result.result_rows:
            print("MV 查詢結果:")
            for row in result.result_rows:
                date, records, tasks = row
                print(f"  {date}: {records} 筆記錄, {tasks} 個任務")
        else:
            print("❌ MV 無資料 (可能今天沒有新任務)")
        
        print("\n" + "=" * 60)
        print("REFRESHABLE MV 建立完成")
        print("=" * 60)
        
        print("✅ 功能說明:")
        print("1. 每日 02:00 UTC 自動刷新")
        print("2. 產生當天的任務快照")
        print("3. 使用 ReplacingMergeTree 避免重複")
        print("4. 可透過 system.view_refreshes 監控")
        
        print("\n⚠️ 注意事項:")
        print("1. 這只會產生今天的快照，不會補齊歷史資料")
        print("2. 歷史資料仍需要用 Python 腳本補齊")
        print("3. 實驗性功能，建議監控執行狀況")
        
    except Exception as e:
        print(f"\n❌ 建立失敗: {e}")

if __name__ == "__main__":
    create_refreshable_mv()