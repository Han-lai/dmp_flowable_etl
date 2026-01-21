#!/usr/bin/env python3
"""
調試 2025-12-28 缺少的1筆任務
期望 V3=11，實際 V3=10，缺少1筆
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

def check_clickhouse_all_tasks():
    """檢查 ClickHouse 中所有 2025-12-28 WJ2+NBU+E5 的任務"""
    logger.info("=" * 60)
    logger.info("ClickHouse 所有任務檢查 (包含排除的)")
    logger.info("=" * 60)
    
    try:
        client = get_clickhouse_client()
        
        # 檢查所有任務（包含被排除的）
        all_tasks_sql = """
        SELECT 
            vx_type,
            task_status,
            is_excluded,
            exclude_reason,
            count() as count
        FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
        WHERE task_create_date = '2025-12-28'
          AND plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
        GROUP BY vx_type, task_status, is_excluded, exclude_reason
        ORDER BY vx_type, task_status, is_excluded
        """
        
        results = client.query(all_tasks_sql).result_rows
        logger.info("所有任務分布:")
        logger.info(f"{'VX':<4} {'Status':<8} {'Excluded':<8} {'Reason':<15} {'Count':<6}")
        logger.info("-" * 50)
        
        total_tasks = 0
        excluded_tasks = 0
        
        for row in results:
            vx_type, status, excluded, reason, count = row
            total_tasks += count
            if excluded:
                excluded_tasks += count
            logger.info(f"{vx_type:<4} {status:<8} {excluded:<8} {reason or 'None':<15} {count:<6}")
        
        logger.info(f"\n總任務數: {total_tasks}")
        logger.info(f"被排除任務數: {excluded_tasks}")
        logger.info(f"有效任務數: {total_tasks - excluded_tasks}")
        
    except Exception as e:
        logger.error(f"❌ ClickHouse 檢查失敗: {e}")

def check_mssql_date_range():
    """檢查 MSSQL 中 2025-12-28 前後的資料"""
    logger.info("=" * 60)
    logger.info("MSSQL 日期範圍檢查")
    logger.info("=" * 60)
    
    try:
        conn = get_mssql_connection()
        cursor = conn.cursor()
        
        # 檢查 2025-12-27 到 2025-12-29 的資料
        date_range_sql = """
        SELECT 
            CONVERT(DATE, hti.START_TIME_) as task_date,
            COUNT(*) as total_tasks
        FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
        INNER JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
        WHERE var_plant.TEXT_ = 'WJ2' 
          AND var_factory.TEXT_ = 'NBU' 
          AND var_lineName.TEXT_ = 'E5'
          AND CONVERT(DATE, hti.START_TIME_) BETWEEN '2025-12-27' AND '2025-12-29'
        GROUP BY CONVERT(DATE, hti.START_TIME_)
        ORDER BY task_date
        """
        
        cursor.execute(date_range_sql)
        results = cursor.fetchall()
        
        logger.info("MSSQL 日期範圍資料:")
        logger.info(f"{'Date':<12} {'Tasks':<6}")
        logger.info("-" * 20)
        
        if results:
            for row in results:
                date, count = row
                logger.info(f"{date:<12} {count:<6}")
        else:
            logger.info("無資料")
        
        # 檢查是否使用了不同的日期欄位
        alt_date_sql = """
        SELECT 
            CONVERT(DATE, hti.CREATE_TIME_) as create_date,
            CONVERT(DATE, hti.START_TIME_) as start_date,
            CONVERT(DATE, hti.END_TIME_) as end_date,
            COUNT(*) as count
        FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
        INNER JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
        WHERE var_plant.TEXT_ = 'WJ2' 
          AND var_factory.TEXT_ = 'NBU' 
          AND var_lineName.TEXT_ = 'E5'
          AND (CONVERT(DATE, hti.CREATE_TIME_) = '2025-12-28' 
               OR CONVERT(DATE, hti.START_TIME_) = '2025-12-28'
               OR CONVERT(DATE, hti.END_TIME_) = '2025-12-28')
        GROUP BY CONVERT(DATE, hti.CREATE_TIME_), CONVERT(DATE, hti.START_TIME_), CONVERT(DATE, hti.END_TIME_)
        ORDER BY create_date, start_date, end_date
        """
        
        cursor.execute(alt_date_sql)
        results = cursor.fetchall()
        
        logger.info(f"\nMSSQL 不同日期欄位檢查:")
        logger.info(f"{'Create':<12} {'Start':<12} {'End':<12} {'Count':<6}")
        logger.info("-" * 45)
        
        if results:
            for row in results:
                create_date, start_date, end_date, count = row
                logger.info(f"{str(create_date) if create_date else 'NULL':<12} {str(start_date) if start_date else 'NULL':<12} {str(end_date) if end_date else 'NULL':<12} {count:<6}")
        else:
            logger.info("無資料")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ MSSQL 檢查失敗: {e}")

def check_clickhouse_date_mapping():
    """檢查 ClickHouse 中的日期對應"""
    logger.info("=" * 60)
    logger.info("ClickHouse 日期對應檢查")
    logger.info("=" * 60)
    
    try:
        client = get_clickhouse_client()
        
        # 檢查任務的不同日期欄位
        date_mapping_sql = """
        SELECT 
            task_create_date,
            toDate(task_create_time) as create_time_date,
            task_end_date,
            count() as count
        FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
        WHERE plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
          AND (task_create_date = '2025-12-28' 
               OR toDate(task_create_time) = '2025-12-28'
               OR task_end_date = '2025-12-28')
        GROUP BY task_create_date, toDate(task_create_time), task_end_date
        ORDER BY task_create_date, create_time_date, task_end_date
        """
        
        results = client.query(date_mapping_sql).result_rows
        logger.info("ClickHouse 日期對應:")
        logger.info(f"{'CreateDate':<12} {'CreateTime':<12} {'EndDate':<12} {'Count':<6}")
        logger.info("-" * 45)
        
        for row in results:
            create_date, create_time_date, end_date, count = row
            logger.info(f"{str(create_date):<12} {str(create_time_date):<12} {str(end_date) if end_date else 'NULL':<12} {count:<6}")
        
    except Exception as e:
        logger.error(f"❌ ClickHouse 日期檢查失敗: {e}")

def main():
    """主要執行流程"""
    logger.info("調試 2025-12-28 缺少的1筆任務")
    logger.info("期望 V3=11，實際 V3=10")
    
    check_clickhouse_all_tasks()
    check_mssql_date_range()
    check_clickhouse_date_mapping()
    
    logger.info("=" * 60)
    logger.info("調試完成")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()