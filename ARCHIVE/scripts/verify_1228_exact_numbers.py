#!/usr/bin/env python3
"""
驗證 2025-12-28 WJ2+NBU+E5 的確切數值
期望: V1=0, V3=11 (Total=11, Done=8, TODO=3, DOING=0)
"""
import clickhouse_connect
import pymssql
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

# MSSQL 連接設定
MSSQL_SERVER = "twtpesqldv2.delta.corp"
MSSQL_PORT = "1433"
MSSQL_USER = "DMP_APP_SRV"
MSSQL_PASSWORD = "APP@DB#01"
MSSQL_DATABASE = "APP_SRV_BPM"

def get_clickhouse_client():
    return clickhouse_connect.get_client(**CH_CONFIG)

def get_mssql_connection():
    return pymssql.connect(
        server=MSSQL_SERVER,
        port=MSSQL_PORT,
        user=MSSQL_USER,
        password=MSSQL_PASSWORD,
        database=MSSQL_DATABASE
    )

def check_clickhouse_1228():
    """檢查 ClickHouse 2025-12-28 數據"""
    logger.info("=" * 60)
    logger.info("ClickHouse 2025-12-28 詳細檢查")
    logger.info("=" * 60)
    
    try:
        client = get_clickhouse_client()
        
        # 檢查 Gold 層快照
        gold_sql = """
        SELECT 
            vx_type,
            sum(total_task_qty) as total,
            sum(done_qty) as done,
            sum(todo_qty) as todo,
            sum(doing_qty) as doing
        FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
        WHERE snapshot_date = '2025-12-28'
          AND plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
        GROUP BY vx_type
        ORDER BY vx_type
        """
        
        results = client.query(gold_sql).result_rows
        logger.info("Gold 層快照結果:")
        logger.info(f"{'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6}")
        logger.info("-" * 35)
        
        for row in results:
            vx_type, total, done, todo, doing = row
            logger.info(f"{vx_type:<4} {total:<6} {done:<6} {todo:<6} {doing:<6}")
        
        # 檢查 Silver 層原始數據
        silver_sql = """
        SELECT 
            vx_type,
            count() as total,
            countIf(task_status = 'DONE') as done,
            countIf(task_status = 'TODO') as todo,
            countIf(task_status = 'DOING') as doing,
            countIf(is_excluded = 1) as excluded
        FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
        WHERE task_create_date = '2025-12-28'
          AND plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
        GROUP BY vx_type
        ORDER BY vx_type
        """
        
        results = client.query(silver_sql).result_rows
        logger.info(f"\nSilver 層原始數據:")
        logger.info(f"{'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6} {'Excluded':<8}")
        logger.info("-" * 45)
        
        for row in results:
            vx_type, total, done, todo, doing, excluded = row
            logger.info(f"{vx_type:<4} {total:<6} {done:<6} {todo:<6} {doing:<6} {excluded:<8}")
        
        # 檢查是否有被排除的任務
        excluded_sql = """
        SELECT 
            vx_type,
            exclude_reason,
            count() as count
        FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
        WHERE task_create_date = '2025-12-28'
          AND plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
          AND is_excluded = 1
        GROUP BY vx_type, exclude_reason
        ORDER BY vx_type, exclude_reason
        """
        
        results = client.query(excluded_sql).result_rows
        if results:
            logger.info(f"\n被排除的任務:")
            logger.info(f"{'VX':<4} {'Reason':<15} {'Count':<6}")
            logger.info("-" * 30)
            
            for row in results:
                vx_type, reason, count = row
                logger.info(f"{vx_type:<4} {reason:<15} {count:<6}")
        else:
            logger.info(f"\n無被排除的任務")
            
    except Exception as e:
        logger.error(f"❌ ClickHouse 檢查失敗: {e}")

def check_mssql_1228():
    """檢查 MSSQL 2025-12-28 數據"""
    logger.info("=" * 60)
    logger.info("MSSQL 2025-12-28 詳細檢查")
    logger.info("=" * 60)
    
    try:
        conn = get_mssql_connection()
        cursor = conn.cursor()
        
        # 使用修正後的邏輯檢查 MSSQL
        mssql_sql = """
        SELECT 
            CASE 
                WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                -- 特定 315% 工單號歸類為 V1 (關鍵修正)
                WHEN var_moNumber.TEXT_ IN ('3152600035', '3152600036', '3152600037') THEN 'V1'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
                -- 其他工單號規則
                WHEN var_moNumber.TEXT_ LIKE '196%' 
                     OR var_moNumber.TEXT_ LIKE '199%' 
                     OR var_moNumber.TEXT_ LIKE '200%'
                     OR var_moNumber.TEXT_ LIKE '210%' 
                     OR var_moNumber.TEXT_ LIKE '212%' 
                     OR var_moNumber.TEXT_ LIKE '213%'
                THEN 'V1'
                ELSE LEFT(hti.TASK_DEF_KEY_, 2)
            END as vx_type,
            COUNT(*) as total,
            SUM(CASE WHEN hti.END_TIME_ IS NOT NULL THEN 1 ELSE 0 END) as done,
            SUM(CASE WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NULL THEN 1 ELSE 0 END) as todo,
            SUM(CASE WHEN hti.END_TIME_ IS NULL AND hti.ASSIGNEE_ IS NOT NULL THEN 1 ELSE 0 END) as doing
        FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
        INNER JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_moNumber ON hi.PROC_INST_ID_ = var_moNumber.PROC_INST_ID_ AND var_moNumber.NAME_ = 'moNumber'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_bypass ON hti.ID_ = var_bypass.TASK_ID_ AND var_bypass.NAME_ = 'autoComplete'
        WHERE var_plant.TEXT_ = 'WJ2' 
          AND var_factory.TEXT_ = 'NBU' 
          AND var_lineName.TEXT_ = 'E5'
          AND CONVERT(DATE, hti.START_TIME_) = '2025-12-28'
          AND (var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0)
        GROUP BY 
            CASE 
                WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                WHEN var_moNumber.TEXT_ IN ('3152600035', '3152600036', '3152600037') THEN 'V1'
                WHEN hti.TASK_DEF_KEY_ LIKE 'V3%' THEN 'V3'
                WHEN var_moNumber.TEXT_ LIKE '196%' 
                     OR var_moNumber.TEXT_ LIKE '199%' 
                     OR var_moNumber.TEXT_ LIKE '200%'
                     OR var_moNumber.TEXT_ LIKE '210%' 
                     OR var_moNumber.TEXT_ LIKE '212%' 
                     OR var_moNumber.TEXT_ LIKE '213%'
                THEN 'V1'
                ELSE LEFT(hti.TASK_DEF_KEY_, 2)
            END
        ORDER BY vx_type
        """
        
        cursor.execute(mssql_sql)
        results = cursor.fetchall()
        
        logger.info("MSSQL 結果:")
        logger.info(f"{'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6}")
        logger.info("-" * 35)
        
        if results:
            for row in results:
                vx_type, total, done, todo, doing = row
                logger.info(f"{vx_type:<4} {total:<6} {done:<6} {todo:<6} {doing:<6}")
        else:
            logger.info("無資料")
        
        # 檢查是否有任何 2025-12-28 的資料
        check_sql = """
        SELECT COUNT(*) as total_tasks
        FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
        INNER JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
        WHERE var_plant.TEXT_ = 'WJ2' 
          AND var_factory.TEXT_ = 'NBU' 
          AND var_lineName.TEXT_ = 'E5'
          AND CONVERT(DATE, hti.START_TIME_) = '2025-12-28'
        """
        
        cursor.execute(check_sql)
        total_count = cursor.fetchone()[0]
        logger.info(f"\nMSSQL 2025-12-28 總任務數: {total_count}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ MSSQL 檢查失敗: {e}")

def main():
    """主要執行流程"""
    logger.info("驗證 2025-12-28 WJ2+NBU+E5 確切數值")
    logger.info("期望: V1=0, V3=11 (Total=11, Done=8, TODO=3, DOING=0)")
    
    check_clickhouse_1228()
    check_mssql_1228()
    
    logger.info("=" * 60)
    logger.info("檢查完成")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()