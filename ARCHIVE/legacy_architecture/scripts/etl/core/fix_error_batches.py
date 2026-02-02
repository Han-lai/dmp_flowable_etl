#!/usr/bin/env python3
"""
修復錯誤批次
使用新的 SessionController 來處理 SESSION_IS_LOCKED 問題
"""

import sys
import logging
import time
from datetime import datetime
from session_controller import SessionController, SessionRetryHandler
from batch_status_manager import BatchStatusManager, BatchStatus, BatchInfo

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

def check_actual_data_count(client, table_name: str, batch_id: str, 
                           start_time: str, end_time: str, time_column: str) -> int:
    """檢查實際的資料筆數"""
    try:
        # 檢查有 batch_id 的資料
        batch_count_sql = f"""
        SELECT count(*) FROM {table_name}
        WHERE _batch_id = '{batch_id}'
        """
        batch_count = client.command(batch_count_sql)
        
        # 檢查時間範圍內的資料
        time_count_sql = f"""
        SELECT count(*) FROM {table_name}
        WHERE {time_column} >= '{start_time}' AND {time_column} < '{end_time}'
        """
        time_count = client.command(time_count_sql)
        
        logger.info(f"  batch_id 資料筆數: {batch_count:,}")
        logger.info(f"  時間範圍資料筆數: {time_count:,}")
        
        return max(batch_count, time_count)
        
    except Exception as e:
        logger.error(f"❌ 檢查資料筆數失敗: {e}")
        return 0

def get_expected_count_from_mssql(client, source_table: str, start_time: str, 
                                 end_time: str, time_column: str) -> int:
    """從 MSSQL 取得預期筆數（使用較短的超時時間）"""
    try:
        count_sql = f"""
        SELECT count(*) FROM jdbc('mssql_master', '
            SELECT 1 FROM {source_table}
            WHERE {time_column} >= ''{start_time}'' 
              AND {time_column} < ''{end_time}''
        ')
        """
        
        expected_count = client.command(count_sql)
        logger.info(f"  MSSQL 預期筆數: {expected_count:,}")
        return expected_count
        
    except Exception as e:
        if "timeout" in str(e).lower():
            logger.warning(f"⚠️ MSSQL 查詢超時，跳過筆數驗證: {e}")
            return -1  # 表示無法驗證
        else:
            logger.error(f"❌ 取得 MSSQL 筆數失敗: {e}")
            return 0

def cleanup_batch_data(client, table_name: str, batch_id: str, 
                      start_time: str, end_time: str, time_column: str):
    """清理批次資料"""
    logger.info(f"清理批次資料: {batch_id}")
    
    try:
        # 記錄清理前的資料筆數
        before_count = client.command(f"SELECT count(*) FROM {table_name}")
        
        # 精確清理 - 使用雙重條件確保安全
        cleanup_sql = f"""
        ALTER TABLE {table_name} DELETE 
        WHERE _batch_id = '{batch_id}'
           OR ({time_column} >= '{start_time}' AND {time_column} < '{end_time}')
        """
        
        client.command(cleanup_sql)
        
        # 等待清理完成
        time.sleep(2)
        
        # 驗證清理結果
        after_count = client.command(f"SELECT count(*) FROM {table_name}")
        cleaned_count = before_count - after_count
        
        logger.info(f"✅ 批次資料清理完成，刪除 {cleaned_count} 筆資料")
        return cleaned_count
        
    except Exception as e:
        logger.error(f"❌ 清理批次資料失敗: {e}")
        raise

def execute_batch_sync(client, batch_config: dict, batch_id: str, 
                      start_time: str, end_time: str) -> int:
    """執行批次同步"""
    logger.info(f"執行批次同步: {batch_id}")
    
    try:
        source_table = batch_config['source_table']
        target_table = batch_config['target_table']
        time_column = batch_config['time_column']
        
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
        
        # 執行同步
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

def fix_batch(session_controller: SessionController, status_manager: BatchStatusManager,
              batch_config: dict, force_retry: bool = False):
    """修復單個批次"""
    batch_id = batch_config['batch_id']
    table_name = batch_config['table_name']
    target_table = batch_config['target_table']
    source_table = batch_config['source_table']
    time_column = batch_config['time_column']
    
    logger.info(f"\n{'='*60}")
    logger.info(f"修復批次: {batch_id}")
    logger.info(f"{'='*60}")
    
    start_time = None
    end_time = None
    
    try:
        # 先用無狀態會話取得批次資訊
        with session_controller.get_stateless_session() as client:
            # 1. 檢查批次狀態
            batch_info = status_manager.get_batch_info(table_name, batch_id)
            
            if batch_info:
                logger.info(f"✅ 找到批次記錄:")
                logger.info(f"  狀態: {batch_info.status.value}")
                logger.info(f"  時間範圍: {batch_info.watermark_start} ~ {batch_info.watermark_end}")
                logger.info(f"  記錄筆數: {batch_info.row_count:,}")
                
                start_time = batch_info.watermark_start
                end_time = batch_info.watermark_end
                
            else:
                logger.error(f"❌ 未找到批次記錄: {batch_id}")
                return False
            
            # 2. 檢查實際資料
            actual_count = check_actual_data_count(client, target_table, batch_id, 
                                                 start_time, end_time, time_column)
        
        # 使用新的會話進行同步操作
        with session_controller.get_session(f"sync_{batch_id}") as sync_client:
            
            # 3. 檢查預期資料（如果不超時的話）
            expected_count = get_expected_count_from_mssql(sync_client, source_table, 
                                                         start_time, end_time, time_column)
            # 4. 決定處理方式
            if not force_retry and actual_count > 0 and expected_count > 0 and actual_count == expected_count:
                # 資料完整，標記為完成
                logger.info("🎯 資料完整，標記為 COMPLETED")
                status_manager.update_batch_status(table_name, batch_id, BatchStatus.COMPLETED, actual_count)
                return True
                
            elif actual_count == 0 or force_retry:
                # 無資料或強制重試，直接重新執行
                logger.info("🔄 重新執行批次同步")
                
                # 更新狀態為 RUNNING
                status_manager.update_batch_status(table_name, batch_id, BatchStatus.RUNNING)
                
                # 執行同步
                sync_start_time = time.perf_counter()
                row_count = execute_batch_sync(sync_client, batch_config, batch_id, start_time, end_time)
                duration = time.perf_counter() - sync_start_time
                
                # 標記為完成
                status_manager.update_batch_status(table_name, batch_id, BatchStatus.COMPLETED, 
                                                 row_count, duration)
                return True
                
            else:
                # 部分資料，清理後重新執行
                logger.info("⚠️ 資料不完整，清理後重新執行")
                
                # 清理資料
                cleanup_batch_data(sync_client, target_table, batch_id, start_time, end_time, time_column)
                
                # 更新狀態為 RUNNING
                status_manager.update_batch_status(table_name, batch_id, BatchStatus.RUNNING)
                
                # 重新執行同步
                sync_start_time = time.perf_counter()
                row_count = execute_batch_sync(sync_client, batch_config, batch_id, start_time, end_time)
                duration = time.perf_counter() - sync_start_time
                
                # 標記為完成
                status_manager.update_batch_status(table_name, batch_id, BatchStatus.COMPLETED, 
                                                 row_count, duration)
                return True
    
    except Exception as e:
        logger.error(f"❌ 修復批次失敗: {e}")
        
        # 標記為失敗
        if start_time and end_time:
            status_manager.update_batch_status(table_name, batch_id, BatchStatus.FAILED, 
                                             0, 0, str(e))
        return False

def main():
    """主程式"""
    import argparse
    
    # 解析命令列參數
    parser = argparse.ArgumentParser(description='修復錯誤批次')
    parser.add_argument('--force-resync', action='store_true', 
                       help='強制重新同步，不管現有資料狀態')
    parser.add_argument('--batch-id', type=str, 
                       help='指定要修復的批次 ID')
    args = parser.parse_args()
    
    try:
        # 創建控制器
        session_controller = SessionController(CLICKHOUSE_CONFIG)
        
        # 使用無狀態會話創建狀態管理器（避免衝突）
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
        
        # 顯示執行模式
        if args.force_resync:
            logger.info("🔄 強制重新同步模式：將清理現有資料並重新從 MSSQL 同步")
        else:
            logger.info("🔍 智能修復模式：將檢查資料狀態後決定處理方式")
        
        # 修復每個批次
        success_count = 0
        for batch_config in error_batches:
            logger.info(f"\n處理批次: {batch_config['batch_id']}")
            if fix_batch(session_controller, status_manager, batch_config, force_retry=args.force_resync):
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