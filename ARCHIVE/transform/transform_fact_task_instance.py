"""
fact_task_instance 轉換程式
========================================
從 Bronze 層 bpm_act_hi_taskinst 轉換到 Silver 層 fact_task_instance

來源表：bronze.bpm_act_hi_taskinst
目標表：silver.fact_task_instance

派生邏輯：
- idle_duration_seconds = dateDiff('second', start_time, claim_time)
- work_duration_seconds = dateDiff('second', claim_time, end_time)
- total_duration_seconds = dateDiff('second', start_time, end_time)
- task_status = 根據 DELETE_REASON_, END_TIME_, CLAIM_TIME_ 派生

支援指標：
- #3 任務處理總時間
- #5 任務閒置時長
- #6 個人處理時長
- #7 任務總歷時
- #9 在途任務數
- #12 平均任務處理時長
- #13 自動完成率
- #14 在途任務-依部門
- #17 在途任務-依人員

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""

import logging
from datetime import datetime
from typing import Optional
import clickhouse_connect

# ============================================
# 設定
# ============================================
CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default"
}

# ============================================
# Logging 設定
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ============================================
# 轉換 SQL
# ============================================

# 全量轉換 SQL
# Property 6: 任務閒置時長計算正確性 - idle_duration_seconds = dateDiff(start_time, claim_time)
# Property 7: 任務處理時長計算正確性 - work_duration_seconds = dateDiff(claim_time, end_time)
# Property 8: 任務狀態派生正確性 - task_status 根據規則派生
# Validates: Requirements 3.2, 3.3, 3.5
TRANSFORM_SQL = """
INSERT INTO silver.fact_task_instance
(
    task_id,
    proc_inst_id,
    task_def_key,
    task_name,
    assignee_emp_code,
    start_time,
    claim_time,
    end_time,
    idle_duration_seconds,
    work_duration_seconds,
    total_duration_seconds,
    task_status,
    delete_reason,
    _transform_time
)
SELECT
    ID_ AS task_id,
    COALESCE(PROC_INST_ID_, '') AS proc_inst_id,
    TASK_DEF_KEY_ AS task_def_key,
    NAME_ AS task_name,
    ASSIGNEE_ AS assignee_emp_code,
    START_TIME_ AS start_time,
    CLAIM_TIME_ AS claim_time,
    END_TIME_ AS end_time,
    -- Property 6: 任務閒置時長計算正確性
    if(CLAIM_TIME_ IS NOT NULL, dateDiff('second', START_TIME_, CLAIM_TIME_), NULL) AS idle_duration_seconds,
    -- Property 7: 任務處理時長計算正確性
    if(CLAIM_TIME_ IS NOT NULL AND END_TIME_ IS NOT NULL, dateDiff('second', CLAIM_TIME_, END_TIME_), NULL) AS work_duration_seconds,
    -- 總歷時
    if(END_TIME_ IS NOT NULL, dateDiff('second', START_TIME_, END_TIME_), NULL) AS total_duration_seconds,
    -- Property 8: 任務狀態派生正確性
    -- 規則順序：CANCELLED > AUTOCOMPLETE > DONE > DOING > TODO
    multiIf(
        DELETE_REASON_ IS NOT NULL AND DELETE_REASON_ != '', 'CANCELLED',
        END_TIME_ IS NOT NULL AND lower(COALESCE(DELETE_REASON_, '')) LIKE '%auto%', 'AUTOCOMPLETE',
        END_TIME_ IS NOT NULL, 'DONE',
        CLAIM_TIME_ IS NOT NULL AND END_TIME_ IS NULL, 'DOING',
        'TODO'
    ) AS task_status,
    DELETE_REASON_ AS delete_reason,
    now64(3) AS _transform_time
FROM bronze.bpm_act_hi_taskinst
"""

# 增量轉換 SQL（基於 _sync_time）
INCREMENTAL_TRANSFORM_SQL = """
INSERT INTO silver.fact_task_instance
(
    task_id,
    proc_inst_id,
    task_def_key,
    task_name,
    assignee_emp_code,
    start_time,
    claim_time,
    end_time,
    idle_duration_seconds,
    work_duration_seconds,
    total_duration_seconds,
    task_status,
    delete_reason,
    _transform_time
)
SELECT
    ID_ AS task_id,
    COALESCE(PROC_INST_ID_, '') AS proc_inst_id,
    TASK_DEF_KEY_ AS task_def_key,
    NAME_ AS task_name,
    ASSIGNEE_ AS assignee_emp_code,
    START_TIME_ AS start_time,
    CLAIM_TIME_ AS claim_time,
    END_TIME_ AS end_time,
    if(CLAIM_TIME_ IS NOT NULL, dateDiff('second', START_TIME_, CLAIM_TIME_), NULL) AS idle_duration_seconds,
    if(CLAIM_TIME_ IS NOT NULL AND END_TIME_ IS NOT NULL, dateDiff('second', CLAIM_TIME_, END_TIME_), NULL) AS work_duration_seconds,
    if(END_TIME_ IS NOT NULL, dateDiff('second', START_TIME_, END_TIME_), NULL) AS total_duration_seconds,
    multiIf(
        DELETE_REASON_ IS NOT NULL AND DELETE_REASON_ != '', 'CANCELLED',
        END_TIME_ IS NOT NULL AND lower(COALESCE(DELETE_REASON_, '')) LIKE '%auto%', 'AUTOCOMPLETE',
        END_TIME_ IS NOT NULL, 'DONE',
        CLAIM_TIME_ IS NOT NULL AND END_TIME_ IS NULL, 'DOING',
        'TODO'
    ) AS task_status,
    DELETE_REASON_ AS delete_reason,
    now64(3) AS _transform_time
FROM bronze.bpm_act_hi_taskinst
WHERE _sync_time > '{last_sync_time}'
"""


# ============================================
# 轉換函數
# ============================================

def connect_clickhouse() -> clickhouse_connect.driver.Client:
    """建立 ClickHouse 連線"""
    logger.info(f"連線 ClickHouse: {CLICKHOUSE_CONFIG['host']}:{CLICKHOUSE_CONFIG['port']}")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    client.command("SELECT 1")
    logger.info("ClickHouse 連線成功")
    return client


def get_last_transform_time(client: clickhouse_connect.driver.Client) -> Optional[datetime]:
    """取得上次轉換時間"""
    sql = """
    SELECT max(_transform_time) 
    FROM silver.fact_task_instance
    """
    result = client.command(sql)
    if result and result != '1970-01-01 00:00:00.000':
        return result
    return None


def get_source_count(client: clickhouse_connect.driver.Client) -> int:
    """取得來源表筆數"""
    return client.command("SELECT count(*) FROM bronze.bpm_act_hi_taskinst")


def get_target_count(client: clickhouse_connect.driver.Client) -> int:
    """取得目標表筆數（FINAL 確保去重）"""
    return client.command("SELECT count(*) FROM silver.fact_task_instance FINAL")


def transform_full(client: clickhouse_connect.driver.Client) -> int:
    """全量轉換"""
    logger.info("執行全量轉換...")
    
    # 清空目標表
    client.command("TRUNCATE TABLE silver.fact_task_instance")
    
    # 執行轉換
    client.command(TRANSFORM_SQL)
    
    # 取得寫入筆數
    rows_written = get_target_count(client)
    logger.info(f"全量轉換完成，寫入 {rows_written:,} 筆")
    
    return rows_written


def transform_incremental(client: clickhouse_connect.driver.Client, last_sync_time: datetime) -> int:
    """增量轉換"""
    logger.info(f"執行增量轉換，上次同步時間: {last_sync_time}")
    
    # 取得轉換前筆數
    before_count = get_target_count(client)
    
    # 執行轉換
    sql = INCREMENTAL_TRANSFORM_SQL.format(last_sync_time=last_sync_time)
    client.command(sql)
    
    # 取得轉換後筆數
    after_count = get_target_count(client)
    rows_written = after_count - before_count
    
    logger.info(f"增量轉換完成，新增/更新 {rows_written:,} 筆")
    
    return rows_written


def log_transform(
    client: clickhouse_connect.driver.Client,
    batch_id: str,
    transform_type: str,
    start_time: datetime,
    rows_read: int,
    rows_written: int,
    status: str,
    error_message: Optional[str] = None
):
    """記錄轉換日誌"""
    sql = """
    INSERT INTO silver._transform_log
    (batch_id, table_name, transform_type, start_time, end_time, status, rows_read, rows_written, error_message)
    VALUES
    ('{batch_id}', 'fact_task_instance', '{transform_type}', '{start_time}', now64(3), '{status}', {rows_read}, {rows_written}, {error_message})
    """.format(
        batch_id=batch_id,
        transform_type=transform_type,
        start_time=start_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
        status=status,
        rows_read=rows_read,
        rows_written=rows_written,
        error_message=f"'{error_message}'" if error_message else "NULL"
    )
    client.command(sql)


def run_transform(mode: str = "auto") -> dict:
    """
    執行轉換
    
    Args:
        mode: 轉換模式
            - "full": 強制全量轉換
            - "incremental": 強制增量轉換
            - "auto": 自動判斷（目標表為空則全量，否則增量）
    
    Returns:
        dict: 轉換結果
    """
    client = connect_clickhouse()
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    start_time = datetime.now()
    
    result = {
        "batch_id": batch_id,
        "table": "fact_task_instance",
        "mode": mode,
        "status": "success",
        "rows_read": 0,
        "rows_written": 0,
        "error": None
    }
    
    try:
        # 取得來源筆數
        result["rows_read"] = get_source_count(client)
        logger.info(f"來源表 bronze.bpm_act_hi_taskinst: {result['rows_read']:,} 筆")
        
        # 判斷轉換模式
        if mode == "auto":
            target_count = get_target_count(client)
            if target_count == 0:
                mode = "full"
                logger.info("目標表為空，使用全量轉換")
            else:
                mode = "incremental"
                logger.info(f"目標表有 {target_count:,} 筆，使用增量轉換")
        
        result["mode"] = mode
        
        # 執行轉換
        if mode == "full":
            result["rows_written"] = transform_full(client)
        else:
            last_sync_time = get_last_transform_time(client)
            if last_sync_time:
                result["rows_written"] = transform_incremental(client, last_sync_time)
            else:
                logger.info("找不到上次轉換時間，改用全量轉換")
                result["rows_written"] = transform_full(client)
                result["mode"] = "full"
        
        # 記錄日誌
        log_transform(
            client, batch_id, 
            "full" if result["mode"] == "full" else "incremental",
            start_time, result["rows_read"], result["rows_written"], "success"
        )
        
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        logger.error(f"轉換失敗: {e}")
        
        # 記錄錯誤日誌
        log_transform(
            client, batch_id, 
            "full" if mode == "full" else "incremental",
            start_time, result["rows_read"], result["rows_written"], "failed", str(e)
        )
    
    return result


def main():
    """主程式"""
    logger.info("=" * 60)
    logger.info("開始 fact_task_instance 轉換")
    logger.info("=" * 60)
    
    result = run_transform(mode="auto")
    
    logger.info("=" * 60)
    logger.info(f"轉換結果: {result['status']}")
    logger.info(f"模式: {result['mode']}")
    logger.info(f"讀取: {result['rows_read']:,} 筆")
    logger.info(f"寫入: {result['rows_written']:,} 筆")
    if result["error"]:
        logger.error(f"錯誤: {result['error']}")
    logger.info("=" * 60)
    
    return result


if __name__ == "__main__":
    main()
