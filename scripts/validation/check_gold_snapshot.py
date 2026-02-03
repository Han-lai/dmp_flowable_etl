
import pyodbc
import clickhouse_connect
import os
import pandas as pd
from dotenv import load_dotenv

# Load env for MSSQL
load_dotenv('.env.validation')

MSSQL_HOST = os.getenv('MSSQL_HOST')
MSSQL_PORT = os.getenv('MSSQL_PORT')
MSSQL_DATABASE_BPM = 'APP_SRV_BPM'
MSSQL_USER = os.getenv('MSSQL_USER')
MSSQL_PASSWORD = os.getenv('MSSQL_PASSWORD')
MSSQL_DRIVER = 'SQL Server'

CLICKHOUSE_CONFIG = {
    "host": "10.136.218.207",
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

# MSSQL (Source of Truth)
SQL_MSSQL = f"""
SELECT 
    count(*) as total,
    sum(case when T.END_TIME_ IS NOT NULL then 1 else 0 end) as done
FROM {MSSQL_DATABASE_BPM}.dbo.ACT_HI_TASKINST T
LEFT JOIN {MSSQL_DATABASE_BPM}.dbo.ACT_HI_VARINST V_LINE 
    ON T.PROC_INST_ID_ = V_LINE.PROC_INST_ID_ AND V_LINE.NAME_ = 'lineName'
LEFT JOIN {MSSQL_DATABASE_BPM}.dbo.ACT_HI_VARINST V_MO 
    ON T.PROC_INST_ID_ = V_MO.PROC_INST_ID_ AND V_MO.NAME_ = 'moNumber'
LEFT JOIN {MSSQL_DATABASE_BPM}.dbo.ACT_HI_VARINST V_AUTO 
    ON T.ID_ = V_AUTO.TASK_ID_ AND V_AUTO.NAME_ = 'autoComplete'
WHERE 
    (CAST(T.START_TIME_ as DATE) = '{TARGET_DATE}' OR
     CAST(T.CLAIM_TIME_ as DATE) = '{TARGET_DATE}' OR
     CAST(T.END_TIME_ as DATE) = '{TARGET_DATE}')
    AND V_LINE.TEXT_ = '{LINE}'
    AND (V_AUTO.LONG_ IS NULL OR V_AUTO.LONG_ != 1)
    AND T.TASK_DEF_KEY_ NOT LIKE 'E%'
    AND T.TASK_DEF_KEY_ NOT LIKE 'C%'
    AND (V_MO.TEXT_ NOT LIKE 'Q%' OR V_MO.TEXT_ IS NULL)
    AND (V_MO.TEXT_ NOT LIKE 'R%' OR V_MO.TEXT_ IS NULL)
    AND (T.DELETE_REASON_ IS NULL OR T.DELETE_REASON_ = 'completed')
"""

# Gold (Snapshot)
SQL_GOLD = f"""
SELECT 
    sum(total_task) as total,
    sum(done_count) as done,
    max(_refresh_time) as last_refresh
FROM gold.rmv_l5_task_completion
WHERE 
    snapshot_date = '{TARGET_DATE}'
    AND plant = '{PLANT}'
    AND factory = '{FACTORY}'
    AND line = '{LINE}'
"""

def get_mssql():
    server = f"{MSSQL_HOST},{MSSQL_PORT}"
    conn_str = f'DRIVER={{{MSSQL_DRIVER}}};SERVER={server};DATABASE={MSSQL_DATABASE_BPM};UID={MSSQL_USER};PWD={MSSQL_PASSWORD}'
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

def get_gold():
    try:
        client = clickhouse_connect.get_client(**CLICKHOUSE_CONFIG)
        res = client.query(SQL_GOLD)
        if res.result_rows:
            return list(res.result_rows[0])
        return [0, 0, "No Data"]
    except Exception as e:
        print(f"Gold Error: {e}")
        return ["ERR", "ERR", "ERR"]

def main():
    print(f"=== Checking Gold Layer Snapshot vs MSSQL: {TARGET_DATE} ===\n")
    
    mssql_data = get_mssql()
    gold_data = get_gold()
    
    print(f"{'Source':<15} | {'Total':<10} | {'Done':<10} | {'Notes'}")
    print("-" * 50)
    
    # MSSQL
    if mssql_data[0] == "ERR":
        print(f"{'MSSQL':<15} | {'ERR':<10} | {'ERR':<10} | Connection Failed")
    else:
        print(f"{'MSSQL':<15} | {str(mssql_data[0]):<10} | {str(mssql_data[1]):<10} | Source of Truth")
        
    # Gold
    if gold_data[0] == "ERR":
         print(f"{'ClickHouse':<15} | {'ERR':<10} | {'ERR':<10} | Query Failed")
    else:
        # Handles case where sum returns None if no rows match
        g_total = gold_data[0] if gold_data[0] is not None else 0
        g_done = gold_data[1] if gold_data[1] is not None else 0
        last_refresh = gold_data[2]
        print(f"{'ClickHouse':<15} | {str(g_total):<10} | {str(g_done):<10} | Last Refresh: {last_refresh}")

    print("\n--- Diagnostic ---")
    if str(mssql_data[0]) != str(gold_data[0] if gold_data[0] is not None else 0):
        print("❌ Data Mismatch!")
        if gold_data[0] is None or gold_data[0] == 0:
            print("   Gold layer is empty for this date. It might have refreshed against empty Bronze/Silver.")
            print("   Since `rmv_l5_task_completion` is a REFRESHABLE VIEW, it mirrors Silver's state at refresh time.")
    else:
        print("✅ Data Matches!")

if __name__ == "__main__":
    main()
