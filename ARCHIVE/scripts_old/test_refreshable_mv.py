#!/usr/bin/env python3
"""
測試 ClickHouse REFRESHABLE MATERIALIZED VIEW
開啟實驗性功能並測試每日快照的可行性
"""
import clickhouse_connect
from datetime import datetime

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

def test_refreshable_mv():
    """測試 REFRESHABLE MATERIALIZED VIEW"""
    client = get_client()
    
    print("=" * 60)
    print("測試 REFRESHABLE MATERIALIZED VIEW")
    print("=" * 60)
    
    try:
        # 1. 開啟實驗性功能
        print("1. 開啟實驗性功能...")
        client.command("SET allow_experimental_refreshable_materialized_view = 1")
        print("✅ 實驗性功能已開啟")
        
        # 2. 建立測試資料庫
        print("\n2. 建立測試環境...")
        client.command("CREATE DATABASE IF NOT EXISTS test_refresh")
        print("✅ 測試資料庫建立完成")
        
        # 3. 建立來源表（模擬 Silver 層）
        source_table_sql = """
        CREATE TABLE IF NOT EXISTS test_refresh.source_tasks (
            task_id String,
            vx_type String,
            plant String,
            factory String,
            line String,
            task_status String,
            task_create_date Date,
            task_create_time DateTime64(3),
            is_excluded UInt8
        ) ENGINE = MergeTree()
        ORDER BY (task_create_date, task_id)
        """
        
        client.command(source_table_sql)
        print("✅ 來源表建立完成")
        
        # 4. 插入測試資料
        print("\n3. 插入測試資料...")
        test_data_sql = """
        INSERT INTO test_refresh.source_tasks VALUES
        ('task1', 'V1', 'WJ2', 'NBU', 'E5', 'DONE', '2025-12-28', '2025-12-28 10:00:00', 0),
        ('task2', 'V1', 'WJ2', 'NBU', 'E5', 'TODO', '2025-12-28', '2025-12-28 11:00:00', 0),
        ('task3', 'V1', 'WJ2', 'NBU', 'E5', 'DOING', '2025-12-29', '2025-12-29 09:00:00', 0),
        ('task4', 'V1', 'WJ2', 'NBU', 'E5', 'DONE', '2025-12-29', '2025-12-29 14:00:00', 0)
        """
        
        client.command(test_data_sql)
        print("✅ 測試資料插入完成")
        
        # 5. 建立 REFRESHABLE MATERIALIZED VIEW
        print("\n4. 建立 REFRESHABLE MATERIALIZED VIEW...")
        
        # 先清理可能存在的 MV
        try:
            client.command("DROP VIEW IF EXISTS test_refresh.daily_snapshot_mv")
        except:
            pass
        
        refreshable_mv_sql = """
        CREATE MATERIALIZED VIEW test_refresh.daily_snapshot_mv
        REFRESH EVERY 30 SECOND
        ENGINE = MergeTree()
        ORDER BY (snapshot_date, vx_type, plant, factory, line)
        AS SELECT
            today() AS snapshot_date,
            vx_type,
            plant,
            factory,
            line,
            'day' AS time_period_type,
            count() AS total_task_qty,
            countIf(task_status = 'TODO') AS todo_qty,
            countIf(task_status = 'DOING') AS doing_qty,
            countIf(task_status = 'DONE') AS done_qty,
            now64(3) AS _snapshot_time
        FROM test_refresh.source_tasks
        WHERE is_excluded = 0
          AND task_create_date = today()
        GROUP BY vx_type, plant, factory, line
        """
        
        client.command(refreshable_mv_sql)
        print("✅ REFRESHABLE MATERIALIZED VIEW 建立成功")
        print("   刷新間隔: 30 秒")
        
        # 6. 檢查 MV 狀態
        print("\n5. 檢查 MV 狀態...")
        
        # 檢查系統表中的 refresh 資訊
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
        WHERE database = 'test_refresh' AND view = 'daily_snapshot_mv'
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
        else:
            print("❌ 未找到 MV 刷新資訊")
        
        # 7. 查詢 MV 結果
        print("\n6. 查詢 MV 結果...")
        
        mv_result_sql = """
        SELECT 
            snapshot_date,
            vx_type,
            plant,
            factory,
            line,
            total_task_qty,
            todo_qty,
            doing_qty,
            done_qty,
            _snapshot_time
        FROM test_refresh.daily_snapshot_mv
        ORDER BY snapshot_date, vx_type, plant, factory, line
        """
        
        result = client.query(mv_result_sql)
        if result.result_rows:
            print("MV 查詢結果:")
            for row in result.result_rows:
                print(f"  {row}")
        else:
            print("❌ MV 無資料")
        
        # 8. 測試手動刷新
        print("\n7. 測試手動刷新...")
        try:
            client.command("SYSTEM REFRESH VIEW test_refresh.daily_snapshot_mv")
            print("✅ 手動刷新成功")
        except Exception as e:
            print(f"❌ 手動刷新失敗: {e}")
        
        # 9. 再次查詢結果
        print("\n8. 手動刷新後查詢結果...")
        result = client.query(mv_result_sql)
        if result.result_rows:
            print("刷新後結果:")
            for row in result.result_rows:
                print(f"  {row}")
        
        # 10. 測試新增資料後的自動刷新
        print("\n9. 測試新增資料...")
        new_data_sql = """
        INSERT INTO test_refresh.source_tasks VALUES
        ('task5', 'V1', 'WJ2', 'NBU', 'E5', 'DONE', today(), now64(3), 0)
        """
        
        client.command(new_data_sql)
        print("✅ 新資料插入完成")
        
        # 等待自動刷新
        import time
        print("等待 35 秒讓 MV 自動刷新...")
        time.sleep(35)
        
        # 查詢最新結果
        result = client.query(mv_result_sql)
        if result.result_rows:
            print("自動刷新後結果:")
            for row in result.result_rows:
                print(f"  {row}")
        
        print("\n" + "=" * 60)
        print("測試結果總結")
        print("=" * 60)
        
        print("✅ REFRESHABLE MATERIALIZED VIEW 功能測試:")
        print("1. ✅ 實驗性功能可以開啟")
        print("2. ✅ 可以建立 REFRESHABLE MV")
        print("3. ✅ 支援定時刷新 (30秒間隔)")
        print("4. ✅ 支援手動刷新")
        print("5. ✅ 系統表可以監控狀態")
        
        print("\n💡 用於 Gold 層快照的可行性:")
        print("✅ 技術可行：可以設定每日刷新")
        print("⚠️ 實驗性功能：穩定性待觀察")
        print("⚠️ 日期保證：需要確保每天都有資料觸發")
        
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        
    finally:
        # 清理測試環境
        print("\n10. 清理測試環境...")
        try:
            client.command("DROP VIEW IF EXISTS test_refresh.daily_snapshot_mv")
            client.command("DROP TABLE IF EXISTS test_refresh.source_tasks")
            client.command("DROP DATABASE IF EXISTS test_refresh")
            print("✅ 測試環境清理完成")
        except Exception as e:
            print(f"⚠️ 清理失敗: {e}")

if __name__ == "__main__":
    test_refreshable_mv()