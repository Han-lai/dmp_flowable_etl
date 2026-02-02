#!/usr/bin/env python3
"""
同步缺失的批次
"""

import sys
import logging
import time
from datetime import datetime
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../core')))

from session_controller import SessionController
from batch_status_manager import BatchStatusManager, BatchStatus

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ClickHouse 連線設定
CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def execute_batch_sync(client, batch_id: str, start_time: str, end_time: str) -> int:
    """執行單個批次同步"""
    logger.info(f"同步批次: {batch_id}")
    logger.info(f"時間範圍: {start_time} ~ {end_time}")
    
    # 先清理可能存在的舊資料
    cleanup_sql = f"""
    ALTER TABLE bronze.bpm_act_hi_taskinst DELETE 
    WHERE _batch_id = '{batch_id}'
       OR (START_TIME_ >= '{start_time}' AND START_TIME_ < '{end_time}')
    """
    
    logger.info("清理舊資料...")
    client.command(cleanup_sql)
    time.sleep(1)  # 等待清理完成
    
    # 執行同步
    sync_sql = f"""
    INSERT INTO bronze.bpm_act_hi_taskinst
    SELECT *, 
           '{batch_id}' as _batch_id,
           now64(3) as _extracted_at,
           1 as _sync_version
    FROM jdbc('mssql_master', '
        SELECT * FROM APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108
        WHERE START_TIME_ >= ''{start_time}'' 
          AND START_TIME_ < ''{end_time}''
          AND START_TIME_ IS NOT NULL
        ORDER BY START_TIME_
    ')
    """
    
    sync_start = time.perf_counter()
    client.command(sync_sql)
    sync_duration = time.perf_counter() - sync_start
    
    # 取得同步的筆數
    count_sql = f"""
    SELECT count(*) FROM bronze.bpm_act_hi_taskinst 
    WHERE _batch_id = '{batch_id}'
    """
    row_count = client.command(count_sql)
    
    logger.info(f"✅ 同步完成: {row_count:,} 筆，耗時 {sync_duration:.2f} 秒")
    
    return row_count, sync_duration

def sync_running_batches():
    """同步所有 running 狀態的批次"""
    session_controller = SessionController(CLICKHOUSE_CONFIG)
    
    try:
        with session_controller.get_stateless_session() as client:
            status_manager = BatchStatusManager(client)
            
            # 取得所有 running 狀態的 ACT_HI_TASKINST_0108 批次
            running_sql = """
            SELECT 
                batch_id,
                watermark_start,
                watermark_end
            FROM bronze.sync_batch_control FINAL
            WHERE table_name = 'ACT_HI_TASKINST_0108' 
              AND status = 'running'
              AND watermark_start >= '2025-12-16'
            ORDER BY watermark_start
            """
            
            result = client.query(running_sql)
            
            if not result.result_rows:
                logger.info("沒有找到需要同步的批次")
                return
            
            logger.info(f"找到 {len(result.result_rows)} 個需要同步的批次")
            
            success_count = 0
            total_rows = 0
            
            for i, (batch_id, start_time, end_time) in enumerate(result.result_rows, 1):
                logger.info(f"\n{'='*60}")
                logger.info(f"處理批次 {i}/{len(result.result_rows)}: {batch_id}")
                logger.info(f"{'='*60}")
                
                try:
                    # 更新狀態為 running（確保狀態正確）
                    status_manager.update_batch_status(
                        'ACT_HI_TASKINST_0108', batch_id, BatchStatus.RUNNING
                    )
                    
                    # 執行同步
                    row_count, duration = execute_batch_sync(
                        client, batch_id, start_time, end_time
                    )
                    
                    # 更新為完成狀態
                    status_manager.update_batch_status(
                        'ACT_HI_TASKINST_0108', batch_id, BatchStatus.COMPLETED,
                        row_count, duration
                    )
                    
                    success_count += 1
                    total_rows += row_count
                    
                    logger.info(f"🎉 批次 {batch_id} 同步成功")
                    
                except Exception as e:
                    logger.error(f"❌ 批次 {batch_id} 同步失敗: {e}")
                    
                    # 更新為失敗狀態
                    try:
                        status_manager.update_batch_status(
                            'ACT_HI_TASKINST_0108', batch_id, BatchStatus.FAILED,
                            0, 0, str(e)
                        )
                    except:
                        pass
            
            # 總結
            logger.info(f"\n{'='*80}")
            logger.info(f"同步完成統計:")
            logger.info(f"成功批次: {success_count}/{len(result.result_rows)}")
            logger.info(f"總同步筆數: {total_rows:,}")
            logger.info(f"{'='*80}")
            
            if success_count == len(result.result_rows):
                logger.info("🎉 所有批次同步成功！")
            else:
                logger.warning("⚠️ 部分批次同步失敗，請檢查日誌")
    
    except Exception as e:
        logger.error(f"同步過程發生錯誤: {e}")
        raise
    
    finally:
        session_controller.close_all_sessions()

def main():
    """主程式"""
    import argparse
    
    parser = argparse.ArgumentParser(description='同步缺失的批次')
    parser.add_argument('--dry-run', action='store_true',
                       help='只顯示要同步的批次，不實際執行')
    args = parser.parse_args()
    
    if args.dry_run:
        # 只顯示要同步的批次
        import clickhouse_connect
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        
        running_sql = """
        SELECT 
            batch_id,
            watermark_start,
            watermark_end
        FROM bronze.sync_batch_control FINAL
        WHERE table_name = 'ACT_HI_TASKINST_0108' 
          AND status = 'running'
          AND watermark_start >= '2025-12-16'
        ORDER BY watermark_start
        """
        
        result = client.query(running_sql)
        
        print("🔍 要同步的批次:")
        print("-" * 60)
        
        for batch_id, start_time, end_time in result.result_rows:
            print(f"{batch_id}: {start_time} ~ {end_time}")
        
        print(f"\n總計: {len(result.result_rows)} 個批次")
        return
    
    try:
        sync_running_batches()
    except KeyboardInterrupt:
        logger.info("\n同步被使用者中斷")
        sys.exit(1)
    except Exception as e:
        logger.error(f"同步失敗: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()