#!/usr/bin/env python3
"""
修復錯誤批次 - 無狀態版本
避免 SESSION_IS_LOCKED 問題
"""

import sys
import logging
import time
from datetime import datetime
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

def execute_batch_sync_stateless(client, batch_config: dict, batch_id: str, 
                                start_time: str, end_time: str) -> int:
    """執行批次同步 - 無狀態版本"""
    logger.info(f"執行批次同步: {batch_id}")
    
    try:
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
        
        # 構建同步 SQL
        sync_sql = f"""
        INSERT INTO {target_table}
        SELECT *, 
               '{batch_id}' as _batch_id,
               now64(3) as _extracted_at,
               1 as _sync_version
        FROM jdbc('mssql_master', '
            SELECT * FROM {source_table}
            WHERE {time_column} >= ''{start_time}'' 
              AND {time_column} < ''{end_time}''
              AND {time_column} IS NOT NULL
            ORDER BY {time_column}
        ')
        """
        
        logger.info("執行資料同步...")
        client.command(sync_sql)
        
        # 取得同步筆數
        count_sql = f"""
        SELECT count(*) FROM {target_table} 
        WHERE _batch_id = '{batch_id}'
        """
        row_count = client.command(count_sql)
        
        logger.info(f"✅ 批次同步完成: {row_count:,} 筆資料")
        return row_count
        
    except Exception as e:
        logger.error(f"❌ 批次同步失敗: {e}")
        raise

def fix_batch_stateless(session_controller: SessionController, 
                       status_manager: BatchStatusManager,
                       batch_config: dict):
    """修復單個批次 - 無狀態版本"""
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
            logger.info("🔄 開始重新同步")
            status_manager.update_batch_status(table_name, batch_id, BatchStatus.RUNNING)
            
            # 3. 執行同步
            sync_start_time = time.perf_counter()
            row_count = execute_batch_sync_stateless(
                client, batch_config, batch_id, 
                batch_info.watermark_start, batch_info.watermark_end
            )
            duration = time.perf_counter() - sync_start_time
            
            # 4. 標記為完成
            status_manager.update_batch_status(
                table_name, batch_id, BatchStatus.COMPLETED, 
                row_count, duration
            )
            
            logger.info(f"🎉 批次修復成功: {batch_id}")
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
    parser = argparse.ArgumentParser(description='修復錯誤批次 - 無狀態版本')
    parser.add_argument('--batch-id', type=str, 
                       help='指定要修復的批次 ID')
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
        
        logger.info("🔄 無狀態修復模式：避免 SESSION_IS_LOCKED 問題")
        
        # 修復每個批次
        success_count = 0
        for batch_config in error_batches:
            logger.info(f"\n處理批次: {batch_config['batch_id']}")
            if fix_batch_stateless(session_controller, status_manager, batch_config):
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