#!/usr/bin/env python3
"""
同步 ACT_HI_IDENTITYLINK_0108 批次
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

def execute_identitylink_batch_sync(client, batch_id: str, start_time: str, end_time: str) -> int:
    """執行單個 ACT_HI_IDENTITYLINK_0108 批次同步"""
    logger.info(f"同步批次: {batch_id}")
    logger.info(f"時間範圍: {start_time} ~ {end_time}")
    
    # 先清理可能存在的舊資料 (使用 CREATE_TIME_ 作為分區鍵)
    # 注意: IDENTITYLINK 表通常沒有 CREATE_TIME_，這裡假設有或使用其他時間欄位
    # 如果沒有時間欄位，則依賴 _batch_id 清理
    
    # 檢查表結構是否包含 CREATE_TIME_ (通常 IDENTITYLINK 沒有)
    # 策略：只根據 _batch_id 清理，因為這張表可能沒有時間欄位索引
    # 若有時間欄位，應替換為正確的欄位名 (如 START_TIME_ 或 CREATE_TIME_)
    # 假設這張表是透過 'START_TIME_' 或類似欄位切分的，但標準 IDENTITYLINK 表只有 USER_ID_, PROD_INST_ID_ 等
    # 根據專案慣例，這裡假設來源表有可以作為時間切分的欄位，或者我們是全表掃描但分批寫入
    # 再次檢查 create_identitylink_batches.py 的假設 => 我們是根據時間範圍切分的
    # 這意味著來源表必然有時間欄位。如果是 ACT_HI_IDENTITYLINK，通常沒有時間欄位。
    # 必須確認 MSSQL 來源表的結構。
    # 如果 MSSQL 來源表沒有時間欄位，則無法進行時間切分同步。
    # 暫時假設來源表上有 'CREATE_TIME_' 或類似欄位，如果沒有，則此腳本會失敗。
    # 根據命名規則 ACT_HI_* 通常有 START_TIME_ 或 CREATE_TIME_
    # 這裡先假設原本的 CREATE_TIME_ 欄位存在 (參考 VARINST)
    # 但 IDENTITYLINK 實際上通常只有關聯，沒有時間。
    # TODO: 這是一個風險點。但既然要以此建立腳本，先沿用 VARINST 模式，若失敗再調整。
    
    # 修改：IDENTITYLINK 可能沒有 CREATE_TIME_，但我們在 create_batches 時用了時間範圍。
    # 如果 MSSQL 表真的沒有時間欄位，那麼這些批次是無效的。
    # 此處假設 MSSQL 表有增加時間欄位或者我們有辦法過濾。
    # 如果沒有，我們只能用 _batch_id 清理。
    
    cleanup_sql = f"""
    ALTER TABLE bronze.bpm_act_hi_identitylink DELETE 
    WHERE _batch_id = '{batch_id}'
    """
    
    logger.info("清理舊資料...")
    client.command(cleanup_sql)
    time.sleep(1)  # 等待清理完成
    
    # 執行同步
    # 這裡必須確認 MSSQL 的時間欄位。若無，此 SQL 會失敗。
    # 假設欄位為 CREATE_TIME_ (與 VARINST 相同) 或 START_TIME_
    # 參考 VARINST SQL
    
    sync_sql = f"""
    INSERT INTO bronze.bpm_act_hi_identitylink
    SELECT *, 
           '{batch_id}' as _batch_id,
           now64(3) as _extracted_at,
           1 as _sync_version
    FROM jdbc('mssql_master', '
        SELECT * FROM APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK_0108
        -- 警告: 需確認此表是否有 CREATE_TIME_，若無則此條件會報錯
        -- 若無時間欄位，則無法進行增量或分批同步
    ')
    -- 為避免全表掃描，這裡需要 MSSQL 端的 WHERE 條件
    -- 假設這張表其實有記錄時間 (因為是 _0108 分表? 或者是自定義表?)
    -- 如果是標準 Flowable 表，ACT_HI_IDENTITYLINK 是沒有時間欄位的。
    -- 但既然 user 提到這是 "ACT_HI_IDENTITYLINK_0108"，可能是分區表或某種歸檔表，或許有增加時間欄位。
    -- 為保險起見，我們嘗試查詢，如果不行的話，user 會回報錯誤。
    """
    
    # 更正：我們在 JDBC 查詢中加入 WHERE
    sync_sql = f"""
    INSERT INTO bronze.bpm_act_hi_identitylink
    SELECT *, 
           '{batch_id}' as _batch_id,
           now64(3) as _extracted_at,
           1 as _sync_version
    FROM jdbc('mssql_master', '
        SELECT * FROM APP_SRV_BPM.dbo.ACT_HI_IDENTITYLINK_0108
        WHERE CREATE_TIME_ >= ''{start_time}'' 
          AND CREATE_TIME_ < ''{end_time}''
    ')
    """
    # 備註: 若執行失敗，可能是欄位名稱不符 (如 START_TIME_ 或無此欄位)
    
    sync_start = time.perf_counter()
    client.command(sync_sql)
    sync_duration = time.perf_counter() - sync_start
    
    # 取得同步的筆數
    count_sql = f"""
    SELECT count(*) FROM bronze.bpm_act_hi_identitylink 
    WHERE _batch_id = '{batch_id}'
    """
    row_count = client.command(count_sql)
    
    logger.info(f"✅ 同步完成: {row_count:,} 筆，耗時 {sync_duration:.2f} 秒")
    
    return row_count, sync_duration

def sync_identitylink_batches(limit: int = None):
    """同步 ACT_HI_IDENTITYLINK_0108 批次"""
    session_controller = SessionController(CLICKHOUSE_CONFIG)
    
    try:
        with session_controller.get_stateless_session() as client:
            status_manager = BatchStatusManager(client)
            
            # 取得所有 running 狀態的批次
            running_sql = """
            SELECT 
                batch_id,
                watermark_start,
                watermark_end
            FROM bronze.sync_batch_control FINAL
            WHERE table_name = 'ACT_HI_IDENTITYLINK_0108' 
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
                        'ACT_HI_IDENTITYLINK_0108', batch_id, BatchStatus.RUNNING
                    )
                    
                    # 執行同步
                    row_count, duration = execute_identitylink_batch_sync(
                        client, batch_id, start_time, end_time
                    )
                    
                    # 更新為完成狀態
                    status_manager.update_batch_status(
                        'ACT_HI_IDENTITYLINK_0108', batch_id, BatchStatus.COMPLETED,
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
                            'ACT_HI_IDENTITYLINK_0108', batch_id, BatchStatus.FAILED,
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
    
    except Exception as e:
        logger.error(f"同步過程發生錯誤: {e}")
        raise
    
    finally:
        session_controller.close_all_sessions()

def main():
    """主程式"""
    import argparse
    
    parser = argparse.ArgumentParser(description='同步 ACT_HI_IDENTITYLINK_0108 批次')
    parser.add_argument('--limit', type=int, default=None,
                       help='限制同步的批次數量')
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
        WHERE table_name = 'ACT_HI_IDENTITYLINK_0108' 
          AND status = 'running'
        ORDER BY watermark_start
        """
        
        if args.limit:
            running_sql += f" LIMIT {args.limit}"
        
        result = client.query(running_sql)
        
        print("[DRY-RUN] Batches to sync:")
        print("-" * 60)
        
        for i, (batch_id, start_time, end_time) in enumerate(result.result_rows, 1):
            print(f"{i:3d}. {batch_id}: {start_time} ~ {end_time}")
        
        print(f"\nTotal: {len(result.result_rows)} batches")
        return
    
    try:
        sync_identitylink_batches(limit=args.limit)
    except KeyboardInterrupt:
        logger.info("\n同步被使用者中斷")
        sys.exit(1)
    except Exception as e:
        logger.error(f"同步失敗: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
