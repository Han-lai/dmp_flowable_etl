#!/usr/bin/env python3
"""
修復錯誤批次 - 優化版本
使用分批插入避免超時問題
"""

import sys
import logging
import time
from datetime import datetime, timedelta
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
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

def parse_datetime(dt_str: str) -> datetime:
    """解析日期時間字串"""
    return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")

def format_datetime(dt: datetime) -> str:
    """格式化日期時間"""
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def split_time_range(start_str: str, end_str: str, chunk_hours: int = 6) -> list:
    """將時間範圍分割成小塊"""
    start_dt = parse_datetime(start_str)
    end_dt = parse_datetime(end_str)
    
    chunks = []
    current_dt = start_dt
    
    while current_dt < end_dt:
        chunk_end = min(current_dt + timedelta(hours=chunk_hours), end_dt)
        chunks.append({
            'start': format_datetime(current_dt),
            'end': format_datetime(chunk_end)
        })
        current_dt = chunk_end
    
    return chunks

def execute_batch_sync_chunked(client, batch_config: dict, batch_id: str, 
                              start_time: str, end_time: str, chunk_hours: int = 6) -> int:
    """執行分塊批次同步"""
    logger.info(f"執行分塊批次同步: {batch_id}")
    
    source_table = batch_config['source_table']
    target_table = batch_config['target_table']
    time_column = batch_config['time_column']
    
    # 先清理可能存在的舊資料
    cleanup_sql = f"""
    ALTER TABLE {target_table} DELETE 
    WHERE _batch_id = '{batch_id}'
       OR ({time_column} >= '{start_time}' AND {time_column} < '{end_time}')
    """
    
    logger.info("清理舊資料...")
    client.command(cleanup_sql)
    time.sleep(2)  # 等待清理完成
    
    # 分割時間範圍
    chunks = split_time_range(start_time, end_time, chunk_hours=chunk_hours)
    logger.info(f"分割為 {len(chunks)} 個時間塊，每塊 {chunk_hours} 小時")
    
    total_rows = 0
    
    for i, chunk in enumerate(chunks, 1):
        logger.info(f"處理第 {i}/{len(chunks)} 塊: {chunk['start']} ~ {chunk['end']}")
        
        try:
            # 構建分塊同步 SQL
            chunk_sql = f"""
            INSERT INTO {target_table}
            SELECT *, 
                   '{batch_id}' as _batch_id,
                   now64(3) as _extracted_at,
                   1 as _sync_version
            FROM jdbc('mssql_master', '
                SELECT * FROM {source_table}
                WHERE {time_column} >= ''{chunk['start']}'' 
                  AND {time_column} < ''{chunk['end']}''
                  AND {time_column} IS NOT NULL
                ORDER BY {time_column}
            ')
            """
            
            chunk_start = time.perf_counter()
            client.command(chunk_sql)
            chunk_duration = time.perf_counter() - chunk_start
            
            # 取得這塊的筆數
            count_sql = f"""
            SELECT count(*) FROM {target_table} 
            WHERE _batch_id = '{batch_id}'
              AND {time_column} >= '{chunk['start']}' 
              AND {time_column} < '{chunk['end']}'
            """
            chunk_rows = client.command(count_sql)
            total_rows += chunk_rows
            
            logger.info(f"✅ 第 {i} 塊完成: {chunk_rows:,} 筆，耗時 {chunk_duration:.2f} 秒")
            
        except Exception as e:
            logger.error(f"❌ 第 {i} 塊失敗: {e}")
            raise
    
    logger.info(f"✅ 分塊同步完成: 總計 {total_rows:,} 筆資料")
    return total_rows

def fix_batch_optimized(session_controller: SessionController, 
                       status_manager: BatchStatusManager,
                       batch_config: dict, chunk_hours: int = 6):
    """修復單個批次 - 優化版本"""
    batch_id = batch_config['batch_id']
    table_name = batch_config['table_name']
    
    logger.info(f"\n{'='*60}")
    logger.info(f"修復批次: {batch_id}")
    logger.info(f"{'='*60}")
    
    try:
        # 使用無狀態會話
        with session_controller.get_stateless_session() as client:
            
            # 1. 檢查批次狀態
            batch_info = status_manager.get_batch_info(table_name, batch_id)
            
            if not batch_info:
                logger.error(f"❌ 未找到批次記錄: {batch_id}")
                return False
            
            logger.info(f"✅ 找到批次記錄:")
            logger.info(f"  狀態: {batch_info.status.value}")
            logger.info(f"  時間範圍: {batch_info.watermark_start} ~ {batch_info.watermark_end}")
            logger.info(f"  記錄筆數: {batch_info.row_count:,}")
            
            # 2. 更新狀態為 RUNNING
            logger.info("🔄 開始分塊重新同步")
            status_manager.update_batch_status(table_name, batch_id, BatchStatus.RUNNING)
            
            # 3. 執行分塊同步
            sync_start_time = time.perf_counter()
            row_count = execute_batch_sync_chunked(
                client, batch_config, batch_id, 
                batch_info.watermark_start, batch_info.watermark_end,
                chunk_hours
            )
            duration = time.perf_counter() - sync_start_time
            
            # 4. 標記為完成
            status_manager.update_batch_status(
                table_name, batch_id, BatchStatus.COMPLETED, 
                row_count, duration
            )
            
            logger.info(f"🎉 批次修復成功: {batch_id}")
            logger.info(f"📊 總耗時: {duration:.2f} 秒，平均速度: {row_count/duration:,.0f} 筆/秒")
            return True
    
    except Exception as e:
        logger.error(f"❌ 修復批次失敗: {e}")
        
        # 標記為失敗
        try:
            status_manager.update_batch_status(table_name, batch_id, BatchStatus.FAILED, 0, 0, str(e))
        except:
            pass
        
        return False

def main():
    """主程式"""
    import argparse
    
    # 解析命令列參數
    parser = argparse.ArgumentParser(description='修復錯誤批次 - 優化版本')
    parser.add_argument('--batch-id', type=str, 
                       help='指定要修復的批次 ID')
    parser.add_argument('--chunk-hours', type=int, default=6,
                       help='每個時間塊的小時數 (預設: 6)')
    args = parser.parse_args()
    
    try:
        # 創建控制器
        session_controller = SessionController(CLICKHOUSE_CONFIG)
        
        # 使用無狀態會話創建狀態管理器
        with session_controller.get_stateless_session() as client:
            status_manager = BatchStatusManager(client)
        
        # 定義要修復的錯誤批次
        error_batches = [
            {
                'batch_id': 'ACT_HI_TASKINST_0108_20251213_151854',
                'table_name': 'ACT_HI_TASKINST_0108',
                'target_table': 'bronze.bpm_act_hi_taskinst',
                'source_table': 'APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108',
                'time_column': 'START_TIME_'
            },
            {
                'batch_id': 'ACT_HI_IDENTITYLINK_0108_20251013_151855',
                'table_name': 'ACT_HI_IDENTITYLINK_0108',
                'target_table': 'bronze.bpm_act_hi_identitylink',
                'source_table': 'APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK_0108',
                'time_column': 'CREATE_TIME_'
            }
        ]
        
        # 如果指定了特定批次，只處理該批次
        if args.batch_id:
            error_batches = [batch for batch in error_batches if batch['batch_id'] == args.batch_id]
            if not error_batches:
                logger.error(f"❌ 找不到批次 ID: {args.batch_id}")
                sys.exit(1)
        
        logger.info(f"🔄 分塊修復模式：每塊 {args.chunk_hours} 小時，避免超時問題")
        
        # 修復每個批次
        success_count = 0
        for batch_config in error_batches:
            logger.info(f"\n處理批次: {batch_config['batch_id']}")
            if fix_batch_optimized(session_controller, status_manager, batch_config, args.chunk_hours):
                success_count += 1
        
        # 總結
        logger.info(f"\n{'='*60}")
        logger.info(f"修復完成: {success_count}/{len(error_batches)} 個批次成功")
        logger.info(f"{'='*60}")
        
        if success_count == len(error_batches):
            logger.info("🎉 所有批次修復成功！")
        else:
            logger.warning("⚠️ 部分批次修復失敗，請檢查日誌")
        
    except Exception as e:
        logger.error(f"修復過程發生錯誤: {e}")
        sys.exit(1)
    
    finally:
        # 清理所有會話
        if 'session_controller' in locals():
            session_controller.close_all_sessions()

if __name__ == "__main__":
    main()