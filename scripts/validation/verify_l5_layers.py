
import pyodbc
import clickhouse_connect
import os
import pandas as pd
from dotenv import load_dotenv

# Load env for MSSQL
load_dotenv('.env.validation')

MSSQL_HOST = os.getenv('MSSQL_HOST')
MSSQL_PORT = os.getenv('MSSQL_PORT')
MSSQL_DATABASE = 'APP_SRV_COMMON'
MSSQL_USER = os.getenv('MSSQL_USER')
MSSQL_PASSWORD = os.getenv('MSSQL_PASSWORD')
MSSQL_DRIVER = 'SQL Server'

# ClickHouse Config
CLICKHOUSE_CONFIG = {
    "host": "REDACTED_IP",
    "port": 8121,
    "username": "default",
    "password": "default",
    "database": "default",
    "send_receive_timeout": 300
}

TARGET_DATE = '2025-12-25'
PLANT = 'WJ2'
FACTORY = 'NBU'
LINE = 'E5'

# ==========================================
# 1. SQL Definitions
# ==========================================

# 1.1 MSSQL Source (Truth)
SQL_MSSQL = f"""
SELECT 
    count(*) as total,
    sum(case when upper(TaskStatus) = 'DONE' then 1 else 0 end) as done
FROM APP_SRV_COMMON.dbo.FlowableTaskStats_0202
WHERE 
    Plant = '{PLANT}'
    AND Factory = '{FACTORY}'
    AND Line = '{LINE}'
    AND (
        CAST(TaskCreateTime as DATE) = '{TARGET_DATE}' OR
        CAST(TaskClaimTime as DATE) = '{TARGET_DATE}' OR
        CAST(TaskEndTime as DATE) = '{TARGET_DATE}'
    )
    AND (TaskBypass = 'N' OR TaskBypass IS NULL)
    AND (DeleteReason IS NULL OR DeleteReason = 'completed')
    AND TaskDefinitionKey NOT LIKE 'E%'
    AND TaskDefinitionKey NOT LIKE 'C%'
    AND (MoNumber NOT LIKE 'Q%' OR MoNumber IS NULL)
    AND (MoNumber NOT LIKE 'R%' OR MoNumber IS NULL)
"""

# 1.3 ClickHouse Silver
# Source: silver.mv_fact_task_vx
# Uses is_excluded=0 which encapsulates business rules
SQL_SILVER = f"""
SELECT 
    count() as total,
    countIf(task_status = 'DONE') as done
FROM silver.mv_fact_task_vx FINAL
WHERE 
    plant = '{PLANT}'
    AND factory = '{FACTORY}'
    AND line = '{LINE}'
    AND (
        toDate(task_create_date) = '{TARGET_DATE}' OR
        toDate(task_claim_date) = '{TARGET_DATE}' OR
        toDate(task_end_date) = '{TARGET_DATE}'
    )
    AND is_excluded = 0
"""

# 1.4 ClickHouse Gold
# Source: gold.rmv_l5_task_completion
SQL_GOLD = f"""
SELECT 
    sum(total_task) as total,
    sum(done_count) as done
FROM gold.rmv_l5_task_completion FINAL
WHERE 
    plant = '{PLANT}'
    AND factory = '{FACTORY}'
    AND line = '{LINE}'
    AND snapshot_date = '{TARGET_DATE}'
"""

def safe_run_mssql():
    server = f"{MSSQL_HOST},{MSSQL_PORT}"
    conn_str = f'DRIVER={{{MSSQL_DRIVER}}};SERVER={server};DATABASE={MSSQL_DATABASE};UID={MSSQL_USER};PWD={MSSQL_PASSWORD}'
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute(SQL_MSSQL)
        row = cursor.fetchone()
        conn.close()
        return list(row)
    except Exception as e:
        print(f"MSSQL Error: {e}")
        return ["ERR", "ERR"]

def safe_run_clickhouse(label, sql):
    try:
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        res = client.query(sql)
        if res.result_rows:
            return list(res.result_rows[0])
        return [0, 0]
    except Exception as e:
        print(f"ClickHouse {label} Error: {e}")
        return ["ERR", "ERR"]

def main():
    print(f"=== E2E Layer Verification (Skip Bronze): {TARGET_DATE} {PLANT}/{FACTORY}/{LINE} ===\n")
    
    # 1. MSSQL Source
    mssql_res = safe_run_mssql()
    
    # 2. CH Silver
    silver_res = safe_run_clickhouse("Silver", SQL_SILVER)
    
    # 3. CH Gold
    gold_res = safe_run_clickhouse("Gold", SQL_GOLD)

    # Output
    print(f"{'Layer':<20} | {'Total':<10} | {'Done':<10} | {'Match MSSQL?'}")
    print("-" * 60)
    
    # Validation Logic
    base_done = mssql_res[1]
    
    def check_match(val):
        if val == "ERR": return "ERROR"
        return "✅" if val == base_done else "❌"

    print(f"{'MSSQL (Truth)':<20} | {str(mssql_res[0]):<10} | {str(mssql_res[1]):<10} | {'(Source)'}")
    print(f"{'CH Silver':<20} | {str(silver_res[0]):<10} | {str(silver_res[1]):<10} | {check_match(silver_res[1])}")
    print(f"{'CH Gold':<20} | {str(gold_res[0]):<10} | {str(gold_res[1]):<10} | {check_match(gold_res[1])}")

if __name__ == "__main__":
    main()
