"""
Silver Layer Database 建立腳本
========================================
依據 design.md 建立 Silver Layer 所有表結構

使用方式：
    python sql/04_create_silver_database.py

表結構說明：
1. fact_biz_event      - 業務事件表（by BUSINESS_KEY_），支援指標 #1,2,8,10,11,18
2. fact_process_instance - 流程實例表（by PROC_INST_ID_），支援指標 #4
3. fact_task_instance  - 任務實例表（by TASK_ID_），支援指標 #3,5,6,7,9,12,13,14,17
4. fact_task_stats     - 任務統計表（by TaskId），支援指標 #15,16
5. dim_employee        - 員工維度表（by EmpCode），提供人員/部門/地區維度 JOIN
"""

import logging
from typing import List, Tuple
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
# DDL 定義
# ============================================

# 建立 Silver Database
CREATE_DATABASE_SQL = "CREATE DATABASE IF NOT EXISTS silver"

# 轉換日誌表
CREATE_TRANSFORM_LOG_SQL = """
CREATE TABLE IF NOT EXISTS silver._transform_log
(
    batch_id String,
    table_name LowCardinality(String),
    transform_type Enum8('full' = 1, 'incremental' = 2),
    start_time DateTime64(3),
    end_time Nullable(DateTime64(3)),
    status Enum8('running' = 1, 'success' = 2, 'failed' = 3),
    rows_read UInt64 DEFAULT 0,
    rows_written UInt64 DEFAULT 0,
    error_message Nullable(String)
)
ENGINE = MergeTree()
ORDER BY (table_name, start_time)
SETTINGS index_granularity = 8192
"""

# 1. fact_biz_event - 業務事件表
# 支援指標：#1 業務事件總歷時, #2 流程執行總時間, #8 在途業務事件數, 
#          #10 逾期在途數(部分), #11 平均業務事件總歷時, #18 流程健康度快照(部分)
CREATE_FACT_BIZ_EVENT_SQL = """
CREATE TABLE IF NOT EXISTS silver.fact_biz_event
(
    -- 主鍵
    biz_event_key String COMMENT '業務事件主鍵 (BUSINESS_KEY_)',
    
    -- 時間欄位
    first_start_time DateTime COMMENT '首個流程開始時間 MIN(START_TIME_)',
    final_end_time Nullable(DateTime) COMMENT '最後流程結束時間 MAX(END_TIME_)',
    
    -- 派生欄位
    total_duration_seconds Nullable(Int64) COMMENT '總歷時（秒）= dateDiff(first_start_time, final_end_time)',
    process_count Int32 COMMENT '流程實例數量 COUNT(*)',
    is_in_progress UInt8 COMMENT '是否在途 (final_end_time IS NULL ? 1 : 0)',
    
    -- 流程定義資訊（取首個流程）
    first_proc_def_key String DEFAULT '' COMMENT '首個流程定義 Key',
    first_proc_def_name String DEFAULT '' COMMENT '首個流程名稱',
    
    -- 系統欄位
    _transform_time DateTime64(3) DEFAULT now64(3) COMMENT '轉換時間'
)
ENGINE = ReplacingMergeTree(_transform_time)
PARTITION BY toYYYYMM(first_start_time)
ORDER BY biz_event_key
SETTINGS index_granularity = 8192
"""

# 2. fact_process_instance - 流程實例表
# 支援指標：#4 流程總歷時
CREATE_FACT_PROCESS_INSTANCE_SQL = """
CREATE TABLE IF NOT EXISTS silver.fact_process_instance
(
    -- 主鍵
    proc_inst_id String COMMENT '流程實例 ID (PROC_INST_ID_)',
    
    -- 關聯鍵
    biz_event_key String COMMENT '業務事件 Key (BUSINESS_KEY_)',
    proc_def_id String COMMENT '流程定義 ID (PROC_DEF_ID_)',
    
    -- 流程定義資訊（JOIN ACT_RE_PROCDEF）
    proc_def_key String DEFAULT '' COMMENT '流程定義 Key',
    proc_def_name String DEFAULT '' COMMENT '流程名稱',
    
    -- 時間欄位
    start_time DateTime COMMENT '開始時間 (START_TIME_)',
    end_time Nullable(DateTime) COMMENT '結束時間 (END_TIME_)',
    
    -- 派生欄位
    duration_seconds Nullable(Int64) COMMENT '執行時長（秒）= DURATION_ / 1000',
    is_completed UInt8 COMMENT '是否完成 (END_TIME_ IS NOT NULL ? 1 : 0)',
    
    -- 其他欄位
    start_user_id Nullable(String) COMMENT '啟動人員 (START_USER_ID_)',
    delete_reason Nullable(String) COMMENT '刪除原因 (DELETE_REASON_)',
    
    -- 系統欄位
    _transform_time DateTime64(3) DEFAULT now64(3) COMMENT '轉換時間'
)
ENGINE = ReplacingMergeTree(_transform_time)
PARTITION BY toYYYYMM(start_time)
ORDER BY proc_inst_id
SETTINGS index_granularity = 8192
"""

# 3. fact_task_instance - 任務實例表
# 支援指標：#3 任務處理總時間, #5 任務閒置時長, #6 個人處理時長, #7 任務總歷時,
#          #9 在途任務數, #12 平均任務處理時長, #13 自動完成率, #14 在途任務-依部門, #17 在途任務-依人員
CREATE_FACT_TASK_INSTANCE_SQL = """
CREATE TABLE IF NOT EXISTS silver.fact_task_instance
(
    -- 主鍵
    task_id String COMMENT '任務 ID (ID_)',
    
    -- 關聯鍵
    proc_inst_id String COMMENT '流程實例 ID (PROC_INST_ID_)',
    
    -- 任務定義
    task_def_key Nullable(String) COMMENT '任務定義 Key (TASK_DEF_KEY_)',
    task_name Nullable(String) COMMENT '任務名稱 (NAME_)',
    
    -- 承接人
    assignee_emp_code Nullable(String) COMMENT '承接人工號 (ASSIGNEE_)',
    
    -- 時間欄位
    start_time DateTime COMMENT '建立時間 (START_TIME_)',
    claim_time Nullable(DateTime) COMMENT '認領時間 (CLAIM_TIME_)',
    end_time Nullable(DateTime) COMMENT '完成時間 (END_TIME_)',
    
    -- 派生時長欄位（秒）
    idle_duration_seconds Nullable(Int64) COMMENT '閒置時長 = dateDiff(start_time, claim_time)',
    work_duration_seconds Nullable(Int64) COMMENT '處理時長 = dateDiff(claim_time, end_time)',
    total_duration_seconds Nullable(Int64) COMMENT '總歷時 = dateDiff(start_time, end_time)',
    
    -- 派生狀態欄位
    task_status LowCardinality(String) COMMENT '任務狀態 (TODO/DOING/DONE/AUTOCOMPLETE/CANCELLED)',
    
    -- 其他欄位
    delete_reason Nullable(String) COMMENT '刪除原因 (DELETE_REASON_)',
    
    -- 系統欄位
    _transform_time DateTime64(3) DEFAULT now64(3) COMMENT '轉換時間'
)
ENGINE = ReplacingMergeTree(_transform_time)
PARTITION BY toYYYYMM(start_time)
ORDER BY task_id
SETTINGS index_granularity = 8192
"""

# 4. fact_task_stats - 任務統計表
# 支援指標：#15 在途任務-依地區, #16 在途任務-依廠區
# 注意：task_create_date 改為 NOT NULL，預設 '1970-01-01'，避免 PARTITION BY Nullable 問題
CREATE_FACT_TASK_STATS_SQL = """
CREATE TABLE IF NOT EXISTS silver.fact_task_stats
(
    -- 主鍵
    task_id String COMMENT '任務 ID (TaskId)',
    
    -- 關聯鍵
    proc_inst_id Nullable(String) COMMENT '流程實例 ID (ProcessInstanceId)',
    
    -- 流程定義
    proc_def_key Nullable(String) COMMENT '流程定義 Key (ProcessDefinitionKey)',
    proc_def_name Nullable(String) COMMENT '流程名稱 (ProcessDefinitionName)',
    
    -- 地理維度（支援指標 #15, #16）
    plant Nullable(String) COMMENT '廠區 (Plant)',
    factory Nullable(String) COMMENT '工廠 (Factory)',
    production_area Nullable(String) COMMENT '生產區域 (ProductionArea)',
    
    -- 任務資訊
    task_name Nullable(String) COMMENT '任務名稱 (TaskName)',
    task_status LowCardinality(String) COMMENT '任務狀態 (TODO/DOING/DONE/AUTOCOMPLETE)',
    
    -- 承接人
    assignee_emp_code Nullable(String) COMMENT '承接人工號 (TaskAssignee)',
    assignee_name Nullable(String) COMMENT '承接人姓名 (TaskAssigneeName)',
    
    -- 時間欄位
    task_create_time Nullable(DateTime) COMMENT '建立時間 (TaskCreateTime)',
    task_claim_time Nullable(DateTime) COMMENT '認領時間 (TaskClaimTime)',
    task_end_time Nullable(DateTime) COMMENT '完成時間 (TaskEndTime)',
    
    -- 派生時長欄位（秒）- 從分鐘轉換
    task_duration_seconds Nullable(Int64) COMMENT '總歷時（秒）= TaskDurationMinutes * 60',
    task_work_seconds Nullable(Int64) COMMENT '處理時長（秒）= TaskWorkMinutes * 60',
    
    -- 分區用（NOT NULL，預設 1970-01-01 避免 PARTITION BY Nullable 問題）
    task_create_date Date DEFAULT '1970-01-01' COMMENT '建立日期 (TaskCreateDate)',
    
    -- 系統欄位
    _transform_time DateTime64(3) DEFAULT now64(3) COMMENT '轉換時間'
)
ENGINE = ReplacingMergeTree(_transform_time)
PARTITION BY toYYYYMM(task_create_date)
ORDER BY task_id
SETTINGS index_granularity = 8192
"""

# 5. dim_employee - 員工維度表
# 提供人員/部門/地區維度 JOIN，支援指標 #14, #15, #17
CREATE_DIM_EMPLOYEE_SQL = """
CREATE TABLE IF NOT EXISTS silver.dim_employee
(
    -- 主鍵
    emp_code String COMMENT '員工工號 (EmpCode)',
    
    -- 基本資訊
    emp_name Nullable(String) COMMENT '員工姓名 (EmpName)',
    display_name Nullable(String) COMMENT '顯示名稱 (DisplayName)',
    ad_account Nullable(String) COMMENT 'AD 帳號 (ADAccount)',
    email Nullable(String) COMMENT '電子郵件 (Email)',
    
    -- 組織維度（支援指標 #14 在途任務-依部門）
    department_code Nullable(String) COMMENT '部門代碼 (DeptCode)',
    department_name Nullable(String) COMMENT '部門名稱 (DeptCodeLname)',
    
    -- 工廠維度
    factory_code Nullable(String) COMMENT '工廠代碼 (FactoryCode)',
    factory_name Nullable(String) COMMENT '工廠名稱 (FactoryLname)',
    
    -- 地區維度（支援指標 #15 在途任務-依地區）
    area_id Nullable(String) COMMENT '地區 ID (AreaID)',
    area_name Nullable(String) COMMENT '地區名稱 (AreaLname)',
    
    -- 主管
    supervisor_emp_code Nullable(String) COMMENT '主管工號 (Supervisor)',
    
    -- 派生欄位
    is_active UInt8 COMMENT '是否在職 (TerminateDate IS NULL OR > now() ? 1 : 0)',
    terminate_date Nullable(DateTime) COMMENT '離職日期 (TerminateDate)',
    
    -- 系統欄位
    _transform_time DateTime64(3) DEFAULT now64(3) COMMENT '轉換時間'
)
ENGINE = ReplacingMergeTree(_transform_time)
ORDER BY emp_code
SETTINGS index_granularity = 8192
"""

# ============================================
# 執行函數
# ============================================

def connect_clickhouse() -> clickhouse_connect.driver.Client:
    """建立 ClickHouse 連線"""
    logger.info(f"連線 ClickHouse: {CLICKHOUSE_CONFIG['host']}:{CLICKHOUSE_CONFIG['port']}")
    client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
    client.command("SELECT 1")
    logger.info("ClickHouse 連線成功")
    return client


def execute_ddl(client: clickhouse_connect.driver.Client, sql: str, description: str) -> bool:
    """執行 DDL 語句"""
    try:
        client.command(sql)
        logger.info(f"✅ {description}")
        return True
    except Exception as e:
        logger.error(f"❌ {description} 失敗: {e}")
        return False


def create_silver_database(client: clickhouse_connect.driver.Client) -> List[Tuple[str, bool]]:
    """建立 Silver Database 與所有表結構"""
    results = []
    
    # 1. 建立 Database
    results.append((
        "CREATE DATABASE silver",
        execute_ddl(client, CREATE_DATABASE_SQL, "建立 silver database")
    ))
    
    # 2. 建立轉換日誌表
    results.append((
        "CREATE TABLE silver._transform_log",
        execute_ddl(client, CREATE_TRANSFORM_LOG_SQL, "建立 silver._transform_log")
    ))
    
    # 3. 建立 fact_biz_event
    results.append((
        "CREATE TABLE silver.fact_biz_event",
        execute_ddl(client, CREATE_FACT_BIZ_EVENT_SQL, "建立 silver.fact_biz_event")
    ))
    
    # 4. 建立 fact_process_instance
    results.append((
        "CREATE TABLE silver.fact_process_instance",
        execute_ddl(client, CREATE_FACT_PROCESS_INSTANCE_SQL, "建立 silver.fact_process_instance")
    ))
    
    # 5. 建立 fact_task_instance
    results.append((
        "CREATE TABLE silver.fact_task_instance",
        execute_ddl(client, CREATE_FACT_TASK_INSTANCE_SQL, "建立 silver.fact_task_instance")
    ))
    
    # 6. 建立 fact_task_stats
    results.append((
        "CREATE TABLE silver.fact_task_stats",
        execute_ddl(client, CREATE_FACT_TASK_STATS_SQL, "建立 silver.fact_task_stats")
    ))
    
    # 7. 建立 dim_employee
    results.append((
        "CREATE TABLE silver.dim_employee",
        execute_ddl(client, CREATE_DIM_EMPLOYEE_SQL, "建立 silver.dim_employee")
    ))
    
    return results


def print_summary(results: List[Tuple[str, bool]]):
    """輸出執行結果摘要"""
    print("\n" + "=" * 60)
    print("Silver Layer 建表結果")
    print("=" * 60)
    
    success_count = 0
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {name}")
        if success:
            success_count += 1
    
    print("-" * 60)
    print(f"總計: {success_count}/{len(results)} 成功")
    print("=" * 60)


def main():
    """主程式"""
    logger.info("開始建立 Silver Layer Database...")
    
    # 連線
    client = connect_clickhouse()
    
    # 建立所有表
    results = create_silver_database(client)
    
    # 輸出摘要
    print_summary(results)
    
    # 驗證表是否存在
    logger.info("\n驗證已建立的表...")
    tables = client.command("SELECT name FROM system.tables WHERE database = 'silver' ORDER BY name")
    logger.info(f"silver database 中的表: {tables}")


if __name__ == "__main__":
    main()
