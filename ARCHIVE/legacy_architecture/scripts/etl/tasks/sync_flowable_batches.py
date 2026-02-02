#!/usr/bin/env python3
"""
同步 FlowableTaskStats 批次
從 MSSQL 同步到 ClickHouse bronze.common_flowable_task_stats
使用動態 schema 建表避免欄位不符
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

def ensure_target_table_exists(client):
    """確保目標表存在 - 使用動態 schema"""
    logger.info("確保目標表存在...")
    
    # 檢查表是否存在
    check_sql = """
    SELECT count() FROM system.tables 
    WHERE database = 'bronze' AND name = 'common_flowable_task_stats'
    """
    exists = client.command(check_sql) > 0
    
    if exists:
        logger.info("✅ 目標表已存在")
        return True
    
    # 動態建立表（從 MSSQL 取得 schema）
    logger.info("目標表不存在，從 MSSQL 動態建立...")
    recreate_target_table(client)
    return True

def recreate_target_table(client):
    """重建目標表（當欄位不符時使用）"""
    logger.info("重建目標表...")
    
    # 刪除舊表
    client.command("DROP TABLE IF EXISTS bronze.common_flowable_task_stats")
    
    # 動態建立表
    create_sql = """
    CREATE TABLE bronze.common_flowable_task_stats
    ENGINE = ReplacingMergeTree(_sync_time)
    ORDER BY (Id)
    SETTINGS allow_nullable_key = 1
    AS SELECT *, 
              '' as _batch_id,
              now64(3) as _sync_time
    FROM jdbc('mssql_master', 'SELECT TOP 0 * FROM APP_SRV_COMMON.dbo.FlowableTaskStats')
    """
    
    client.command(create_sql)
    logger.info("✅ 目標表已重建")

def execute_flowable_batch_sync(client, batch_id: str, start_time: str, end_time: str) -> tuple:
    """執行單個 FlowableTaskStats 批次同步"""
    logger.info(f"同步批次: {batch_id}")
    logger.info(f"時間範圍: {start_time} ~ {end_time}")
    
    # 先清理可能存在的舊資料
    cleanup_sql = f"""
    ALTER TABLE bronze.common_flowable_task_stats DELETE 
    WHERE _batch_id = '{batch_id}'
    """
    
    logger.info("清理舊資料...")
    try:
        client.command(cleanup_sql)
        time.sleep(1)  # 等待清理完成
    except:
        pass  # 忽略清理錯誤
    
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
    SETTINGS 
        max_execution_time = 600,
        send_timeout = 600,
        receive_timeout = 600
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
    
    logger.info(f"✅ 同步完成: {row_count:,} 筆，耗時 {sync_duration:.2f} 秒")
    
    return row_count, sync_duration

def sync_flowable_batches(limit: int = None, recreate: bool = False):
    """同步 FlowableTaskStats 批次"""
    session_controller = SessionController(CLICKHOUSE_CONFIG)
    
    try:
        with session_controller.get_stateless_session() as client:
            # 設定長 timeout
            client.command("SET send_timeout = 600")
            client.command("SET receive_timeout = 600")
            
            # 重建表（如果需要）
            if recreate:
                recreate_target_table(client)
            else:
                ensure_target_table_exists(client)
            
            status_manager = BatchStatusManager(client)
            
            # 取得所有 running 狀態的 FlowableTaskStats 批次
            running_sql = """
            SELECT 
                batch_id,
                watermark_start,
                watermark_end
            FROM bronze.sync_batch_control FINAL
            WHERE table_name = 'FlowableTaskStats' 
              AND status = 'running'
            ORDER BY watermark_start
            """
            
            if limit:
                running_sql += f" LIMIT {limit}"
            
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
                    # 更新狀態為 running
                    status_manager.update_batch_status(
                        'FlowableTaskStats', batch_id, BatchStatus.RUNNING
                    )
                    
                    # 執行同步
                    row_count, duration = execute_flowable_batch_sync(
                        client, batch_id, start_time, end_time
                    )
                    
                    # 更新為完成狀態
                    status_manager.update_batch_status(
                        'FlowableTaskStats', batch_id, BatchStatus.COMPLETED,
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
                            'FlowableTaskStats', batch_id, BatchStatus.FAILED,
                            0, 0, str(e)
                        )
                    except:
                        pass
            
            # 總結
            logger.info(f"\n{'='*80}")
            logger.info(f"FlowableTaskStats 同步完成統計:")
            logger.info(f"成功批次: {success_count}/{len(result.result_rows)}")
            logger.info(f"總同步筆數: {total_rows:,}")
            logger.info(f"{'='*80}")
            
            # 顯示表狀態
            table_count = client.command("SELECT count() FROM bronze.common_flowable_task_stats")
            logger.info(f"📊 表總筆數: {table_count:,}")
            
    except Exception as e:
        logger.error(f"同步過程發生錯誤: {e}")
        raise
    
    finally:
        session_controller.close_all_sessions()

def main():
    """主程式"""
    import argparse
    
    parser = argparse.ArgumentParser(description='同步 FlowableTaskStats 批次')
    parser.add_argument('--limit', type=int, default=None,
                       help='限制同步的批次數量')
    parser.add_argument('--dry-run', action='store_true',
                       help='只顯示要同步的批次，不實際執行')
    parser.add_argument('--recreate', action='store_true',
                       help='重建目標表（當欄位不符時使用）')
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
        WHERE table_name = 'FlowableTaskStats' 
          AND status = 'running'
        ORDER BY watermark_start
        """
        
        if args.limit:
            running_sql += f" LIMIT {args.limit}"
        
        result = client.query(running_sql)
        
        print("[DRY-RUN] FlowableTaskStats 批次清單:")
        print("-" * 60)
        
        for i, (batch_id, start_time, end_time) in enumerate(result.result_rows, 1):
            print(f"{i:3d}. {batch_id}: {start_time} ~ {end_time}")
        
        print(f"\nTotal: {len(result.result_rows)} batches")
        return
    
    try:
        sync_flowable_batches(limit=args.limit, recreate=args.recreate)
    except KeyboardInterrupt:
        logger.info("\n同步被使用者中斷")
        sys.exit(1)
    except Exception as e:
        logger.error(f"同步失敗: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
