
import pyodbc
import clickhouse_connect
import sys

# Config
server = 'WJOAUATDB01S.delta.corp,65000'
username = 'APP_SRV_BPM'
password = 'APP_SRV_BPM'

ch_client = clickhouse_connect.get_client(host='REDACTED_IP', port=8121, username='default', password='default')

def get_mssql_count(db, query):
    conn_str = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={db};UID={username};PWD={password}'
    try:
        conn = pyodbc.connect(conn_str, timeout=15)
        cursor = conn.cursor()
        cursor.execute(query)
        res = cursor.fetchone()
        conn.close()
        return res[0]
    except Exception as e:
        return f"Error: {e}"

def verify_scenario(date_str, plant, line):
    print(f"\n--- Verification Scenario: {date_str} | {plant} | {line} ---")
    
    # 1. FlowableTaskStats_0202
    # Note: Using parameterized-style strings (double quotes for CH jdbc or just f-string for direct MSSQL)
    query_0202 = f"""
    SELECT count(*) FROM FlowableTaskStats_0202 i
    WHERE (
        CAST(i.TaskCreateDate AS DATE) = '{date_str}'
        OR CAST(i.TaskEndDate AS DATE) = '{date_str}'
        OR CAST(i.TaskClaimDate AS DATE) = '{date_str}'
    )
    AND i.TaskBypass ='N' AND i.TaskStatus = 'DONE'
    AND i.Plant = '{plant}' AND i.Line = '{line}'
    AND (
        i.MoNumber NOT LIKE 'E%' 
        AND i.MoNumber NOT LIKE 'C%' 
        AND i.MoNumber NOT LIKE 'Q%' 
        AND i.MoNumber NOT LIKE 'R%'
    )
    """
    c1 = get_mssql_count('APP_SRV_COMMON', query_0202)
    print(f"1. MSSQL FlowableTaskStats_0202: {c1}")

    # 2. MSSQL Raw
    # Searching for correct DB
    # We use APP_SRV_BPM for raw taskinst, but we need to check if 0108 is the correct suffix for OCT data.
    # Usually it is.
    query_raw = f"""
    SELECT count(DISTINCT hti.ID_)
    FROM APP_SRV_BPM.dbo.ACT_HI_PROCINST_0108 hi
    LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 var_plant on hi.PROC_INST_ID_ = var_plant.PROC_INST_ID_ and var_plant.NAME_ = 'plant'
    LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 var_lineName on hi.PROC_INST_ID_ = var_lineName.PROC_INST_ID_ and var_lineName.NAME_ = 'lineName'
    LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 var_mo on hi.PROC_INST_ID_ = var_mo.PROC_INST_ID_ and var_mo.NAME_ = 'moNumber'
    LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_TASKINST_0108 hti ON hi.PROC_INST_ID_ = hti.PROC_INST_ID_
    LEFT JOIN APP_SRV_BPM.dbo.ACT_HI_VARINST_0108 tb ON hti.ID_ = tb.TASK_ID_ AND tb.NAME_ = 'autoComplete'
    WHERE (
        CAST(hti.START_TIME_ AS DATE) = '{date_str}'
        OR CAST(hti.CLAIM_TIME_ AS DATE) = '{date_str}'
        OR CAST(hti.END_TIME_ AS DATE) = '{date_str}'
    )
    AND var_plant.TEXT_ = '{plant}'
    AND var_lineName.TEXT_ = '{line}'
    AND (tb.LONG_ IS NULL OR tb.LONG_ = 0)
    AND hti.END_TIME_ IS NOT NULL
    AND (
        var_mo.TEXT_ NOT LIKE 'E%' 
        AND var_mo.TEXT_ NOT LIKE 'C%' 
        AND var_mo.TEXT_ NOT LIKE 'Q%' 
        AND var_mo.TEXT_ NOT LIKE 'R%'
    )
    """
    c2 = get_mssql_count('APP_SRV_BPM', query_raw)
    print(f"2. MSSQL Raw Data:             {c2}")

    # 3. ClickHouse Gold
    query_ch = f"""
    SELECT sum(total_task) FROM gold.rmv_l5_task_completion 
    WHERE snapshot_date = '{date_str}' 
    AND plant = '{plant}' AND line = '{line}'
    """
    c3 = ch_client.command(query_ch)
    # Check if empty
    if c3 is None or c3 == "":
        c3 = 0
    print(f"3. ClickHouse Gold Layer:      {c3}")
    
    return c1, c2, c3

# Scenarios to test
scenarios = [
    ('2025-12-25', 'WJ2', 'E5'),    # Already aligned
    ('2025-10-22', 'DG3', 'ST11'),  # Large Oct data
]

for d, p, l in scenarios:
    verify_scenario(d, p, l)
