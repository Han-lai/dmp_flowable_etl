#!/usr/bin/env python3
"""
建立 FlowableTaskStats 的批次記錄
按照 LastUpdatedTime 每 7 天分批（資料量較小）
"""

import clickhouse_connect
from datetime import datetime, timedelta
import sys

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def get_flowable_date_range(client):
    """取得 FlowableTaskStats 的時間範圍"""
    print("📊 查詢 FlowableTaskStats 時間範圍...")
    
    try:
        result = client.query("""
            SELECT * FROM jdbc('mssql_master', '
                SELECT 
                    MIN(LastUpdatedTime) as min_time,
                    MAX(LastUpdatedTime) as max_time,
                    COUNT(*) as total_count
                FROM APP_SRV_COMMON.dbo.FlowableTaskStats
                WHERE LastUpdatedTime IS NOT NULL
            ')
        """)
        
        if result.result_rows:
            min_time, max_time, total_count = result.result_rows[0]
            print(f"  最早時間: {min_time}")
            print(f"  最晚時間: {max_time}")
            print(f"  總筆數: {total_count:,}")
            return min_time, max_time, total_count
    except Exception as e:
        print(f"  ❌ 查詢失敗: {e}")
        return None, None, 0
    
    return None, None, 0

def create_flowable_batches():
    """建立 FlowableTaskStats 批次記錄"""
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("🔄 建立 FlowableTaskStats 批次")
    print("=" * 80)
    
    # 取得實際時間範圍
    min_time, max_time, total_count = get_flowable_date_range(client)
    
    if not min_time or not max_time:
        print("❌ 無法取得時間範圍，使用預設值")
        # 預設值：假設近一年資料
        start_date = datetime(2025, 1, 1)
        end_date = datetime(2026, 1, 30)
    else:
        start_date = min_time
        end_date = max_time
    
    print(f"\n資料範圍: {start_date} ~ {end_date}")
    
    # 計算天數和批次
    total_days = (end_date - start_date).days
    batch_days = 7  # 每批次 7 天
    
    print(f"批次間隔: {batch_days} 天")
    print(f"總計天數: {total_days}")
    
    # 生成批次
    batches_to_create = []
    current_date = start_date if isinstance(start_date, datetime) else datetime.fromisoformat(str(start_date))
    end_datetime = end_date if isinstance(end_date, datetime) else datetime.fromisoformat(str(end_date))
    
    while current_date < end_datetime:
        next_date = min(current_date + timedelta(days=batch_days), end_datetime + timedelta(seconds=1))
        
        batch_id = f"FlowableTaskStats_{current_date.strftime('%Y%m%d')}"
        
        batches_to_create.append({
            'batch_id': batch_id,
            'watermark_start': current_date.strftime('%Y-%m-%d %H:%M:%S'),
            'watermark_end': next_date.strftime('%Y-%m-%d %H:%M:%S')
        })
        
        current_date = next_date
    
    print(f"準備建立 {len(batches_to_create)} 個批次")
    if total_count > 0:
        print(f"預估每批次約 {total_count // len(batches_to_create):,} 筆")
    
    # 確認是否繼續
    response = input("\n是否繼續建立批次？(y/N): ")
    if response.lower() != 'y':
        print("取消建立批次")
        return 0
    
    # 建立批次記錄
    success_count = 0
    
    for i, batch in enumerate(batches_to_create, 1):
        try:
            print(f"建立批次 {i}/{len(batches_to_create)}: {batch['batch_id']}")
            
            # 插入批次控制記錄
            insert_sql = """
            INSERT INTO bronze.sync_batch_control 
            (table_name, batch_id, batch_start_time, batch_end_time,
             watermark_start, watermark_end, status, row_count, 
             duration_seconds, error_message, created_at, updated_at)
            VALUES 
            (%(table_name)s, %(batch_id)s, now64(3), now64(3),
             %(watermark_start)s, %(watermark_end)s, %(status)s, 0,
             0, '', now64(3), now64(3))
            """
            
            params = {
                'table_name': 'FlowableTaskStats',
                'batch_id': batch['batch_id'],
                'watermark_start': batch['watermark_start'],
                'watermark_end': batch['watermark_end'],
                'status': 'running'  # 初始狀態設為 running
            }
            
            client.command(insert_sql, parameters=params)
            success_count += 1
            
            print(f"  ✅ {batch['watermark_start']} ~ {batch['watermark_end']}")
            
        except Exception as e:
            print(f"  ❌ 建立失敗: {e}")
    
    print(f"\n{'='*60}")
    print(f"批次建立完成: {success_count}/{len(batches_to_create)} 成功")
    print(f"{'='*60}")
    
    return success_count

def verify_created_batches():
    """驗證建立的批次"""
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("\n🔍 驗證建立的批次")
    print("-" * 60)
    
    verify_sql = """
    SELECT 
        batch_id,
        watermark_start,
        watermark_end,
        status
    FROM bronze.sync_batch_control FINAL
    WHERE table_name = 'FlowableTaskStats'
    ORDER BY watermark_start
    """
    
    result = client.query(verify_sql)
    
    if result.result_rows:
        print(f"找到 {len(result.result_rows)} 個批次:")
        for i, (batch_id, start, end, status) in enumerate(result.result_rows, 1):
            print(f"  {i:2d}. {batch_id}: {start} ~ {end} ({status})")
    else:
        print("❌ 沒有找到批次記錄")

if __name__ == "__main__":
    try:
        created_count = create_flowable_batches()
        if created_count > 0:
            verify_created_batches()
    except KeyboardInterrupt:
        print("\n操作被取消")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        sys.exit(1)
