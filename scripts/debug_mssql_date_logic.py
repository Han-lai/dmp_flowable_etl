#!/usr/bin/env python3
"""
調試 MSSQL 日期邏輯
檢查為什麼 MSSQL 使用正確日期邏輯後沒有資料
"""
import pymssql
import logging

# 設定 logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# MSSQL 連接設定
MSSQL_SERVER = "twtpesqldv2.delta.corp"
MSSQL_PORT = "1433"
MSSQL_USER = "DMP_APP_SRV"
MSSQL_PASSWORD = "APP@DB#01"
MSSQL_DATABASE = "APP_SRV_BPM"

def get_mssql_connection():
    return pymssql.connect(
        server=MSSQL_SERVER,
        port=MSSQL_PORT,
        user=MSSQL_USER,
        password=MSSQL_PASSWORD,
        database=MSSQL_DATABASE
    )

def check_mssql_date_fields():
    """檢查 MSSQL 中的日期欄位"""
    logger.info("=" * 60)
    logger.info("檢查 MSSQL 日期欄位")
    logger.info("=" * 60)
    
    try:
        conn = get_mssql_connection()
        cursor = conn.cursor()
        
        # 檢查各個日期欄位的資料分布
        date_check_sql = """
        SELECT 
            CONVERT(DATE, hti.START_TIME_) as start_date,
            CONVERT(DATE, hti.CLAIM_TIME_) as claim_date,
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
          AND (
            CONVERT(DATE, hti.START_TIME_) BETWEEN '2025-12-27' AND '2025-12-29'
            OR CONVERT(DATE, hti.CLAIM_TIME_) BETWEEN '2025-12-27' AND '2025-12-29'
            OR CONVERT(DATE, hti.END_TIME_) BETWEEN '2025-12-27' AND '2025-12-29'
          )
        GROUP BY CONVERT(DATE, hti.START_TIME_), CONVERT(DATE, hti.CLAIM_TIME_), CONVERT(DATE, hti.END_TIME_)
        ORDER BY start_date, claim_date, end_date
        """
        
        cursor.execute(date_check_sql)
        results = cursor.fetchall()
        
        logger.info("MSSQL 日期欄位分布:")
        logger.info(f"{'StartDate':<12} {'ClaimDate':<12} {'EndDate':<12} {'Count':<6}")
        logger.info("-" * 50)
        
        if results:
            for row in results:
                start_date, claim_date, end_date, count = row
                logger.info(f"{str(start_date) if start_date else 'NULL':<12} {str(claim_date) if claim_date else 'NULL':<12} {str(end_date) if end_date else 'NULL':<12} {count:<6}")
        else:
            logger.info("無資料")
        
        # 檢查是否有 2025-12-28 的任何資料
        simple_check_sql = """
        SELECT COUNT(*) as total_count
        FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST hi
        INNER JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_plant ON hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ AND var_plant.NAME_ = 'plant'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_factory ON hi.PROC_INST_ID_ = var_factory.PROC_INST_ID_ AND var_factory.NAME_ = 'factory'
        LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST var_lineName ON hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ AND var_lineName.NAME_ = 'lineName'
        WHERE var_plant.TEXT_ = 'WJ2' 
          AND var_factory.TEXT_ = 'NBU' 
          AND var_lineName.TEXT_ = 'E5'
          AND (
            CONVERT(DATE, hti.START_TIME_) = '2025-12-28'
            OR CONVERT(DATE, hti.CLAIM_TIME_) = '2025-12-28'
            OR CONVERT(DATE, hti.END_TIME_) = '2025-12-28'
          )
        """
        
        cursor.execute(simple_check_sql)
        total_count = cursor.fetchone()[0]
        logger.info(f"\nMSSQL 2025-12-28 總任務數 (正確日期邏輯): {total_count}")
        
        # 如果有資料，檢查詳細分布
        if total_count > 0:
            detail_sql = """
            SELECT 
                CASE 
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                    -- 315% 工單號歸類為 V1 (修正：使用 LIKE '315%' 涵蓋所有 315 開頭工單號)
                    WHEN var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
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
              AND (
                CONVERT(DATE, hti.START_TIME_) = '2025-12-28'
                OR CONVERT(DATE, hti.CLAIM_TIME_) = '2025-12-28'
                OR CONVERT(DATE, hti.END_TIME_) = '2025-12-28'
              )
              AND (var_bypass.LONG_ IS NULL OR var_bypass.LONG_ = 0)
            GROUP BY 
                CASE 
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V1%' THEN 'V1'
                    WHEN hti.TASK_DEF_KEY_ LIKE 'V2%' THEN 'V2'
                    WHEN var_moNumber.TEXT_ LIKE '315%' THEN 'V1'
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
            
            cursor.execute(detail_sql)
            results = cursor.fetchall()
            
            logger.info(f"\nMSSQL 詳細分布:")
            logger.info(f"{'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6}")
            logger.info("-" * 35)
            
            for row in results:
                vx_type, total, done, todo, doing = row
                logger.info(f"{vx_type:<4} {total:<6} {done:<6} {todo:<6} {doing:<6}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ MSSQL 檢查失敗: {e}")

def check_mssql_without_bypass():
    """檢查 MSSQL 不包含 bypass 條件的結果"""
    logger.info("=" * 60)
    logger.info("檢查 MSSQL 不包含 bypass 條件")
    logger.info("=" * 60)
    
    try:
        conn = get_mssql_connection()
        cursor = conn.cursor()
        
        # 不包含 bypass 條件的查詢
        no_bypass_sql = """
        SELECT 
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
        WHERE var_plant.TEXT_ = 'WJ2' 
          AND var_factory.TEXT_ = 'NBU' 
          AND var_lineName.TEXT_ = 'E5'
          AND (
            CONVERT(DATE, hti.START_TIME_) = '2025-12-28'
            OR CONVERT(DATE, hti.CLAIM_TIME_) = '2025-12-28'
            OR CONVERT(DATE, hti.END_TIME_) = '2025-12-28'
          )
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
        
        cursor.execute(no_bypass_sql)
        results = cursor.fetchall()
        
        logger.info("MSSQL 結果 (不包含 bypass 條件):")
        logger.info(f"{'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6}")
        logger.info("-" * 35)
        
        if results:
            for row in results:
                vx_type, total, done, todo, doing = row
                logger.info(f"{vx_type:<4} {total:<6} {done:<6} {todo:<6} {doing:<6}")
        else:
            logger.info("無資料")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ MSSQL 檢查失敗: {e}")

def main():
    """主要執行流程"""
    logger.info("調試 MSSQL 日期邏輯")
    
    check_mssql_date_fields()
    check_mssql_without_bypass()
    
    logger.info("=" * 60)
    logger.info("調試完成")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()