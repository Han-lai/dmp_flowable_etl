#!/usr/bin/env python3
"""
確認 2025-12-28 期望結果的日期定義
檢查是基於創建日期還是結束日期
"""
import clickhouse_connect
import logging

# 設定 logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ClickHouse 連線設定
CH_CONFIG = {
    'host': '10.136.218.207',
    'port': 8121,
    'username': 'default',
    'password': 'default'
}

def get_clickhouse_client():
    return clickhouse_connect.get_client(**CH_CONFIG)

def check_different_date_criteria():
    """檢查不同日期條件的結果"""
    logger.info("=" * 60)
    logger.info("不同日期條件的結果比較")
    logger.info("=" * 60)
    
    try:
        client = get_clickhouse_client()
        
        # 方案1: 基於創建日期 (目前使用)
        create_date_sql = """
        SELECT 
            vx_type,
            count() as total,
            countIf(task_status = 'DONE') as done,
            countIf(task_status = 'TODO') as todo,
            countIf(task_status = 'DOING') as doing
        FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
        WHERE task_create_date = '2025-12-28'
          AND plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
          AND is_excluded = 0
        GROUP BY vx_type
        ORDER BY vx_type
        """
        
        results = client.query(create_date_sql).result_rows
        logger.info("方案1: 基於創建日期 (task_create_date = '2025-12-28')")
        logger.info(f"{'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6}")
        logger.info("-" * 35)
        
        for row in results:
            vx_type, total, done, todo, doing = row
            logger.info(f"{vx_type:<4} {total:<6} {done:<6} {todo:<6} {doing:<6}")
        
        # 方案2: 基於結束日期
        end_date_sql = """
        SELECT 
            vx_type,
            count() as total,
            countIf(task_status = 'DONE') as done,
            countIf(task_status = 'TODO') as todo,
            countIf(task_status = 'DOING') as doing
        FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
        WHERE task_end_date = '2025-12-28'
          AND plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
          AND is_excluded = 0
        GROUP BY vx_type
        ORDER BY vx_type
        """
        
        results = client.query(end_date_sql).result_rows
        logger.info(f"\n方案2: 基於結束日期 (task_end_date = '2025-12-28')")
        logger.info(f"{'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6}")
        logger.info("-" * 35)
        
        for row in results:
            vx_type, total, done, todo, doing = row
            logger.info(f"{vx_type:<4} {total:<6} {done:<6} {todo:<6} {doing:<6}")
        
        # 方案3: 基於創建時間日期
        create_time_sql = """
        SELECT 
            vx_type,
            count() as total,
            countIf(task_status = 'DONE') as done,
            countIf(task_status = 'TODO') as todo,
            countIf(task_status = 'DOING') as doing
        FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
        WHERE toDate(task_create_time) = '2025-12-28'
          AND plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
          AND is_excluded = 0
        GROUP BY vx_type
        ORDER BY vx_type
        """
        
        results = client.query(create_time_sql).result_rows
        logger.info(f"\n方案3: 基於創建時間日期 (toDate(task_create_time) = '2025-12-28')")
        logger.info(f"{'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6}")
        logger.info("-" * 35)
        
        for row in results:
            vx_type, total, done, todo, doing = row
            logger.info(f"{vx_type:<4} {total:<6} {done:<6} {todo:<6} {doing:<6}")
        
        # 方案4: 任何日期欄位包含 2025-12-28
        any_date_sql = """
        SELECT 
            vx_type,
            count() as total,
            countIf(task_status = 'DONE') as done,
            countIf(task_status = 'TODO') as todo,
            countIf(task_status = 'DOING') as doing
        FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
        WHERE (task_create_date = '2025-12-28' 
               OR toDate(task_create_time) = '2025-12-28'
               OR task_end_date = '2025-12-28')
          AND plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
          AND is_excluded = 0
        GROUP BY vx_type
        ORDER BY vx_type
        """
        
        results = client.query(any_date_sql).result_rows
        logger.info(f"\n方案4: 任何日期欄位包含 2025-12-28")
        logger.info(f"{'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6}")
        logger.info("-" * 35)
        
        for row in results:
            vx_type, total, done, todo, doing = row
            logger.info(f"{vx_type:<4} {total:<6} {done:<6} {todo:<6} {doing:<6}")
        
        logger.info(f"\n期望結果: V1=0, V3=11 (Total=11, Done=8, TODO=3, DOING=0)")
        logger.info(f"哪個方案最接近期望結果？")
        
    except Exception as e:
        logger.error(f"❌ 檢查失敗: {e}")

def main():
    """主要執行流程"""
    logger.info("確認 2025-12-28 期望結果的日期定義")
    
    check_different_date_criteria()
    
    logger.info("=" * 60)
    logger.info("檢查完成")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()