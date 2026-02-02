#!/usr/bin/env python3
"""
建立 ACT_HI_IDENTITYLINK_0108 的批次記錄 (小批次策略)
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

def create_identitylink_batches():
    """建立 ACT_HI_IDENTITYLINK_0108 批次記錄"""
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    
    print("🔄 建立 ACT_HI_IDENTITYLINK_0108 批次")
    print("=" * 80)
    
    # 資料範圍：2025-10-08 ~ 2026-01-08
    # 總計約 50,000,000 筆
    # VARINST 是 12 小時一批 (約 9 萬筆)
    # IDENTITYLINK 資料量是 VARINST 的 3 倍
    # 建議每批次 6 小時，以控制每批次資料量在 10 萬筆左右
    
    start_date = datetime(2025, 10, 8, 15, 18, 54)
    end_date = datetime(2026, 1, 8, 17, 10, 19)
    
    print(f"資料範圍: {start_date} ~ {end_date}")
    print(f"批次間隔: 6 小時 (保守策略)")
    print(f"預估總筆數: ~50,000,000")
    
    # 生成每 6 小時的批次
    batches_to_create = []
    current_date = start_date
    
    while current_date < end_date:
        next_date = min(current_date + timedelta(hours=6), end_date)
        
        batch_id = f"ACT_HI_IDENTITYLINK_0108_{current_date.strftime('%Y%m%d_%H%M%S')}"
        
        batches_to_create.append({
            'batch_id': batch_id,
            'watermark_start': current_date.strftime('%Y-%m-%d %H:%M:%S'),
            'watermark_end': next_date.strftime('%Y-%m-%d %H:%M:%S')
        })
        
        current_date = next_date
    
    print(f"準備建立 {len(batches_to_create)} 個批次")
    print(f"預估每批次資料量約 10-15 萬筆")
    
    # 確認是否繼續
    response = input("\n是否繼續建立批次？(y/N): ")
    if response.lower() != 'y':
        print("取消建立批次")
        return
    
    # 建立批次記錄
    success_count = 0
    
    for i, batch in enumerate(batches_to_create, 1):
        try:
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
                'table_name': 'ACT_HI_IDENTITYLINK_0108',
                'batch_id': batch['batch_id'],
                'watermark_start': batch['watermark_start'],
                'watermark_end': batch['watermark_end'],
                'status': 'running'  # 初始狀態設為 running
            }
            
            client.command(insert_sql, parameters=params)
            success_count += 1
            
            if i % 10 == 0:
                print(f"已建立 {i}/{len(batches_to_create)} 個批次...")
            
        except Exception as e:
            print(f"  ❌ 批次 {batch['batch_id']} 建立失敗: {e}")
    
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
    SELECT count(*)
    FROM bronze.sync_batch_control FINAL
    WHERE table_name = 'ACT_HI_IDENTITYLINK_0108'
    """
    
    count = client.command(verify_sql)
    print(f"目前共有 {count} 個 ACT_HI_IDENTITYLINK_0108 批次記錄")

if __name__ == "__main__":
    try:
        created_count = create_identitylink_batches()
        if created_count is not None and created_count > 0:
            verify_created_batches()
    except KeyboardInterrupt:
        print("\n操作被取消")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        sys.exit(1)
