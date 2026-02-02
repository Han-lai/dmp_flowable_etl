#!/usr/bin/env python3
"""
建立 ACT_HI_TASKINST_0108 缺失的批次
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

def create_missing_batches():
    """建立缺失的批次記錄"""
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("🔄 建立 ACT_HI_TASKINST_0108 缺失批次")
    print("=" * 80)
    
    # 缺失時間範圍：2025-12-16 15:18:54 ~ 2026-01-08 15:12:27
    start_date = datetime(2025, 12, 16, 15, 18, 54)
    end_date = datetime(2026, 1, 8, 15, 12, 27)
    
    print(f"缺失範圍: {start_date} ~ {end_date}")
    print(f"批次間隔: 1 天")
    
    # 生成每日批次
    batches_to_create = []
    current_date = start_date
    
    while current_date < end_date:
        next_date = min(current_date + timedelta(days=1), end_date)
        
        batch_id = f"ACT_HI_TASKINST_0108_{current_date.strftime('%Y%m%d_%H%M%S')}"
        
        batches_to_create.append({
            'batch_id': batch_id,
            'watermark_start': current_date.strftime('%Y-%m-%d %H:%M:%S'),
            'watermark_end': next_date.strftime('%Y-%m-%d %H:%M:%S')
        })
        
        current_date = next_date
    
    print(f"準備建立 {len(batches_to_create)} 個批次")
    
    # 確認是否繼續
    response = input("\n是否繼續建立批次？(y/N): ")
    if response.lower() != 'y':
        print("取消建立批次")
        return
    
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
                'table_name': 'ACT_HI_TASKINST_0108',
                'batch_id': batch['batch_id'],
                'watermark_start': batch['watermark_start'],
                'watermark_end': batch['watermark_end'],
                'status': 'running'  # 初始狀態設為 running，等待同步
            }
            
            client.command(insert_sql, parameters=params)
            success_count += 1
            
            print(f"  ✅ 時間範圍: {batch['watermark_start']} ~ {batch['watermark_end']}")
            
        except Exception as e:
            print(f"  ❌ 建立失敗: {e}")
    
    print(f"\n{'='*60}")
    print(f"批次建立完成: {success_count}/{len(batches_to_create)} 成功")
    print(f"{'='*60}")
    
    if success_count > 0:
        print("✅ 批次記錄已建立，狀態為 'running'")
        print("💡 接下來可以使用同步工具執行這些批次")
    
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
    WHERE table_name = 'ACT_HI_TASKINST_0108'
      AND watermark_start >= '2025-12-16 15:18:54'
    ORDER BY watermark_start
    """
    
    result = client.query(verify_sql)
    
    if result.result_rows:
        print(f"找到 {len(result.result_rows)} 個新批次:")
        for batch_id, start, end, status in result.result_rows:
            print(f"  {batch_id}: {start} ~ {end} ({status})")
    else:
        print("❌ 沒有找到新建立的批次")

if __name__ == "__main__":
    try:
        created_count = create_missing_batches()
        if created_count > 0:
            verify_created_batches()
    except KeyboardInterrupt:
        print("\n操作被取消")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        sys.exit(1)