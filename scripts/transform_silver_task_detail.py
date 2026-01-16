#!/usr/bin/env python3
"""
Silver 層轉換：任務明細寬表
等價於 MSSQL Reference SQL
"""
import time
import logging
import clickhouse_connect

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default"
}

def connect():
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    client.command("SELECT 1")
    logger.info("ClickHouse 連線成功")
    return client

def create_tables(client):
    """建立 Silver 層表"""
    logger.info("建立 Silver 層表...")
    
    # 讀取 DDL
    with open("sql/10_create_silver_task_detail.sql", "r", encoding="utf-8") as f:
        ddl = f.read()
    
    # 分割並執行每個 statement
    for stmt in ddl.split(";"):
        stmt = stmt.strip()
        if stmt and not stmt.startswith("--"):
            try:
                client.command(stmt)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    logger.warning(f"DDL 執行警告: {e}")
    
    logger.info("Silver 層表建立完成")

def transform_varinst_process_pivot(client):
    """轉換流程變數寬表"""
    logger.info("轉換 varinst_process_pivot...")
    start = time.perf_counter()
    
    client.command("TRUNCATE TABLE silver.varinst_process_pivot")
    
    sql = """
    INSERT INTO silver.varinst_process_pivot
    SELECT 
        PROC_INST_ID_ AS proc_inst_id,
        MAX(CASE WHEN NAME_ = 'plant' THEN TEXT_ END) AS plant,
        MAX(CASE WHEN NAME_ = 'factory' THEN TEXT_ END) AS factory,
        MAX(CASE WHEN NAME_ = 'productionArea' THEN TEXT_ END) AS production_area,
        MAX(CASE WHEN NAME_ = 'lineName' THEN TEXT_ END) AS line_name,
        MAX(CASE WHEN NAME_ = 'modelName' THEN TEXT_ END) AS model_name,
        MAX(CASE WHEN NAME_ = 'deliveryArea' THEN TEXT_ END) AS delivery_area,
        MAX(CASE WHEN NAME_ = 'scheduleNumber' THEN TEXT_ END) AS schedule_number,
        MAX(CASE WHEN NAME_ = 'moNumber' THEN TEXT_ END) AS mo_number,
        MAX(CASE WHEN NAME_ = 'sapPlant' THEN TEXT_ END) AS sap_plant,
        MAX(CASE WHEN NAME_ = 'sapProductGroup' THEN TEXT_ END) AS sap_product_group,
        MAX(CASE WHEN NAME_ = 'pallet' THEN TEXT_ END) AS pallet,
        MAX(CASE WHEN NAME_ = 'transferNo' THEN TEXT_ END) AS transfer_no,
        MAX(CASE WHEN NAME_ = 'qBlockEventId' THEN TEXT_ END) AS q_block_event_id,
        MAX(CASE WHEN NAME_ = 'defectSn' THEN TEXT_ END) AS defect_sn,
        MAX(CASE WHEN NAME_ = 'time' THEN concat('_', TEXT_) END) AS time_key,
        MAX(CASE WHEN NAME_ = 'region' THEN TEXT_ END) AS region,
        now64(3) AS _transform_time
    FROM bronze.bpm_act_hi_varinst FINAL
    WHERE NAME_ IN (
        'plant', 'factory', 'productionArea', 'lineName', 'modelName',
        'deliveryArea', 'scheduleNumber', 'moNumber', 'sapPlant', 'sapProductGroup',
        'pallet', 'transferNo', 'qBlockEventId', 'defectSn', 'time', 'region'
    )
      AND PROC_INST_ID_ IS NOT NULL
      AND PROC_INST_ID_ != ''
    GROUP BY PROC_INST_ID_
    """
    client.command(sql)
    
    count = client.command("SELECT count(*) FROM silver.varinst_process_pivot")
    duration = time.perf_counter() - start
    logger.info(f"varinst_process_pivot 完成: {count:,} 筆, 耗時 {duration:.2f} 秒")
    return count

def transform_varinst_task_pivot(client):
    """轉換 Task 變數寬表"""
    logger.info("轉換 varinst_task_pivot...")
    start = time.perf_counter()
    
    client.command("TRUNCATE TABLE silver.varinst_task_pivot")
    
    sql = """
    INSERT INTO silver.varinst_task_pivot
    SELECT 
        TASK_ID_ AS task_id,
        MAX(LONG_) AS auto_complete,
        now64(3) AS _transform_time
    FROM bronze.bpm_act_hi_varinst FINAL
    WHERE NAME_ = 'autoComplete'
      AND TASK_ID_ IS NOT NULL
      AND TASK_ID_ != ''
    GROUP BY TASK_ID_
    """
    client.command(sql)
    
    count = client.command("SELECT count(*) FROM silver.varinst_task_pivot")
    duration = time.perf_counter() - start
    logger.info(f"varinst_task_pivot 完成: {count:,} 筆, 耗時 {duration:.2f} 秒")
    return count

def transform_task_detail_wide(client):
    """轉換任務明細寬表"""
    logger.info("轉換 task_detail_wide...")
    start = time.perf_counter()
    
    client.command("TRUNCATE TABLE silver.task_detail_wide")
    
    sql = """
    INSERT INTO silver.task_detail_wide
    SELECT 
        hti.ID_ AS task_id,
        hti.PROC_INST_ID_ AS proc_inst_id,
        hti.PROC_DEF_ID_ AS proc_def_id,
        pd.KEY_ AS process_definition_key,
        pd.NAME_ AS process_definition_name,
        hi.BUSINESS_KEY_ AS business_key,
        hi.DELETE_REASON_ AS delete_reason,
        hti.TASK_DEF_KEY_ AS task_definition_key,
        hti.NAME_ AS task_name,
        CASE
            WHEN hti.END_TIME_ IS NOT NULL THEN 'DONE'
            WHEN hti.ASSIGNEE_ IS NOT NULL THEN 'DOING'
            ELSE 'TODO'
        END AS task_status,
        CASE WHEN COALESCE(vt.auto_complete, 0) = 1 THEN 'Y' ELSE 'N' END AS task_bypass,
        hti.ASSIGNEE_ AS task_assignee,
        he.ADAccount AS task_assignee_account,
        he.EmpName AS task_assignee_name,
        hti.START_TIME_ AS task_create_time,
        hti.CLAIM_TIME_ AS task_claim_time,
        hti.END_TIME_ AS task_end_time,
        toDate(hti.START_TIME_) AS task_create_date,
        CASE
            WHEN hti.END_TIME_ IS NOT NULL THEN
                round(dateDiff('second', hti.START_TIME_, hti.END_TIME_) / 60.0, 2)
            ELSE
                round(dateDiff('second', hti.START_TIME_, now()) / 60.0, 2)
        END AS task_duration_minutes,
        CASE
            WHEN hti.CLAIM_TIME_ IS NULL THEN 0
            WHEN hti.END_TIME_ IS NOT NULL THEN
                round(dateDiff('second', hti.CLAIM_TIME_, hti.END_TIME_) / 60.0, 2)
            ELSE
                round(dateDiff('second', hti.CLAIM_TIME_, now()) / 60.0, 2)
        END AS task_work_minutes,
        vp.plant,
        vp.factory,
        vp.production_area,
        vp.line_name AS line,
        vp.model_name,
        vp.delivery_area,
        vp.schedule_number,
        vp.mo_number,
        vp.sap_plant,
        vp.sap_product_group,
        vp.pallet,
        vp.transfer_no,
        vp.q_block_event_id,
        vp.defect_sn,
        vp.time_key,
        vp.region,
        now64(3) AS _transform_time
    FROM bronze.bpm_act_hi_taskinst hti FINAL
    INNER JOIN bronze.bpm_act_hi_procinst hi FINAL ON hti.PROC_INST_ID_ = hi.PROC_INST_ID_
    LEFT JOIN bronze.bpm_act_re_procdef pd ON hti.PROC_DEF_ID_ = pd.ID_
    LEFT JOIN silver.varinst_process_pivot vp ON hti.PROC_INST_ID_ = vp.proc_inst_id
    LEFT JOIN silver.varinst_task_pivot vt ON hti.ID_ = vt.task_id
    LEFT JOIN bronze.common_hr_employee he ON hti.ASSIGNEE_ = he.EmpCode
    """
    client.command(sql)
    
    count = client.command("SELECT count(*) FROM silver.task_detail_wide")
    duration = time.perf_counter() - start
    logger.info(f"task_detail_wide 完成: {count:,} 筆, 耗時 {duration:.2f} 秒")
    return count

def verify_reference_result(client):
    """驗證 Reference SQL 結果"""
    logger.info("\n" + "=" * 80)
    logger.info("驗證 Reference SQL 結果")
    logger.info("條件: task_create_date='2025-12-31', task_bypass='N', plant='WJ2', line='E5'")
    logger.info("=" * 80)
    
    # 總筆數
    count = client.command("""
        SELECT count(*) FROM silver.task_detail_wide FINAL
        WHERE task_create_date = '2025-12-31'
          AND task_bypass = 'N'
          AND plant = 'WJ2'
          AND line = 'E5'
    """)
    logger.info(f"總筆數: {count} (預期: 12)")
    
    # 狀態分布
    result = client.query("""
        SELECT task_status, count(*) as cnt
        FROM silver.task_detail_wide FINAL
        WHERE task_create_date = '2025-12-31'
          AND task_bypass = 'N'
          AND plant = 'WJ2'
          AND line = 'E5'
        GROUP BY task_status
        ORDER BY task_status
    """)
    logger.info("狀態分布:")
    for row in result.result_rows:
        logger.info(f"  {row[0]}: {row[1]}")
    logger.info("預期: TODO=8, DOING=2, DONE=2")
    
    # TaskId 清單
    result = client.query("""
        SELECT task_id FROM silver.task_detail_wide FINAL
        WHERE task_create_date = '2025-12-31'
          AND task_bypass = 'N'
          AND plant = 'WJ2'
          AND line = 'E5'
        ORDER BY task_id
    """)
    logger.info(f"\nTaskId 清單 ({len(result.result_rows)} 筆):")
    for row in result.result_rows:
        logger.info(f"  {row[0]}")
    
    return count == 12

def main():
    client = connect()
    
    # 建立表
    create_tables(client)
    
    # 轉換
    transform_varinst_process_pivot(client)
    transform_varinst_task_pivot(client)
    transform_task_detail_wide(client)
    
    # 驗證
    success = verify_reference_result(client)
    
    if success:
        logger.info("\n✅ 驗證通過！ClickHouse 結果與 MSSQL Reference SQL 一致")
    else:
        logger.warning("\n⚠️ 驗證失敗！請檢查資料")

if __name__ == "__main__":
    main()
