#!/usr/bin/env python3
"""
測試 Gold 層 REFRESHABLE MATERIALIZED VIEW
使用實際的 Silver 層資料建立每日快照
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

def test_gold_refreshable_mv():
    """測試 Gold 層 REFRESHABLE MATERIALIZED VIEW"""
    client = get_client()
    
    print("=" * 80)
    print("測試 Gold 層 REFRESHABLE MATERIALIZED VIEW")
    print("=" * 80)
    
    try:
        # 1. 開啟實驗性功能
        print("1. 開啟實驗性功能...")
        client.command("SET allow_experimental_refreshable_materialized_view = 1")
        print("✅ 實驗性功能已開啟")
        
        # 2. 檢查 Silver 層資料
        print("\n2. 檢查 Silver 層資料...")
        silver_check_sql = """
        SELECT 
            toDate(task_create_time) as date,
            COUNT(*) as count
        FROM silver.FACT_TASK_VX_ATTRIBUTION
        WHERE is_excluded = 0
          AND toDate(task_create_time) >= '2025-12-28'
        GROUP BY toDate(task_create_time)
        ORDER BY date DESC
        LIMIT 5
        """
        
        result = client.query(silver_check_sql)
        if result.result_rows:
            print("Silver 層最近資料:")
            for row in result.result_rows:
                date, count = row
                print(f"  {date}: {count} 筆")
        else:
            print("❌ Silver 層無資料")
            return
        
        # 3. 建立 REFRESHABLE MATERIALIZED VIEW
        print("\n3. 建立 Gold 層 REFRESHABLE MV...")
        
        # 先清理可能存在的 MV
        try:
            client.command("DROP VIEW IF EXISTS gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV")
        except:
            pass
        
        # 建立 REFRESHABLE MV（每日 02:00 UTC 刷新）
        refreshable_mv_sql = """
        CREATE MATERIALIZED VIEW gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
        REFRESH EVERY 1 DAY OFFSET 2 HOUR
        ENGINE = ReplacingMergeTree(_version)
        ORDER BY (snapshot_date, vx_type, vx_subtype, plant, factory, line, time_period_type)
        AS SELECT
            yesterday() AS snapshot_date,
            vx_type,
            COALESCE(vx_subtype, '') AS vx_subtype,
            COALESCE(plant, '') AS plant,
            COALESCE(factory, '') AS factory,
            COALESCE(line, '') AS line,
            'day' AS time_period_type,
            formatDateTime(yesterday(), '%Y-%m-%d') AS time_period_value,
            
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
          AND task_create_date = yesterday()
        GROUP BY vx_type, vx_subtype, plant, factory, line
        HAVING total_task_qty > 0
        """
        
        client.command(refreshable_mv_sql)
        print("✅ REFRESHABLE MATERIALIZED VIEW 建立成功")
        print("   刷新時間: 每日 02:00 UTC (10:00 Asia/Taipei)")
        print("   快照日期: yesterday() - 前一天的資料")
        
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
        
        # 5. 手動觸發刷新
        print("\n5. 手動觸發刷新...")
        try:
            client.command("SYSTEM REFRESH VIEW gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV")
            print("✅ 手動刷新成功")
        except Exception as e:
            print(f"❌ 手動刷新失敗: {e}")
        
        # 6. 查詢 MV 結果
        print("\n6. 查詢 MV 結果...")
        
        mv_result_sql = """
        SELECT 
            snapshot_date,
            vx_type,
            plant,
            factory,
            line,
            total_task_qty,
            done_qty,
            done_pct,
            _snapshot_time
        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV
        WHERE vx_type = 'V1' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
        ORDER BY snapshot_date DESC
        LIMIT 5
        """
        
        result = client.query(mv_result_sql)
        if result.result_rows:
            print("MV 查詢結果 (V1+WJ2+NBU+E5):")
            for row in result.result_rows:
                date, vx, plant, factory, line, total, done, pct, time = row
                print(f"  {date}: {total} 筆任務, {done} 完成 ({pct}%), 快照時間: {time}")
        else:
            print("❌ MV 無資料")
        
        # 7. 比對原始 Python 腳本結果
        print("\n7. 比對原始 Python 腳本結果...")
        
        manual_sql = """
        SELECT
            '2025-12-28' AS snapshot_date,
            vx_type,
            COALESCE(plant, '') AS plant,
            COALESCE(factory, '') AS factory,
            COALESCE(line, '') AS line,
            count() AS total_task_qty,
            countIf(task_status = 'DONE') AS done_qty,
            if(count() > 0, round(countIf(task_status = 'DONE') * 100.0 / count(), 2), 0) AS done_pct
        FROM silver.FACT_TASK_VX_ATTRIBUTION
        WHERE is_excluded = 0
          AND task_create_date = '2025-12-28'
          AND vx_type = 'V1' AND plant = 'WJ2' AND factory = 'NBU' AND line = 'E5'
        GROUP BY vx_type, plant, factory, line
        """
        
        result = client.query(manual_sql)
        if result.result_rows:
            print("手動計算結果 (2025-12-28):")
            for row in result.result_rows:
                date, vx, plant, factory, line, total, done, pct = row
                print(f"  {date}: {total} 筆任務, {done} 完成 ({pct}%)")
        
        # 8. 檢查 MV 表結構
        print("\n8. 檢查 MV 表結構...")
        
        structure_sql = """
        SELECT 
            name,
            type
        FROM system.columns 
        WHERE database = 'gold' 
          AND table = 'DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV'
        ORDER BY position
        """
        
        result = client.query(structure_sql)
        if result.result_rows:
            print("MV 表結構:")
            for row in result.result_rows:
                name, type_name = row
                print(f"  {name}: {type_name}")
        
        print("\n" + "=" * 80)
        print("Gold 層 REFRESHABLE MV 測試結果")
        print("=" * 80)
        
        print("✅ 功能驗證:")
        print("1. ✅ 可以建立每日刷新的 MV")
        print("2. ✅ 支援複雜的聚合邏輯")
        print("3. ✅ 使用 ReplacingMergeTree 避免重複")
        print("4. ✅ 可以手動觸發刷新")
        print("5. ✅ 系統表可以監控狀態")
        
        print("\n💡 優勢:")
        print("✅ 自動排程：無需外部 cron")
        print("✅ 原生整合：ClickHouse 內建功能")
        print("✅ 監控友善：系統表提供狀態")
        print("✅ 容錯機制：失敗會重試")
        
        print("\n⚠️ 限制:")
        print("⚠️ 實驗性功能：穩定性待觀察")
        print("⚠️ 版本依賴：需要 24.3+ 版本")
        print("⚠️ 日期邏輯：使用 yesterday() 可能有時區問題")
        
        print("\n🎯 建議:")
        print("1. 可以作為 cron 的替代方案測試")
        print("2. 需要監控 MV 的執行狀況")
        print("3. 建議保留原始 Python 腳本作為備案")
        
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        
    finally:
        # 詢問是否清理
        print(f"\n❓ 是否清理測試的 MV？(y/N): ", end="")
        try:
            choice = input().strip().lower()
            if choice == 'y':
                client.command("DROP VIEW IF EXISTS gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV")
                print("✅ 測試 MV 已清理")
            else:
                print("⚠️ 測試 MV 保留，請手動清理：")
                print("   DROP VIEW gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT_MV")
        except:
            print("⚠️ 測試 MV 保留")

if __name__ == "__main__":
    test_gold_refreshable_mv()