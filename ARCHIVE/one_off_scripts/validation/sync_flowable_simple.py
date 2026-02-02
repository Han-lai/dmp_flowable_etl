#!/usr/bin/env python3
"""
FlowableTaskStats 簡易同步腳本
避免 Session 鎖定問題，使用無 Session 的直接連線
"""

import clickhouse_connect
import time
from datetime import datetime

# ClickHouse 連線設定 (無 session，更長 timeout)
CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 1800,  # 30 分鐘
    "connect_timeout": 60
}

def sync_single_batch(batch_id: str, start_time: str, end_time: str):
    """同步單一批次 - 每次都建立新連線"""
    print(f"\n{'='*60}")
    print(f"同步批次: {batch_id}")
    print(f"時間範圍: {start_time} ~ {end_time}")
    print(f"{'='*60}")
    
    # 每次建立新連線
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    try:
        # 設定長 timeout
        client.command("SET max_execution_time = 1800")
        client.command("SET send_timeout = 1800")
        client.command("SET receive_timeout = 1800")
        
        # 執行同步
        sync_sql = f"""
        INSERT INTO bronze.common_flowable_task_stats
        SELECT *, 
               '{batch_id}' as _batch_id,
               now64(3) as _sync_time
        FROM jdbc('mssql_master', '
            SELECT * FROM APP_SRV_COMMON.dbo.FlowableTaskStats
            WHERE LastUpdatedTime >= ''{start_time}'' 
              AND LastUpdatedTime < ''{end_time}''
            ORDER BY LastUpdatedTime
        ')
        """
        
        sync_start = time.perf_counter()
        client.command(sync_sql)
        sync_duration = time.perf_counter() - sync_start
        
        # 取得同步的筆數
        count_sql = f"""
        SELECT count(*) FROM bronze.common_flowable_task_stats 
        WHERE _batch_id = '{batch_id}'
        """
        row_count = client.command(count_sql)
        
        print(f"✅ 同步完成: {row_count:,} 筆，耗時 {sync_duration:.1f} 秒")
        
        # 更新批次狀態
        update_sql = f"""
        INSERT INTO bronze.sync_batch_control 
        SELECT table_name, batch_id, now64(3), now64(3), watermark_start, watermark_end, 
               'completed', {row_count}, {sync_duration:.2f}, '', now64(3), now64(3)
        FROM bronze.sync_batch_control FINAL
        WHERE table_name = 'FlowableTaskStats' AND batch_id = '{batch_id}'
        """
        client.command(update_sql)
        print(f"✅ 批次狀態已更新為 completed")
        
        return True, row_count
        
    except Exception as e:
        print(f"❌ 同步失敗: {e}")
        return False, 0
    
    finally:
        client.close()

def get_running_batches():
    """取得待同步的批次"""
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    result = client.query("""
        SELECT batch_id, watermark_start, watermark_end
        FROM bronze.sync_batch_control FINAL
        WHERE table_name = 'FlowableTaskStats' 
          AND status = 'running'
        ORDER BY watermark_start
    """)
    
    client.close()
    return result.result_rows

def main():
    print("=" * 60)
    print("FlowableTaskStats 簡易同步（無 Session 模式）")
    print("=" * 60)
    print(f"開始時間: {datetime.now()}")
    
    # 取得待同步批次
    batches = get_running_batches()
    
    if not batches:
        print("\n✅ 沒有待同步的批次")
        return
    
    print(f"\n找到 {len(batches)} 個待同步批次")
    
    success_count = 0
    total_rows = 0
    
    for i, (batch_id, start_time, end_time) in enumerate(batches, 1):
        print(f"\n📦 處理批次 {i}/{len(batches)}")
        
        success, rows = sync_single_batch(batch_id, start_time, end_time)
        
        if success:
            success_count += 1
            total_rows += rows
        
        # 每批次之間休息 5 秒
        if i < len(batches):
            print("⏳ 休息 5 秒...")
            time.sleep(5)
    
    # 顯示最終結果
    print("\n" + "=" * 60)
    print("同步完成統計:")
    print(f"  成功批次: {success_count}/{len(batches)}")
    print(f"  總同步筆數: {total_rows:,}")
    print("=" * 60)
    
    # 顯示表總筆數
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    table_count = client.command("SELECT count() FROM bronze.common_flowable_task_stats")
    print(f"\n📊 表總筆數: {table_count:,}")
    client.close()
    
    print(f"\n完成時間: {datetime.now()}")

if __name__ == "__main__":
    main()
