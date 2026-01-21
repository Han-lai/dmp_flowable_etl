#!/usr/bin/env python3
"""
完整修正 V1/V3 歸屬邏輯
從源頭 Silver 層轉換開始，重新生成所有相關資料
"""
import clickhouse_connect
import pymssql
from datetime import datetime
import logging
import subprocess
import sys

# 設定 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ClickHouse 連線設定
CH_CONFIG = {
    'host': 'REDACTED_IP',
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
    """建立 ClickHouse 連線"""
    return clickhouse_connect.get_client(**CH_CONFIG)

def get_mssql_connection():
    """建立 MSSQL 連線"""
    return pymssql.connect(
        server=MSSQL_SERVER,
        port=MSSQL_PORT,
        user=MSSQL_USER,
        password=MSSQL_PASSWORD,
        database=MSSQL_DATABASE
    )

def step1_rebuild_silver_layer():
    """步驟1: 重新轉換 Silver 層"""
    logger.info("=" * 60)
    logger.info("步驟1: 重新轉換 Silver 層")
    logger.info("=" * 60)
    
    try:
        # 執行 Silver 層轉換腳本
        result = subprocess.run([
            sys.executable, 
            'scripts/transform_silver_generic_metrics.py',
            '--table', 'task'
        ], capture_output=True, text=True, cwd='.')
        
        if result.returncode == 0:
            logger.info("✅ Silver 層轉換完成")
            logger.info(result.stdout)
        else:
            logger.error("❌ Silver 層轉換失敗")
            logger.error(result.stderr)
            return False
            
    except Exception as e:
        logger.error(f"❌ Silver 層轉換執行失敗: {e}")
        return False
    
    return True

def step2_regenerate_gold_snapshots():
    """步驟2: 重新生成 Gold 層快照"""
    logger.info("=" * 60)
    logger.info("步驟2: 重新生成 Gold 層快照")
    logger.info("=" * 60)
    
    target_dates = ['2025-12-28', '2025-12-30', '2025-12-31']
    
    try:
        client = get_clickhouse_client()
        
        for date in target_dates:
            logger.info(f"重新生成 {date} 快照...")
            
            # 刪除舊快照
            delete_sql = f"""
            DELETE FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
            WHERE snapshot_date = '{date}'
            """
            client.command(delete_sql)
            
            # 生成新快照
            insert_sql = f"""
            INSERT INTO gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT
            SELECT
                '{date}' AS snapshot_date,
                vx_type,
                vx_subtype,
                plant,
                factory,
                line,
                'day' AS time_period_type,
                '{date}' AS time_period_value,
                
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
            WHERE task_create_date = '{date}'
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
            count = client.command(f"""
                SELECT count() FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT 
                WHERE snapshot_date = '{date}'
            """)
            
            logger.info(f"✅ {date} 快照重新生成完成，共 {count} 筆記錄")
        
        logger.info("✅ 所有 Gold 層快照重新生成完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ Gold 層快照重新生成失敗: {e}")
        return False

def step3_verify_results():
    """步驟3: 驗證修正結果"""
    logger.info("=" * 60)
    logger.info("步驟3: 驗證修正結果")
    logger.info("=" * 60)
    
    try:
        # ClickHouse 驗證
        client = get_clickhouse_client()
        
        logger.info("ClickHouse 驗證結果:")
        for date in ['2025-12-28', '2025-12-30', '2025-12-31']:
            ch_sql = f"""
            SELECT 
                vx_type,
                sum(total_task_qty) as total,
                sum(done_qty) as done,
                sum(todo_qty) as todo,
                sum(doing_qty) as doing
            FROM gold.DAILY_L5_TASK_COMPLETION_SNAPSHOT FINAL
            WHERE snapshot_date = '{date}'
              AND plant = 'WJ2' 
              AND factory = 'NBU' 
              AND line = 'E5'
            GROUP BY vx_type
            ORDER BY vx_type
            """
            
            results = client.query(ch_sql).result_rows
            
            logger.info(f"\n{date} ClickHouse:")
            logger.info(f"{'VX':<4} {'Total':<6} {'Done':<6} {'TODO':<6} {'DOING':<6}")
            logger.info("-" * 35)
            
            for row in results:
                vx_type, total, done, todo, doing = row
                logger.info(f"{vx_type:<4} {total:<6} {done:<6} {todo:<6} {doing:<6}")
        
        # MSSQL 驗證
        conn = get_mssql_connection()
        cursor = conn.cursor()
        
        logger.info(f"\nMSSQL 驗證結果:")
        for date in ['2025-12-28', '2025-12-30', '2025-12-31']:
            mssql_sql = f"""
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
              AND CONVERT(DATE, hti.START_TIME_) = '{date}'
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
            
            logger.info(f"\n{date} MSSQL:")
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
        
        logger.info("✅ 驗證完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ 驗證失敗: {e}")
        return False

def main():
    """主要執行流程"""
    logger.info("=" * 80)
    logger.info("完整修正 V1/V3 歸屬邏輯")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    
    # 執行修正流程
    success = True
    
    # 步驟1: 重新轉換 Silver 層
    if success:
        success = step1_rebuild_silver_layer()
    
    # 步驟2: 重新生成 Gold 層快照
    if success:
        success = step2_regenerate_gold_snapshots()
    
    # 步驟3: 驗證結果
    if success:
        success = step3_verify_results()
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    logger.info("=" * 80)
    if success:
        logger.info("✅ V1/V3 歸屬邏輯修正完成！")
        logger.info("修正內容:")
        logger.info("- 只有特定315%工單號（'3152600035', '3152600036', '3152600037'）歸類為 V1")
        logger.info("- 其他 V3 TaskDefinitionKey 保持 V3")
        logger.info("- TaskDefinitionKey 優先於工單號規則")
    else:
        logger.info("❌ V1/V3 歸屬邏輯修正失敗")
    
    logger.info(f"總耗時: {elapsed:.2f} 秒")
    logger.info("=" * 80)

if __name__ == "__main__":
    main()