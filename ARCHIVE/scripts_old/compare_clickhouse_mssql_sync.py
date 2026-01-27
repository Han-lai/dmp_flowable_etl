#!/usr/bin/env python3
"""
比較 ClickHouse 和 MSSQL 的資料同步狀況
檢查為什麼 ClickHouse 有 2025-12-28 資料但 MSSQL 沒有
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

def compare_date_ranges():
    """比較 ClickHouse 和 MSSQL 的日期範圍"""
    logger.info("=" * 60)
    logger.info("比較 ClickHouse 和 MSSQL 日期範圍")
    logger.info("=" * 60)
    
    try:
        # ClickHouse 日期範圍
        client = get_clickhouse_client()
        
        ch_sql = """
        SELECT 
            toDate(task_create_time) as date,
            count() as count
        FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
        WHERE plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
          AND toDate(task_create_time) BETWEEN '2025-12-27' AND '2025-12-30'
        GROUP BY toDate(task_create_time)
        ORDER BY date
        """
        
        results = client.query(ch_sql).result_rows
        logger.info("ClickHouse 日期分布 (基於 task_create_time):")
        logger.info(f"{'Date':<12} {'Count':<6}")
        logger.info("-" * 20)
        
        for row in results:
            date, count = row
            logger.info(f"{str(date):<12} {count:<6}")
        
        # MSSQL 日期範圍
        conn = get_mssql_connection()
        cursor = conn.cursor()
        
        mssql_sql = """
        SELECT 
            CONVERT(DATE, hti.START_TIME_) as date,
            COUNT(*) as count
        FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
        INNER JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
        WHERE var_plant.TEXT_ = 'WJ2' 
          AND var_factory.TEXT_ = 'NBU' 
          AND var_lineName.TEXT_ = 'E5'
          AND (
              hti.START_TIME_ BETWEEN '2025-12-27 00:00:00' AND '2025-12-30 23:59:59'
              OR hti.CLAIM_TIME_ BETWEEN '2025-12-27 00:00:00' AND '2025-12-30 23:59:59'
              OR hti.END_TIME_ BETWEEN '2025-12-27 00:00:00' AND '2025-12-30 23:59:59'
          )
        GROUP BY CONVERT(DATE, hti.START_TIME_)
        ORDER BY date
        """
        
        cursor.execute(mssql_sql)
        results = cursor.fetchall()
        
        logger.info(f"\nMSSQL 日期分布 (基於 START_TIME):")
        logger.info(f"{'Date':<12} {'Count':<6}")
        logger.info("-" * 20)
        
        if results:
            for row in results:
                date, count = row
                logger.info(f"{str(date):<12} {count:<6}")
        else:
            logger.info("無資料")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ 比較失敗: {e}")

def check_data_source_difference():
    """檢查資料來源差異"""
    logger.info("=" * 60)
    logger.info("檢查資料來源差異")
    logger.info("=" * 60)
    
    try:
        # 檢查 ClickHouse Bronze 層資料
        client = get_clickhouse_client()
        
        bronze_sql = """
        SELECT 
            toDate(TaskCreateTime) as date,
            count() as count
        FROM bronze.common_flowable_task_stats
        WHERE Plant = 'WJ2' 
          AND Factory = 'NBU' 
          AND Line = 'E5'
          AND toDate(TaskCreateTime) BETWEEN '2025-12-27' AND '2025-12-30'
        GROUP BY toDate(TaskCreateTime)
        ORDER BY date
        """
        
        results = client.query(bronze_sql).result_rows
        logger.info("ClickHouse Bronze 層日期分布:")
        logger.info(f"{'Date':<12} {'Count':<6}")
        logger.info("-" * 20)
        
        for row in results:
            date, count = row
            logger.info(f"{str(date):<12} {count:<6}")
        
        # 檢查 ClickHouse 中是否有 2025-12-28 的具體任務
        detail_sql = """
        SELECT 
            task_id,
            task_create_date,
            toDate(task_create_time) as create_time_date,
            task_end_date,
            vx_type,
            task_status
        FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
        WHERE plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
          AND (
            toDate(task_create_time) = '2025-12-28'
            OR toDate(task_claim_time) = '2025-12-28' 
            OR toDate(task_end_time) = '2025-12-28'
          )
        LIMIT 5
        """
        
        results = client.query(detail_sql).result_rows
        logger.info(f"\nClickHouse 2025-12-28 任務樣本:")
        logger.info(f"{'TaskId':<15} {'CreateDate':<12} {'CreateTime':<12} {'EndDate':<12} {'VX':<4} {'Status':<8}")
        logger.info("-" * 70)
        
        for row in results:
            task_id, create_date, create_time_date, end_date, vx_type, status = row
            logger.info(f"{task_id[:15]:<15} {str(create_date):<12} {str(create_time_date):<12} {str(end_date) if end_date else 'NULL':<12} {vx_type:<4} {status:<8}")
        
    except Exception as e:
        logger.error(f"❌ 檢查失敗: {e}")

def main():
    """主要執行流程"""
    logger.info("比較 ClickHouse 和 MSSQL 資料同步狀況")
    
    compare_date_ranges()
    check_data_source_difference()
    
    logger.info("=" * 60)
    logger.info("結論:")
    logger.info("ClickHouse 有 2025-12-28 資料，MSSQL 沒有")
    logger.info("這表示兩個資料源可能不同步或來源不同")
    logger.info("期望結果可能是基於 ClickHouse 的資料")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()