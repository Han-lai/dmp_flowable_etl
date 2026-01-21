#!/usr/bin/env python3
"""
修正 2025-12-28 日期邏輯
使用正確的日期條件: START_TIME OR CLAIM_TIME OR END_TIME 在指定日期範圍內
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

def test_correct_date_logic():
    """測試正確的日期邏輯"""
    logger.info("=" * 60)
    logger.info("測試正確的日期邏輯")
    logger.info("=" * 60)
    
    try:
        # ClickHouse 測試
        client = get_clickhouse_client()
        
        # 使用正確的日期邏輯查詢 ClickHouse
        ch_sql = """
        SELECT 
            vx_type,
            count() as total,
            countIf(task_status = 'DONE') as done,
            countIf(task_status = 'TODO') as todo,
            countIf(task_status = 'DOING') as doing
        FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
        WHERE (
            toDate(task_create_time) = '2025-12-28'
            OR toDate(task_claim_time) = '2025-12-28' 
            OR toDate(task_end_time) = '2025-12-28'
        )
          AND plant = 'WJ2' 
          AND factory = 'NBU' 
          AND line = 'E5'
          AND is_excluded = 0
        GROUP BY vx_type
        ORDER BY vx_type
        """
        
        results = client.query(ch_sql).result_rows
        logger.info("ClickHouse 結果 (正確日期邏輯):")
        logger.info(f"{'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6}")
        logger.info("-" * 35)
        
        for row in results:
            vx_type, total, done, todo, doing = row
            logger.info(f"{vx_type:<4} {total:<6} {done:<6} {todo:<6} {doing:<6}")
        
        # MSSQL 測試
        conn = get_mssql_connection()
        cursor = conn.cursor()
        
        # 使用正確的日期邏輯查詢 MSSQL
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
        
        logger.info(f"\nMSSQL 結果 (正確日期邏輯):")
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
        
        logger.info(f"\n期望結果: V1=0, V3=11 (Total=11, Done=8, TODO=3, DOING=0)")
        
    except Exception as e:
        logger.error(f"❌ 測試失敗: {e}")

def regenerate_gold_snapshot_with_correct_logic():
    """使用正確的日期邏輯重新生成 Gold 層快照"""
    logger.info("=" * 60)
    logger.info("重新生成 2025-12-28 Gold 層快照 (正確日期邏輯)")
    logger.info("=" * 60)
    
    try:
        client = get_clickhouse_client()
        
        # 刪除舊快照
        delete_sql = """
        DELETE FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
        WHERE snapshot_date = '2025-12-28'
        """
        client.command(delete_sql)
        
        # 使用正確的日期邏輯生成新快照
        insert_sql = """
        INSERT INTO gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
        SELECT
            '2025-12-28' AS snapshot_date,
            vx_type,
            vx_subtype,
            plant,
            factory,
            line,
            'day' AS time_period_type,
            '2025-12-28' AS time_period_value,
            
            -- 基礎統計（只計算未排除的任務）
            countIf(is_excluded = 0) AS total_task_qty,
            countIf(is_excluded = 0 AND task_status = 'TODO') AS todo_qty,
            countIf(is_excluded = 0 AND task_status = 'DOING') AS doing_qty,
            countIf(is_excluded = 0 AND task_status = 'DONE') AS done_qty,
            countIf(is_excluded = 0 AND task_status IN ('DOING', 'DONE')) AS doing_done_qty,
            countIf(is_excluded = 0 AND task_status IN ('TODO', 'DOING')) AS todo_doing_acc_qty,
            
            -- 計算百分比
            CASE 
                WHEN countIf(is_excluded = 0) > 0 
                THEN round(countIf(is_excluded = 0 AND task_status = 'TODO') * 100.0 / countIf(is_excluded = 0), 2)
                ELSE 0.0
            END AS todo_pct,
            CASE 
                WHEN countIf(is_excluded = 0) > 0 
                THEN round(countIf(is_excluded = 0 AND task_status = 'DOING') * 100.0 / countIf(is_excluded = 0), 2)
                ELSE 0.0
            END AS doing_pct,
            CASE 
                WHEN countIf(is_excluded = 0) > 0 
                THEN round(countIf(is_excluded = 0 AND task_status = 'DONE') * 100.0 / countIf(is_excluded = 0), 2)
                ELSE 0.0
            END AS done_pct,
            CASE 
                WHEN countIf(is_excluded = 0) > 0 
                THEN round(countIf(is_excluded = 0 AND task_status IN ('DOING', 'DONE')) * 100.0 / countIf(is_excluded = 0), 2)
                ELSE 0.0
            END AS doing_done_pct,
            
            toUnixTimestamp64Milli(now64(3)) AS _version,
            now64(3) AS _snapshot_time
            
        FROM silver.FACT_TASK_VX_ATTRIBUTION FINAL
        WHERE (
            toDate(task_create_time) = '2025-12-28'
            OR toDate(task_claim_time) = '2025-12-28' 
            OR toDate(task_end_time) = '2025-12-28'
        )
        GROUP BY 
            vx_type,
            vx_subtype,
            plant,
            factory,
            line
        HAVING countIf(is_excluded = 0) > 0
        """
        
        client.command(insert_sql)
        
        # 檢查結果
        count = client.command("""
            SELECT count() FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT 
            WHERE snapshot_date = '2025-12-28'
        """)
        
        logger.info(f"✅ 2025-12-28 快照重新生成完成，共 {count} 筆記錄")
        
        # 驗證結果
        verify_sql = """
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
        
        results = client.query(verify_sql).result_rows
        logger.info(f"\n驗證結果:")
        logger.info(f"{'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6}")
        logger.info("-" * 35)
        
        for row in results:
            vx_type, total, done, todo, doing = row
            logger.info(f"{vx_type:<4} {total:<6} {done:<6} {todo:<6} {doing:<6}")
        
    except Exception as e:
        logger.error(f"❌ 重新生成失敗: {e}")

def main():
    """主要執行流程"""
    logger.info("修正 2025-12-28 日期邏輯")
    logger.info("使用條件: START_TIME OR CLAIM_TIME OR END_TIME 在指定日期")
    
    # 1. 測試正確的日期邏輯
    test_correct_date_logic()
    
    # 2. 重新生成 Gold 層快照
    regenerate_gold_snapshot_with_correct_logic()
    
    logger.info("=" * 60)
    logger.info("修正完成")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()